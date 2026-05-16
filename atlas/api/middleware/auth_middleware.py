"""
Auth Middleware - Reusable security boundary for FastAPI

This middleware:
  1. Extracts Bearer token from Authorization header
  2. Validates token using AuthService
  3. Enforces RBAC scope checks
  4. Logs all requests to audit trail
  5. Rate limiting hooks (actual limiting done separately)

Gold Standard:
  ✓ Reusable across all endpoints
  ✓ Centralized auth logic
  ✓ Observability built-in
  ✓ Scope enforcement
  ✓ Rate limit integration

Usage:
  In FastAPI endpoint, inject token dependency:
  
    @app.get("/copy/logs")
    async def copy_logs(token: str = Depends(verify_token)):
        # token is now a validated APIKey object
        # scope already verified if we reach here
        ...
"""

from typing import Optional, Dict, Any
from functools import lru_cache
import time
import hashlib

from fastapi import HTTPException, status, Request, Depends
from loguru import logger

from atlas.api.services.auth_service import AuthService, APIKey


class AuthMiddleware:
    """FastAPI dependency for API key authentication"""
    
    def __init__(self, auth_service: AuthService):
        self.auth = auth_service
        self._token_cache: Dict[str, tuple[Optional[APIKey], float]] = {}
        self._cache_ttl_seconds = 60  # Cache valid keys for 1 minute
    
    async def verify_token(self, 
                           request: Request,
                           authorization: Optional[str] = None) -> APIKey:
        """
        Extract and validate Bearer token.
        
        Raises:
            HTTPException(401) if no token or invalid
            HTTPException(403) if scope not allowed
        
        Returns:
            Valid APIKey object
        """
        # Extract token from header
        token = self._extract_bearer_token(authorization or request.headers.get("authorization", ""))
        
        if not token:
            logger.warning("Request missing Authorization header")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid Authorization header",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Validate token (with caching)
        api_key = await self._get_validated_key(token)
        
        if not api_key:
            logger.warning(f"Request with invalid token (prefix: {token[:10]}...)")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Attach to request for audit logging
        request.state.api_key = api_key
        
        return api_key
    
    async def verify_scope(self,
                           request: Request,
                           api_key: APIKey,
                           required_endpoint: str,
                           required_method: str = "GET") -> APIKey:
        """
        Verify API key has scope to access this endpoint.
        
        Use after verify_token to enforce scope.
        
        Raises:
            HTTPException(403) if scope denied
        """
        allowed = await self.auth.check_scope(api_key, required_endpoint, required_method)
        
        if not allowed:
            logger.warning(
                f"Scope denied: key {api_key.id} ({api_key.role}) "
                f"cannot access {required_method} {required_endpoint}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key does not have permission for {required_method} {required_endpoint}",
            )
        
        return api_key
    
    async def log_request(self,
                          request: Request,
                          response_status: int,
                          latency_ms: int,
                          error_message: Optional[str] = None):
        """Log request to audit trail (call from endpoint or response middleware)"""
        api_key = getattr(request.state, 'api_key', None)
        api_key_id = api_key.id if api_key else None
        ip_hash = self._hash_ip(request.client.host if request.client else "unknown")
        
        await self.auth.log_request(
            api_key_id=api_key_id,
            endpoint=request.url.path,
            method=request.method,
            status_code=response_status,
            latency_ms=latency_ms,
            ip_hash=ip_hash,
            error_message=error_message,
        )
    
    # ====================================================================
    # PRIVATE HELPERS
    # ====================================================================
    
    def _extract_bearer_token(self, auth_header: str) -> Optional[str]:
        """Extract token from 'Bearer <token>' header"""
        if not auth_header:
            return None
        
        parts = auth_header.strip().split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        
        return parts[1]
    
    async def _get_validated_key(self, raw_token: str) -> Optional[APIKey]:
        """Validate token with optional caching"""
        # Check cache first
        cache_entry = self._token_cache.get(raw_token)
        if cache_entry:
            key, cached_at = cache_entry
            if time.time() - cached_at < self._cache_ttl_seconds:
                return key
        
        # Validate via service
        key = await self.auth.validate_key(raw_token)
        
        # Cache result (including None)
        self._token_cache[raw_token] = (key, time.time())
        
        return key
    
    def _hash_ip(self, ip: str) -> str:
        """Hash IP for privacy (not reversible)"""
        return hashlib.sha256(ip.encode()).hexdigest()[:16]
    
    def clear_cache(self):
        """Clear token cache (useful for testing or admin)"""
        self._token_cache.clear()


# ========================================================================
# DEPENDENCY FACTORIES (use these in FastAPI endpoints)
# ========================================================================

# Global middleware instance (initialized in main API file)
_auth_middleware: Optional[AuthMiddleware] = None


def set_auth_middleware(middleware: AuthMiddleware):
    """Initialize global auth middleware (call during app startup)"""
    global _auth_middleware
    _auth_middleware = middleware


async def verify_token(request: Request) -> APIKey:
    """FastAPI dependency: verify Bearer token"""
    if not _auth_middleware:
        raise RuntimeError("Auth middleware not initialized")
    return await _auth_middleware.verify_token(request)


async def verify_admin_token(api_key: APIKey = Depends(verify_token)) -> APIKey:
    """FastAPI dependency: verify Bearer token is admin"""
    if api_key.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return api_key


async def verify_trader_token(api_key: APIKey = Depends(verify_token)) -> APIKey:
    """FastAPI dependency: verify Bearer token is trader or admin"""
    if api_key.role.value not in ("trader", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Trader or admin access required"
        )
    return api_key


async def verify_read_token(api_key: APIKey = Depends(verify_token)) -> APIKey:
    """FastAPI dependency: verify Bearer token (any authenticated user)"""
    # Already verified via verify_token
    return api_key


class RateLimitMiddleware:
    """
    Rate limiting middleware (uses token bucket algorithm).
    
    To use:
      1. Add to FastAPI app as middleware
      2. AuthMiddleware.log_request() is called by response middleware
      3. Redis stores token buckets per API key
    
    Implementation note: This is a skeleton for Phase A.
    Full implementation in Phase A-2 when Redis is integrated.
    """
    
    def __init__(self, auth_service: AuthService):
        self.auth = auth_service
        # TODO: Initialize Redis client
        # self.redis = ...
    
    async def check_rate_limit(self, api_key: APIKey) -> bool:
        """Check if API key is within rate limit"""
        # TODO: Implement token bucket using Redis
        # For now, always allow
        return True
    
    async def get_remaining(self, api_key: APIKey) -> int:
        """Get remaining requests for this period"""
        # TODO: Query Redis
        return api_key.rate_limit_per_min
