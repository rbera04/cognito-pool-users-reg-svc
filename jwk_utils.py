"""
Utilities to fetch Cognito JWKS and verify tokens. Signature verification is optional and controlled via config.VERIFY_JWT_SIGNATURE.

This file uses `python-jose` for JWT handling and `requests` to fetch JWKS.

Important: In production enable VERIFY_JWT_SIGNATURE=True and ensure network access to Cognito JWKS URL.
"""
from jose import jwt
from jose.utils import base64url_decode
import requests
import time
from typing import Dict, Any
from config import COGNITO_JWKS_URL, JWKS_CACHE_TTL, VERIFY_JWT_SIGNATURE, COGNITO_CLIENT_ID

_jwks_cache: Dict[str, Any] = {"keys": [], "fetched_at": 0}


def _fetch_jwks() -> Dict[str, Any]:
    now = int(time.time())
    if _jwks_cache["keys"] and now - _jwks_cache["fetched_at"] < JWKS_CACHE_TTL:
        return _jwks_cache

    resp = requests.get(COGNITO_JWKS_URL, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    _jwks_cache["keys"] = data.get("keys", [])
    _jwks_cache["fetched_at"] = now
    return _jwks_cache


def get_jwk_for_kid(kid: str) -> Dict[str, Any]:
    jwks = _fetch_jwks()
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    raise KeyError("No matching JWK for kid")


def verify_cognito_token(token: str, audience: str = None) -> Dict[str, Any]:
    """
    Verifies a Cognito JWT token and returns the decoded payload.

    If VERIFY_JWT_SIGNATURE is False this will decode without signature verification (NOT FOR PROD).
    If VERIFY_JWT_SIGNATURE is True it will fetch JWKS and validate signature and claims.
    """
    if not VERIFY_JWT_SIGNATURE:
        # WARNING: no signature verification
        payload = jwt.get_unverified_claims(token)
        return payload

    # With signature verification
    headers = jwt.get_unverified_header(token)
    kid = headers.get("kid")
    if not kid:
        raise ValueError("Token header missing kid")

    jwk = get_jwk_for_kid(kid)

    # construct public key from jwk
    # python-jose's jwt.decode supports passing jwk directly as the key
    # but it expects proper key format; pass the jwk JSON

    try:
        decoded = jwt.decode(token, jwk, algorithms=[jwk.get("alg", "RS256")], audience=audience)
    except Exception as e:
        raise

    return decoded