import logging
from fastapi import HTTPException, Request
from typing import Optional
from jwk_utils import verify_cognito_token
from config import COGNITO_CLIENT_ID

logger = logging.getLogger(__name__)


def get_token_from_header(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization")
    if not auth:
        return None
    if not auth.lower().startswith("bearer "):
        return None
    return auth.split(" ", 1)[1].strip()

async def extract_cognito_headers(request: Request):
    pool_id = request.headers.get("X-Cognito-Pool-Id")
    client_id = request.headers.get("X-Cognito-Client-Id")

    if not pool_id or not client_id:
        raise HTTPException(
            status_code=400,
            detail="Missing required headers: X-Cognito-Pool-Id, X-Cognito-Client-Id"
        )
    logger.info(f"Extracted Cognito headers: pool_id={pool_id}, client_id={client_id}")
    return pool_id, client_id

async def require_admin(request: Request):
    pool_id, client_id = await extract_cognito_headers(request)
    token = get_token_from_header(request)

    if not token:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

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
