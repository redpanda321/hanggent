"""Authentication middleware for backend API.

Provides JWT token validation middleware for protecting API endpoints
in web mode. In Electron mode, authentication can be bypassed for
local-only operation.
"""

import jwt
from datetime import datetime
from typing import Optional, Callable

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import AppMode, get_config
from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("auth_middleware")


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware for JWT authentication.
    
    Validates JWT tokens on incoming requests and attaches user info
    to the request state. Supports configurable bypass for certain
    paths and modes.
    """

    # Paths that don't require authentication
    PUBLIC_PATHS = {
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    # Path prefixes that don't require authentication
    PUBLIC_PREFIXES = (
        "/docs",
        "/redoc",
    )

    def __init__(
        self,
        app,
        secret_key: str,
        algorithm: str = "HS256",
        require_auth: bool = True,
        bypass_in_electron: bool = True,
    ):
        """Initialize auth middleware.
        
        Args:
            app: FastAPI application
            secret_key: JWT secret key
            algorithm: JWT algorithm
            require_auth: Whether to require authentication
            bypass_in_electron: Skip auth in Electron mode
        """
        super().__init__(app)
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.require_auth = require_auth
        self.bypass_in_electron = bypass_in_electron

    def _is_public_path(self, path: str) -> bool:
        """Check if path doesn't require authentication."""
        # Allow health checks under a configurable prefix (e.g. /api/backend/health)
        if path.endswith("/health"):
            return True
        if path in self.PUBLIC_PATHS:
            return True
        if any(path.startswith(prefix) for prefix in self.PUBLIC_PREFIXES):
            return True
        return False

    def _extract_token(self, request: Request) -> Optional[str]:
        """Extract JWT token from Authorization header."""
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None
        
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        
        return parts[1]

    def _validate_token(self, token: str) -> dict:
        """Validate JWT token and return payload.
        
        Args:
            token: JWT token string
            
        Returns:
            Token payload dict
            
        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Check expiration
            exp = payload.get("exp")
            if exp and exp < int(datetime.now().timestamp()):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    async def dispatch(self, request: Request, call_next: Callable):
        """Process request through auth middleware."""
        path = request.url.path
        
        # Skip auth for public paths
        if self._is_public_path(path):
            return await call_next(request)
        
        # Skip auth in Electron mode if configured
        config = get_config()
        if self.bypass_in_electron and config.is_electron_mode:
            logger.debug(f"Skipping auth in Electron mode for: {path}")
            return await call_next(request)
        
        # Skip auth if not required
        if not self.require_auth:
            return await call_next(request)
        
        # Extract and validate token
        token = self._extract_token(request)
        if not token:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authentication required"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        try:
            payload = self._validate_token(token)
            
            # Attach user info to request state
            request.state.user_id = payload.get("id")
            request.state.token_type = payload.get("type", "access")
            request.state.authenticated = True
            
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail},
                headers=e.headers,
            )
        
        return await call_next(request)


def get_current_user_id(request: Request) -> Optional[int]:
    """Get current user ID from request state.
    
    Args:
        request: FastAPI request
        
    Returns:
        User ID or None if not authenticated
    """
    return getattr(request.state, "user_id", None)


def require_auth(request: Request) -> int:
    """Dependency to require authentication.
    
    Args:
        request: FastAPI request
        
    Returns:
        User ID
        
    Raises:
        HTTPException: If not authenticated
    """
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user_id


def setup_auth_middleware(app, config=None):
    """Setup authentication middleware on FastAPI app.
    
    Args:
        app: FastAPI application
        config: Optional AppConfig (uses global if not provided)
    """
    if config is None:
        config = get_config()
    
    # Only add auth middleware in web mode or when explicitly required
    if config.is_web_mode or config.auth.require_auth:
        app.add_middleware(
            AuthMiddleware,
            secret_key=config.auth.secret_key,
            algorithm=config.auth.algorithm,
            require_auth=config.auth.require_auth,
            bypass_in_electron=config.is_electron_mode,
        )
        logger.info("Auth middleware enabled")
    else:
        logger.info("Auth middleware disabled (Electron mode)")
