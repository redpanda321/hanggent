# ========= Copyright 2025-2026 @ Hanggent.AI All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ========= Copyright 2025-2026 @ Hanggent.AI All Rights Reserved. =========

import asyncio
import logging

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi_babel import _
from sqlmodel import Session, select

from app.component import code
from app.component.auth import Auth
from app.component.database import session
from app.component.encrypt import password_verify
from app.component.stack_auth import StackAuth
from app.exception.exception import UserException
from app.model.user.user import (
    LoginByPasswordIn,
    LoginResponse,
    RegisterIn,
    Status,
    User,
)
from app.service import openclaw_service

logger = logging.getLogger("server_login_controller")

router = APIRouter(tags=["Login/Registration"])


@router.post("/login", name="login by email or password")
async def by_password(data: LoginByPasswordIn, session: Session = Depends(session)) -> LoginResponse:
    """
    User login with email and password
    """
    email = data.email
    user = User.by(User.email == email, s=session).one_or_none()

    if not user:
        logger.warning("Login failed: user not found", extra={"email": email})
        raise UserException(code.password, _("Account or password error"))

    if not password_verify(data.password, user.password):
        logger.warning("Login failed: invalid password", extra={"user_id": user.id, "email": email})
        raise UserException(code.password, _("Account or password error"))

    logger.info("User login successful", extra={"user_id": user.id, "email": email})

    # Auto-start OpenClaw if user has channels configured (fire-and-forget, don't break login)
    try:
        if user.bot_channels:
            asyncio.create_task(
                openclaw_service.ensure_bot_running_fire_and_forget(user.id, user.bot_channels)
            )
    except Exception as e:
        logger.warning("Failed to schedule OpenClaw auto-start on login: %s", e)

    return LoginResponse(token=Auth.create_access_token(user.id), email=user.email)


@router.post("/dev_login", name="OAuth2 password flow login (for Swagger UI)")
async def dev_login(
    username: str = Form(...),  # OAuth2 uses 'username' but we accept email
    password: str = Form(...),
    session: Session = Depends(session),
) -> dict:
    """
    OAuth2 password flow compatible login endpoint for Swagger UI.
    This endpoint accepts form data (username/password) and returns an access token.
    """
    # Use username as email (OAuth2 standard uses 'username' field)
    email = username
    user = User.by(User.email == email, s=session).one_or_none()

    if not user:
        logger.warning("OAuth2 login failed: user not found", extra={"email": email})
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    if not password_verify(password, user.password):
        logger.warning(
            "OAuth2 login failed: invalid password",
            extra={"user_id": user.id, "email": email},
        )
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    token = Auth.create_access_token(user.id)
    logger.info("OAuth2 login successful", extra={"user_id": user.id, "email": email})

    # Return OAuth2 compatible response
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login-by_stack", name="login by stack")
async def by_stack_auth(
    token: str,
    type: str = "signup",
    invite_code: str | None = None,
    session: Session = Depends(session),
):
    try:
        stack_id = await StackAuth.user_id(token)
        info = await StackAuth.user_info(token)
    except Exception as e:
        logger.error("Stack auth failed", extra={"type": type, "error": str(e)}, exc_info=True)
        raise HTTPException(500, detail=_("Authentication failed"))

    user = User.by(User.stack_id == stack_id, s=session).one_or_none()

    if not user:
        if type != "signup":
            logger.warning(
                "Stack auth signup blocked: user not found",
                extra={"stack_id": stack_id, "type": type},
            )
            raise UserException(code.error, _("User not found"))

        with session as s:
            try:
                user = User(
                    username=info["username"] if "username" in info else None,
                    nickname=info["display_name"],
                    email=info["primary_email"],
                    avatar=info["profile_image_url"],
                    stack_id=stack_id,
                )
                s.add(user)
                s.commit()
                s.refresh(user)
                logger.info(
                    "New user registered via stack",
                    extra={
                        "user_id": user.id,
                        "email": user.email,
                        "stack_id": stack_id,
                    },
                )
                return LoginResponse(token=Auth.create_access_token(user.id), email=user.email)
            except Exception as e:
                s.rollback()
                logger.error(
                    "Stack auth registration failed",
                    extra={"stack_id": stack_id, "error": str(e)},
                    exc_info=True,
                )
                raise UserException(code.error, _("Failed to register"))
    else:
        if user.status == Status.Block:
            logger.warning(
                "Blocked user login attempt",
                extra={"user_id": user.id, "stack_id": stack_id},
            )
            raise UserException(code.error, _("Your account has been blocked."))

        logger.info(
            "User login via stack successful",
            extra={"user_id": user.id, "email": user.email, "stack_id": stack_id},
        )

        # Auto-start OpenClaw if user has channels configured (fire-and-forget, don't break login)
        try:
            if user.bot_channels:
                asyncio.create_task(
                    openclaw_service.ensure_bot_running_fire_and_forget(user.id, user.bot_channels)
                )
        except Exception as e:
            logger.warning("Failed to schedule OpenClaw auto-start on login: %s", e)

        return LoginResponse(token=Auth.create_access_token(user.id), email=user.email)


