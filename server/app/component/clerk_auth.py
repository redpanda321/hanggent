"""
Clerk Authentication Verification.

This module provides JWT verification for Clerk authentication tokens
using Clerk's JWKS endpoint for public key retrieval.
"""

import asyncio
import logging
import httpx
import jwt
from typing import Optional
from pydantic import BaseModel
from app.component.environment import env
from app.exception.exception import UserException
from app.component import code

logger = logging.getLogger(__name__)


class ClerkUserInfo(BaseModel):
    """Clerk user information extracted from JWT token."""
    user_id: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    image_url: Optional[str] = None


class ClerkAuth:
    """
    Clerk authentication verification using JWKS.
    
    Verifies Clerk session tokens by fetching public keys from Clerk's
    JWKS endpoint and validating JWT signatures.
    """
    _signing_key_cache = {}
    _jwks_client = None

    @staticmethod
    def _get_clerk_domain() -> str:
        """Get Clerk domain from environment or derive from publishable key."""
        # Try explicit domain first
        clerk_domain = env("CLERK_DOMAIN")
        if clerk_domain:
            return clerk_domain.rstrip("/")
        
        # Derive from publishable key (pk_test_xxx or pk_live_xxx)
        # The frontend instance ID is encoded in the publishable key
        # Format: https://<instance>.clerk.accounts.dev for dev
        # Format: https://clerk.<domain> for production
        publishable_key = env("CLERK_PUBLISHABLE_KEY") or env("VITE_CLERK_PUBLISHABLE_KEY")
        if publishable_key:
            # For development keys (pk_test_), use the clerk dev domain
            if publishable_key.startswith("pk_test_"):
                # Extract instance ID from key - it's base64 encoded
                import base64
                try:
                    # Remove prefix and decode
                    encoded = publishable_key.replace("pk_test_", "").replace("pk_live_", "")
                    # Add padding if needed
                    padding = 4 - len(encoded) % 4
                    if padding != 4:
                        encoded += "=" * padding
                    decoded = base64.b64decode(encoded).decode("utf-8")
                    # The decoded value contains the instance ID
                    # Format is usually: <instance_id>$
                    instance_id = decoded.split("$")[0] if "$" in decoded else decoded
                    return f"https://{instance_id}.clerk.accounts.dev"
                except Exception:
                    pass
        
        raise UserException(code.config_error, "CLERK_DOMAIN or CLERK_PUBLISHABLE_KEY not configured")

    @staticmethod
    def _get_jwks_url() -> str:
        """Get JWKS URL for Clerk."""
        domain = ClerkAuth._get_clerk_domain()
        return f"{domain}/.well-known/jwks.json"

    @staticmethod
    async def verify_token(token: str) -> ClerkUserInfo:
        """
        Verify a Clerk session token and extract user information.
        
        Args:
            token: The Clerk session JWT token
            
        Returns:
            ClerkUserInfo with user details
            
        Raises:
            UserException: If token is invalid or verification fails
        """
        try:
            # Get the key ID from the token header
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if not kid:
                raise UserException(code.token_invalid, "Token is missing 'kid' in header")

            # Get the signing key
            signing_key = await ClerkAuth._get_signing_key(kid)
            
            # Decode and verify the token
            # Clerk uses RS256 algorithm
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                # Clerk tokens have 'aud' claim but verification is optional
                options={"verify_aud": False}
            )
            
            # Extract user information from Clerk JWT claims
            # Clerk JWT structure: https://clerk.com/docs/backend-requests/resources/session-tokens
            user_id = payload.get("sub")
            if not user_id:
                raise UserException(code.token_invalid, "Token missing 'sub' claim")

            # Try to get email from JWT claims first (available if session
            # token customization is configured in the Clerk dashboard).
            email = payload.get("email") or payload.get("primary_email_address")
            first_name = payload.get("first_name")
            last_name = payload.get("last_name")
            username = payload.get("username")
            image_url = payload.get("image_url") or payload.get("profile_image_url")

            # Default Clerk session JWTs do NOT include user profile claims.
            # Fall back to the Clerk Backend API when email is missing.
            if not email:
                try:
                    api_user = await ClerkAuth.get_user_from_api(user_id)
                    email_addresses = api_user.get("email_addresses", [])
                    primary_email_id = api_user.get("primary_email_address_id")
                    # Pick the primary email, or fall back to the first verified one
                    for ea in email_addresses:
                        if ea.get("id") == primary_email_id:
                            email = ea.get("email_address")
                            break
                    if not email and email_addresses:
                        email = email_addresses[0].get("email_address")

                    first_name = first_name or api_user.get("first_name")
                    last_name = last_name or api_user.get("last_name")
                    username = username or api_user.get("username")
                    image_url = image_url or api_user.get("image_url") or api_user.get("profile_image_url")
                    logger.info(
                        "Fetched user details from Clerk API",
                        extra={"user_id": user_id, "email": email},
                    )
                except UserException:
                    raise
                except Exception as api_err:
                    logger.warning(
                        "Could not fetch user from Clerk API, email may be missing",
                        extra={"user_id": user_id, "error": str(api_err)},
                    )

            return ClerkUserInfo(
                user_id=user_id,
                email=email,
                first_name=first_name,
                last_name=last_name,
                username=username,
                image_url=image_url,
            )
            
        except UserException:
            raise
        except jwt.ExpiredSignatureError:
            raise UserException(code.token_expired, "Clerk token has expired")
        except jwt.InvalidTokenError as e:
            raise UserException(code.token_invalid, f"Invalid Clerk token: {str(e)}")
        except Exception as e:
            raise UserException(code.token_invalid, f"Clerk token verification failed: {str(e)}")

    @staticmethod
    async def _get_signing_key(kid: str):
        """
        Get signing key from Clerk JWKS endpoint.
        
        Args:
            kid: Key ID from JWT header
            
        Returns:
            JWT signing key
        """
        # Check cache first
        if kid in ClerkAuth._signing_key_cache:
            return ClerkAuth._signing_key_cache[kid]

        jwks_url = ClerkAuth._get_jwks_url()
        loop = asyncio.get_running_loop()
        
        # Create JWKS client if not exists
        if ClerkAuth._jwks_client is None:
            ClerkAuth._jwks_client = jwt.PyJWKClient(jwks_url)

        try:
            signing_key = await loop.run_in_executor(
                None, 
                ClerkAuth._jwks_client.get_signing_key, 
                kid
            )
            ClerkAuth._signing_key_cache[kid] = signing_key
            return signing_key
        except jwt.exceptions.PyJWKClientError as e:
            raise UserException(code.token_invalid, f"Failed to fetch Clerk signing key: {str(e)}")

    @staticmethod
    async def get_user_from_api(user_id: str) -> dict:
        """
        Fetch full user details from Clerk Backend API.
        
        This requires CLERK_SECRET_KEY to be configured.
        
        Args:
            user_id: Clerk user ID (e.g., user_xxx)
            
        Returns:
            Full user object from Clerk API
        """
        secret_key = env("CLERK_SECRET_KEY")
        if not secret_key:
            logger.error(
                "CLERK_SECRET_KEY is not configured — cannot fetch user details from Clerk API. "
                "Set CLERK_SECRET_KEY in environment/secrets, or add 'email' to Clerk session token claims."
            )
            raise UserException(
                code.config_error,
                "CLERK_SECRET_KEY not configured. Please set it in your deployment secrets "
                "or add the email claim to your Clerk session token customization.",
            )
        
        # Clerk Backend API endpoint
        url = f"https://api.clerk.com/v1/users/{user_id}"
        headers = {
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json",
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                logger.error(
                    "Clerk API returned 401 — CLERK_SECRET_KEY is invalid or does not match the Clerk instance",
                    extra={"user_id": user_id, "status": 401},
                )
                raise UserException(
                    code.config_error,
                    "Failed to authenticate with Clerk API — CLERK_SECRET_KEY is invalid. "
                    "Verify the key matches your Clerk instance in the Clerk Dashboard → API Keys.",
                )
            elif response.status_code == 403:
                logger.error(
                    "Clerk API returned 403 — CLERK_SECRET_KEY lacks permissions",
                    extra={"user_id": user_id, "status": 403},
                )
                raise UserException(
                    code.config_error,
                    "Clerk API access forbidden — CLERK_SECRET_KEY may lack required permissions.",
                )
            elif response.status_code == 404:
                raise UserException(code.user_not_found, f"Clerk user {user_id} not found")
            else:
                logger.error(
                    "Clerk API returned unexpected status",
                    extra={"user_id": user_id, "status": response.status_code, "body": response.text[:500]},
                )
                raise UserException(
                    code.token_invalid, 
                    f"Clerk API error: {response.status_code} - {response.text[:200]}"
                )


def is_clerk_enabled() -> bool:
    """Check if Clerk authentication is configured."""
    return bool(
        env("CLERK_PUBLISHABLE_KEY") or 
        env("VITE_CLERK_PUBLISHABLE_KEY") or
        env("CLERK_DOMAIN")
    )
