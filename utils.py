import logging
import boto3
from fastapi import HTTPException, Request
from typing import Optional, Tuple, Dict, Any
from jwk_utils import verify_cognito_token
from config import COGNITO_CLIENT_ID, AWS_REGION, COGNITO_USER_POOL_ID

logger = logging.getLogger(__name__)

IDTOKEN_COOKIE_NAME = "id_token"

# Centralized boto3 client to avoid multiple initializations
_cognito_client = None


def get_cognito_client():
    """Get or create Cognito boto3 client (singleton)."""
    global _cognito_client
    if _cognito_client is None:
        _cognito_client = boto3.client("cognito-idp", region_name=AWS_REGION)
    return _cognito_client


def get_token_from_header(request: Request) -> Optional[str]:
    """Extract Bearer token from Authorization header."""
    auth = request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return None
    return auth.split(" ", 1)[1].strip()


def get_token_from_cookie(request: Request) -> Optional[str]:
    """Retrieve IdToken from cookies."""
    token = request.cookies.get(IDTOKEN_COOKIE_NAME)
    if token:
        logger.info("Retrieved IdToken from cookie")
    return token


def get_token(request: Request) -> Optional[str]:
    """Get token from header or cookie (with fallback)."""
    return get_token_from_header(request) or get_token_from_cookie(request)


def extract_cognito_context(request: Request) -> Tuple[str, str]:
    """Extract pool_id and client_id from headers, with config fallback."""
    pool_id = request.headers.get("X-Cognito-Pool-Id") or COGNITO_USER_POOL_ID
    client_id = request.headers.get("X-Cognito-Client-Id") or COGNITO_CLIENT_ID
    return pool_id, client_id


async def require_admin(request: Request) -> Tuple[Dict[str, Any], str, str]:
    """Verify admin access. Returns (token_payload, pool_id, client_id)."""
    token = get_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing IdToken. Please sign in first using /login")
    
    pool_id, client_id = extract_cognito_context(request)
    logger.info(f"Verifying token for pool_id={pool_id}, client_id={client_id}")

    try:
        payload = verify_cognito_token(token, audience=client_id, pool_id=pool_id)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

    # Cognito places custom attributes in tokens as 'custom:role'
    role = payload.get("custom:role") or payload.get("role")
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")

    return payload, pool_id, client_id
