from fastapi import FastAPI, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from auth import admin_create_user, initiate_auth
from utils import require_admin, get_token_from_header
from config import APP_BASE_URL
from fastapi.responses import JSONResponse

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
def login(req: LoginRequest):
    try:
        resp = initiate_auth(req.username, req.password)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return resp


@app.get("/whoami")
async def whoami(request: Request):
    token = get_token_from_header(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    # decode without verification for quick info (not secure)
    from jose import jwt
    claims = jwt.get_unverified_claims(token)
    return claims