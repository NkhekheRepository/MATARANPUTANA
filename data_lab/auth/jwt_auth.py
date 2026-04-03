#!/usr/bin/env python3
"""
JWT Authentication Module
Provides JWT-based authentication for API access
"""

import os
import sys
import time
import logging
import hashlib
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps

sys.path.insert(0, '/home/ubuntu/financial_orchestrator')

logger = logging.getLogger('JWTAuth')

try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    logger.warning("PyJWT not available")


@dataclass
class TokenPayload:
    """JWT token payload"""
    sub: str
    exp: int
    iat: int
    iss: str = "quant_lab"
    aud: str = "data_lab_api"
    permissions: List[str] = None
    
    def __post_init__(self):
        if self.permissions is None:
            self.permissions = []


class JWTAuthenticator:
    """
    JWT-based authentication for the data lab API.
    """
    
    def __init__(
        self,
        secret_key: Optional[str] = None,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 60,
        issuer: str = "quant_lab",
        audience: str = "data_lab_api"
    ):
        self.secret_key = secret_key or os.getenv("JWT_SECRET_KEY", "change_this_secret_key")
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.issuer = issuer
        self.audience = audience
        
        self._token_blacklist = set()
        
        if not JWT_AVAILABLE:
            logger.warning("JWT library not available, authentication disabled")
    
    def create_token(
        self,
        user_id: str,
        permissions: List[str] = None
    ) -> Optional[str]:
        """Create a new JWT access token"""
        if not JWT_AVAILABLE:
            return "dummy_token_for_testing"
            
        now = int(time.time())
        
        payload = {
            'sub': user_id,
            'iat': now,
            'exp': now + (self.access_token_expire_minutes * 60),
            'iss': self.issuer,
            'aud': self.audience,
            'permissions': permissions or []
        }
        
        try:
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            return token
        except Exception as e:
            logger.error(f"Failed to create token: {e}")
            return None
    
    def verify_token(self, token: str) -> Optional[TokenPayload]:
        """Verify and decode a JWT token"""
        if not JWT_AVAILABLE:
            return TokenPayload(sub="test_user", exp=int(time.time()) + 3600, iat=int(time.time()))
            
        if token in self._token_blacklist:
            return None
            
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                issuer=self.issuer,
                audience=self.audience
            )
            
            return TokenPayload(
                sub=payload.get('sub'),
                exp=payload.get('exp'),
                iat=payload.get('iat'),
                iss=payload.get('iss'),
                aud=payload.get('aud'),
                permissions=payload.get('permissions', [])
            )
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidIssuerError:
            logger.warning("Invalid token issuer")
            return None
        except jwt.InvalidAudienceError:
            logger.warning("Invalid token audience")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
    
    def revoke_token(self, token: str):
        """Revoke a token (add to blacklist)"""
        self._token_blacklist.add(token)
    
    def has_permission(self, token_payload: TokenPayload, permission: str) -> bool:
        """Check if token has specific permission"""
        if not token_payload:
            return False
        return permission in (token_payload.permissions or [])
    
    def get_user_permissions(self, token_payload: TokenPayload) -> List[str]:
        """Get list of permissions for user"""
        if not token_payload:
            return []
        return token_payload.permissions or []


def require_auth(authenticator: JWTAuthenticator, required_permission: str = None):
    """
    Decorator to require authentication for a function.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            token = kwargs.get('token') or (args[0] if args else None)
            
            if not token:
                return {'error': 'Authentication required', 'code': 401}
            
            payload = authenticator.verify_token(token)
            
            if not payload:
                return {'error': 'Invalid or expired token', 'code': 401}
            
            if required_permission and not authenticator.has_permission(payload, required_permission):
                return {'error': 'Insufficient permissions', 'code': 403}
            
            kwargs['auth_user'] = payload.sub
            kwargs['auth_payload'] = payload
            
            return func(*args, **kwargs)
            
        return wrapper
    return decorator


class APIRateLimiter:
    """
    Simple rate limiter for API endpoints.
    """
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_size: int = 10
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_size = burst_size
        
        self._request_history: Dict[str, List[float]] = {}
        self._lock = __import__('threading').Lock()
    
    def check_rate_limit(self, client_id: str) -> Dict[str, Any]:
        """Check if request is within rate limit"""
        now = time.time()
        
        with self._lock:
            if client_id not in self._request_history:
                self._request_history[client_id] = []
            
            history = self._request_history[client_id]
            
            recent_minute = [t for t in history if now - t < 60]
            recent_hour = [t for t in history if now - t < 3600]
            
            remaining_minute = max(0, self.requests_per_minute - len(recent_minute))
            remaining_hour = max(0, self.requests_per_hour - len(recent_hour))
            
            if len(recent_minute) >= self.requests_per_minute:
                return {
                    'allowed': False,
                    'reason': 'Rate limit exceeded (per minute)',
                    'remaining': 0,
                    'reset_in': 60 - (now - min(recent_minute)) if recent_minute else 60
                }
            
            if len(recent_hour) >= self.requests_per_hour:
                return {
                    'allowed': False,
                    'reason': 'Rate limit exceeded (per hour)',
                    'remaining': 0,
                    'reset_in': 3600 - (now - min(recent_hour)) if recent_hour else 3600
                }
            
            history.append(now)
            history[:] = [t for t in history if now - t < 3600]
            
            return {
                'allowed': True,
                'remaining': remaining_minute,
                'reset_in': 60
            }


def get_authenticator() -> JWTAuthenticator:
    """Get singleton authenticator instance"""
    return JWTAuthenticator()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    auth = JWTAuthenticator()
    
    token = auth.create_token(
        user_id="test_user",
        permissions=["read:market_data", "write:internal_queue"]
    )
    
    print(f"Created token: {token[:50]}...")
    
    payload = auth.verify_token(token)
    
    if payload:
        print(f"Token valid for user: {payload.sub}")
        print(f"Permissions: {payload.permissions}")
        print(f"Has read:market_data: {auth.has_permission(payload, 'read:market_data')}")
        print(f"Has admin: {auth.has_permission(payload, 'admin')}")
    
    limiter = APIRateLimiter(requests_per_minute=10)
    
    for i in range(12):
        result = limiter.check_rate_limit("test_client")
        print(f"Request {i+1}: {result['allowed']}, remaining: {result.get('remaining', 'N/A')}")
