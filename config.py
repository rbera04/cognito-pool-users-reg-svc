import os
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID")
COGNITO_CLIENT_SECRET = os.getenv("COGNITO_CLIENT_SECRET") or None

APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
VERIFY_JWT_SIGNATURE = os.getenv("VERIFY_JWT_SIGNATURE", "false").lower() in ("1","true","yes")
JWKS_CACHE_TTL = int(os.getenv("JWKS_CACHE_TTL", "300"))

# Cognito JWKS URL pattern
COGNITO_JWKS_URL = f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"

# Comma-separated allowed roles for create-user validation. Defaults to 'admin,user'
ALLOWED_ROLES = [r.strip() for r in os.getenv("ALLOWED_ROLES", "admin,user").split(",") if r.strip()]