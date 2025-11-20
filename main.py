from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from auth import admin_create_user, initiate_auth
from utils import get_token_from_cookie, require_admin, get_token_from_header, IDTOKEN_COOKIE_NAME
from config import APP_BASE_URL

app = FastAPI(title="Cognito Admin Create User")


class CreateUserRequest(BaseModel):
    email: EmailStr
    role: str  # e.g. "admin" or "user"


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/create-user")
async def create_user(req: CreateUserRequest, _admin=Depends(require_admin)):
    # Create the user in Cognito with admin_create_user
    payload, pool_id, client_id = _admin
    result = admin_create_user(pool_id, req.email, req.role)
    if not result.get("ok"):
        return JSONResponse(status_code=400, content={"detail": result.get("error")})

    # In production you might want to send an email to the user with next steps.
    return {"message": "User created in Cognito. Temporary password set (user must change password on first login)."}

@app.post("/login")
async def login(req: LoginRequest, request: Request):
    try:
        resp = initiate_auth(req.username, req.password)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Extract IdToken from Cognito response and set it as a cookie
    id_token = resp.get("AuthenticationResult", {}).get("IdToken")
    if id_token:
        response = JSONResponse(content=resp)
        # Set secure cookie (HttpOnly=True prevents JS access, Secure=True for HTTPS only in prod)
        response.set_cookie(
            key=IDTOKEN_COOKIE_NAME,
            value=id_token,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax",
            max_age=3600  # 1 hour expiry
        )
        return response
    
    return resp


@app.get("/whoami")
async def whoami(request: Request):
    token = get_token_from_header(request)
    if not token:
        token = get_token_from_cookie(request)
    
    if not token:
        raise HTTPException(status_code=401, detail="Missing IdToken. Please sign in first using /login")
    # decode without verification for quick info (not secure)
    from jose import jwt
    claims = jwt.get_unverified_claims(token)
    return claims