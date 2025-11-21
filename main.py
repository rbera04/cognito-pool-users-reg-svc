from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from typing import Optional
from auth import admin_create_user, initiate_auth, compute_secret_hash
from utils import (
    get_token, require_admin, IDTOKEN_COOKIE_NAME, 
    get_cognito_client, extract_cognito_context
)
from jwk_utils import verify_cognito_token
from config import (
    APP_BASE_URL, COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID, 
    COGNITO_CLIENT_SECRET, AWS_REGION, ALLOWED_ROLES
)

app = FastAPI(title="Cognito Admin Create User")


class CreateUserRequest(BaseModel):
    email: EmailStr
    role: str  # required for create-user; validated against ALLOWED_ROLES
    password: str  # initial password for the user
    # optional convenience fields; will be added as Cognito custom attributes
    role_name: Optional[str] = None
    role_id: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class UpdateUserRequest(BaseModel):
    username: str  # email or username of the user to update
    # optional convenience fields to update
    role_name: Optional[str] = None
    role_id: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    old_password: str  # current password
    new_password: str  # new password


@app.post("/create-user")
async def create_user(req: CreateUserRequest, _admin=Depends(require_admin)):
    """Create user with role validation and custom attributes."""
    payload, pool_id, client_id = _admin
    
    if req.role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid role. Allowed roles: {ALLOWED_ROLES}"
        )

    # Build extra attributes for custom fields
    extra_attrs = {}
    if req.role_name:
        extra_attrs["custom:roleName"] = req.role_name
    if req.role_id:
        extra_attrs["custom:roleId"] = req.role_id

    result = admin_create_user(
        pool_id, req.email, req.role, 
        password=req.password, extra_attributes=extra_attrs
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return {"message": "User created in Cognito. Permanent password set. User can now log in."}

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
    """Return decoded IdToken claims (header or cookie token)."""
    token = get_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing IdToken. Please sign in first using /login")

    pool_id, client_id = extract_cognito_context(request)

    try:
        payload = verify_cognito_token(token, audience=client_id, pool_id=pool_id)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

    return payload


@app.get("/list-users")
async def list_users(request: Request, _admin=Depends(require_admin)):
    """List all users in the Cognito pool with their attributes (admin-only)."""
    payload, pool_id, client_id = _admin
    
    try:
        cognito = get_cognito_client()
        users = []
        paginator = cognito.get_paginator('list_users')
        
        for page in paginator.paginate(UserPoolId=pool_id):
            for user in page.get('Users', []):
                user_info = {
                    "username": user.get("Username"),
                    "status": user.get("UserStatus"),
                    "created": str(user.get("UserCreateDate")),
                    "modified": str(user.get("UserLastModifiedDate")),
                    "attributes": {
                        attr["Name"]: attr["Value"] 
                        for attr in user.get("Attributes", [])
                    }
                }
                users.append(user_info)
        
        return {"total": len(users), "users": users}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching users: {str(e)}")


@app.post("/update-user")
async def update_user(req: UpdateUserRequest, request: Request, _admin=Depends(require_admin)):
    """Update user attributes (admin-only). Supports role_name and role_id."""
    payload, pool_id, client_id = _admin
    
    try:
        cognito = get_cognito_client()
        
        # Build attributes to update
        update_attrs = []
        if req.role_name:
            update_attrs.append({"Name": "custom:roleName", "Value": req.role_name})
        if req.role_id:
            update_attrs.append({"Name": "custom:roleId", "Value": req.role_id})
        
        if not update_attrs:
            raise HTTPException(status_code=400, detail="No attributes to update")
        
        # Update user attributes
        cognito.admin_update_user_attributes(
            UserPoolId=pool_id,
            Username=req.username,
            UserAttributes=update_attrs
        )
        
        # Fetch and return updated user
        user = cognito.admin_get_user(UserPoolId=pool_id, Username=req.username)
        user_info = {
            "username": user.get("Username"),
            "status": user.get("UserStatus"),
            "attributes": {
                attr["Name"]: attr["Value"] 
                for attr in user.get("UserAttributes", [])
            }
        }
        
        return {"message": "User updated successfully", "user": user_info}
    except cognito.exceptions.UserNotFoundException:
        raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating user: {str(e)}")


@app.post("/change-password")
async def change_password(req: ChangePasswordRequest, request: Request):
    """Change password for the authenticated user. Requires valid IdToken."""
    token = get_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing IdToken. Please sign in first using /login")

    pool_id, client_id = extract_cognito_context(request)

    try:
        payload = verify_cognito_token(token, audience=client_id, pool_id=pool_id)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

    username = payload.get("cognito:username") or payload.get("email")
    if not username:
        raise HTTPException(status_code=400, detail="Cannot determine username from token")

    try:
        cognito = get_cognito_client()
        
        # Use initiate_auth to verify old password and get AccessToken
        auth_params = {"USERNAME": username, "PASSWORD": req.old_password}
        secret_hash = compute_secret_hash(username, COGNITO_CLIENT_ID, COGNITO_CLIENT_SECRET)
        if secret_hash:
            auth_params["SECRET_HASH"] = secret_hash
        
        try:
            auth_resp = cognito.initiate_auth(
                ClientId=COGNITO_CLIENT_ID,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters=auth_params
            )
            access_token = auth_resp.get("AuthenticationResult", {}).get("AccessToken")
            if not access_token:
                raise HTTPException(status_code=401, detail="Old password is incorrect")
        except Exception:
            raise HTTPException(status_code=401, detail="Old password is incorrect")
        
        # Change password using AccessToken
        cognito.change_password(
            AccessToken=access_token,
            PreviousPassword=req.old_password,
            ProposedPassword=req.new_password
        )
        
        return {"message": "Password changed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        if "InvalidPasswordException" in str(type(e)):
            raise HTTPException(status_code=400, detail="New password does not meet requirements")
        raise HTTPException(status_code=500, detail=f"Error changing password: {str(e)}")