@router.post("/login-by-clerk", name="login by Clerk JWT")
async def by_clerk(
    token: str,
    type: str = "login",
    session: Session = Depends(session),
):
    """
    Exchange a Clerk session JWT for a local HS256 token.
    Verifies the Clerk JWT, finds or creates the user, and returns a local token.
    """
    from app.component.clerk_auth import ClerkAuth, is_clerk_enabled

    if not is_clerk_enabled():
        logger.warning("Clerk login attempted but Clerk is not configured")
        raise HTTPException(500, detail="Clerk authentication is not configured")

    if not token or not token.strip():
        raise HTTPException(400, detail="Clerk token is required")

    try:
        clerk_user = await ClerkAuth.verify_token(token)
    except UserException as e:
        logger.warning(
            "Clerk token verification failed",
            extra={"type": type, "code": e.code, "error": e.description},
        )
        if e.code == code.config_error:
            raise HTTPException(500, detail=e.description)
        if e.code in (code.token_need, code.token_expired, code.token_invalid, code.token_blocked):
            raise HTTPException(401, detail=e.description)
        raise HTTPException(400, detail=e.description)
    except Exception as e:
        logger.error("Unexpected Clerk token verification error", extra={"type": type, "error": str(e)}, exc_info=True)
        raise HTTPException(401, detail="Invalid Clerk token")

    if not clerk_user.email:
        logger.warning("Clerk user has no email", extra={"user_id": clerk_user.user_id})
        raise HTTPException(
            400,
            detail="Clerk account has no email address. Please add a verified primary email in Clerk and try again.",
        )

    try:
        user = User.by(User.email == clerk_user.email, s=session).one_or_none()
    except Exception as e:
        logger.error(
            "Clerk auth user lookup failed",
            extra={"email": clerk_user.email, "clerk_user_id": clerk_user.user_id, "error": str(e)},
            exc_info=True,
        )
        raise HTTPException(500, detail=f"Failed to query user data: {e.__class__.__name__}: {str(e)}")

    if not user:
        if type not in ("signup", "login"):
            logger.warning(
                "Clerk auth: user not found and type is not signup/login",
                extra={"clerk_user_id": clerk_user.user_id, "type": type},
            )
            raise UserException(code.error, "User not found")

        with session as s:
            try:
                user = User(
                    username=clerk_user.username,
                    nickname=(
                        f"{clerk_user.first_name or ''} {clerk_user.last_name or ''}".strip()
                        or (clerk_user.username or "")
                    ),
                    email=clerk_user.email,
                    avatar=clerk_user.image_url or "",
                )
                s.add(user)
                s.commit()
                s.refresh(user)
                logger.info(
                    "New user registered via Clerk",
                    extra={
                        "user_id": user.id,
                        "email": user.email,
                        "clerk_user_id": clerk_user.user_id,
                    },
                )
                return LoginResponse(
                    token=Auth.create_access_token(user.id),
                    email=user.email,
                    username=user.username,
                    user_id=user.id,
                )
            except Exception as e:
                s.rollback()
                logger.error(
                    "Clerk auth registration failed",
                    extra={"clerk_user_id": clerk_user.user_id, "error": str(e)},
                    exc_info=True,
                )
                raise HTTPException(500, detail="Failed to register user")
    else:
        if user.status == Status.Block:
            logger.warning(
                "Blocked user Clerk login attempt",
                extra={"user_id": user.id, "clerk_user_id": clerk_user.user_id},
            )
            raise UserException(code.error, "Your account has been blocked.")

        logger.info(
            "User login via Clerk successful",
            extra={"user_id": user.id, "email": user.email, "clerk_user_id": clerk_user.user_id},
        )

        # Auto-start OpenClaw if user has channels configured (fire-and-forget, don't break login)
        try:
            if user.bot_channels:
                asyncio.create_task(
                    openclaw_service.ensure_bot_running_fire_and_forget(user.id, user.bot_channels)
                )
        except Exception as e:
            logger.warning("Failed to schedule OpenClaw auto-start on login: %s", e)

        return LoginResponse(
            token=Auth.create_access_token(user.id),
            email=user.email,
            username=user.username,
            user_id=user.id,
        )


@router.post("/register", name="register by email/password")
async def register(data: RegisterIn, session: Session = Depends(session)):
    email = data.email

    if User.by(User.email == email, s=session).one_or_none():
        logger.warning("Registration failed: email already exists", extra={"email": email})
        raise UserException(code.error, _("Email already registered"))

    with session as s:
        try:
            user = User(
                email=email,
                password=data.password,
            )
            s.add(user)
            s.commit()
            s.refresh(user)
            logger.info(
                "User registered successfully",
                extra={"user_id": user.id, "email": email},
            )
        except Exception as e:
            s.rollback()
            logger.error(
                "User registration failed",
                extra={"email": email, "error": str(e)},
                exc_info=True,
            )
            raise UserException(code.error, _("Failed to register"))

    return {"status": "success"}
