"""
Bot WebSocket Controller — bidirectional WebSocket proxy
from authenticated web users to their OpenClaw gateway sub-process
via the supervisor.

Route:
  WS /bot/ws — proxy WebSocket to user's OpenClaw gateway
"""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.component.auth import Auth
from app.service import openclaw_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Bot"])


async def _authenticate_ws(ws: WebSocket) -> int | None:
    """
    Authenticate a WebSocket connection using a Clerk/JWT token.
    Token is passed as query param ?token=... or in the first message.
    Returns user_id or None.
    """
    token = ws.query_params.get("token")
    if not token:
        # Try Sec-WebSocket-Protocol header (some clients use this)
        token = ws.headers.get("sec-websocket-protocol")

    if not token:
        return None

    try:
        auth = Auth.decode(token)
        if auth and not auth.is_expired:
            return auth.id
    except Exception:
        pass

    # Try Clerk verification
    try:
        from app.component.clerk_auth import ClerkAuth
        from app.component.environment import is_clerk_enabled

        if is_clerk_enabled():
            clerk = ClerkAuth()
            payload = clerk.verify_token(token)
            if payload:
                # Look up user by email or Clerk sub
                from app.component.database import session_make
                from app.model.user.user import User

                s = session_make()
                try:
                    email = payload.get("email")
                    if email:
                        user = User.by(s).filter(User.email == email).first()
                        if user:
                            return user.id
                finally:
                    s.close()
    except Exception as e:
        logger.debug(f"Clerk WS auth failed: {e}")

    return None


@router.websocket("/bot/ws")
async def bot_websocket(ws: WebSocket):
    """
    Bidirectional WebSocket proxy to the user's OpenClaw gateway.
    Authenticates via token query param, then connects to the supervisor's
    WS proxy endpoint and relays messages in both directions.
    """
    await ws.accept()

    # Authenticate
    user_id = await _authenticate_ws(ws)
    if user_id is None:
        await ws.close(code=4001, reason="Authentication required")
        return

    # Get supervisor WS URL for this user
    supervisor_ws_url = openclaw_service.get_supervisor_ws_url(user_id)

    # Add supervisor auth token
    import os

    supervisor_token = os.getenv("OPENCLAW_SUPERVISOR_TOKEN", "")
    headers = {}
    if supervisor_token:
        headers["Authorization"] = f"Bearer {supervisor_token}"

    try:
        import websockets

        async with websockets.connect(
            supervisor_ws_url,
            additional_headers=headers,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        ) as upstream:
            # Bidirectional relay
            async def client_to_upstream():
                try:
                    while True:
                        data = await ws.receive_text()
                        await upstream.send(data)
                except WebSocketDisconnect:
                    pass
                except Exception as e:
                    logger.debug(f"[ws-proxy:{user_id}] client→upstream error: {e}")

            async def upstream_to_client():
                try:
                    async for message in upstream:
                        if isinstance(message, str):
                            await ws.send_text(message)
                        elif isinstance(message, bytes):
                            await ws.send_bytes(message)
                except Exception as e:
                    logger.debug(f"[ws-proxy:{user_id}] upstream→client error: {e}")

            # Run both directions concurrently
            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(client_to_upstream()),
                    asyncio.create_task(upstream_to_client()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel the other direction
            for task in pending:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

    except Exception as e:
        logger.error(f"[ws-proxy:{user_id}] connection error: {e}")
        try:
            await ws.close(code=4002, reason=f"Upstream connection failed: {str(e)}")
        except Exception:
            pass
