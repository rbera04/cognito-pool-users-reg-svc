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
from config import COGNITO_JWKS_URL, JWKS_CACHE_TTL, VERIFY_JWT_SIGNATURE, COGNITO_CLIENT_ID, AWS_REGION

# cache keyed by jwks_url to support multiple pools
_jwks_cache: Dict[str, Any] = {}


def _fetch_jwks(jwks_url: str) -> Dict[str, Any]:
    now = int(time.time())
    entry = _jwks_cache.get(jwks_url)
    if entry and entry.get("keys") and now - entry.get("fetched_at", 0) < JWKS_CACHE_TTL:
        return entry

    resp = requests.get(jwks_url, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    entry = {"keys": data.get("keys", []), "fetched_at": now}
    _jwks_cache[jwks_url] = entry
    return entry


def get_jwk_for_kid(kid: str, jwks_url: str) -> Dict[str, Any]:
    jwks = _fetch_jwks(jwks_url)
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    raise KeyError("No matching JWK for kid")


def verify_cognito_token(token: str, audience: str = None, pool_id: str = None) -> Dict[str, Any]:
    """
    Verifies a Cognito JWT token and returns the decoded payload.

    If VERIFY_JWT_SIGNATURE is False this will decode without signature verification (NOT FOR PROD).
    If VERIFY_JWT_SIGNATURE is True it will fetch JWKS and validate signature and claims.
    """
    if not VERIFY_JWT_SIGNATURE:
        # WARNING: no signature verification
        payload = jwt.get_unverified_claims(token)
        # even when skipping signature verification, enforce token expiration
        exp = payload.get("exp")
        if exp is not None:
            now = int(time.time())
            try:
                exp_int = int(exp)
            except Exception:
                raise ValueError("Invalid exp claim in token")
            if exp_int < now:
                raise ValueError("Token expired")
        return payload

    # With signature verification
    headers = jwt.get_unverified_header(token)
    kid = headers.get("kid")
    if not kid:
        raise ValueError("Token header missing kid")

    # determine jwks url: use provided pool_id if present to support multi-pool headers
    if pool_id:
        jwks_url = f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{pool_id}/.well-known/jwks.json"
    else:
        jwks_url = COGNITO_JWKS_URL

    jwk = get_jwk_for_kid(kid, jwks_url)

    # construct public key from jwk
    # python-jose's jwt.decode supports passing jwk directly as the key
    # but it expects proper key format; pass the jwk JSON

    try:
        decoded = jwt.decode(token, jwk, algorithms=[jwk.get("alg", "RS256")], audience=audience)
    except Exception as e:
        raise

    return decoded