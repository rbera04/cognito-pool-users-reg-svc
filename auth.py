"""
Encapsulates Cognito operations used by the FastAPI app.
"""
import boto3
import hmac
import hashlib
import base64
from botocore.exceptions import ClientError
from config import AWS_REGION, COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID, COGNITO_CLIENT_SECRET

cognito = boto3.client("cognito-idp", region_name=AWS_REGION)


def compute_secret_hash(username: str, client_id: str, client_secret: str) -> str:
    """Compute SECRET_HASH for Cognito authentication with client secret."""
    if not client_secret:
        return None
    
    message = bytes(username + client_id, 'utf-8')
    secret = bytes(client_secret, 'utf-8')
    dig = hmac.new(secret, msg=message, digestmod=hashlib.sha256).digest()
    return base64.b64encode(dig).decode()


def admin_create_user(pool_id: str, email: str, role: str, password: str = None, extra_attributes: dict = None) -> dict:
    """Create a user in Cognito with custom:role attribute and optional extra attributes.
    `extra_attributes` should be a mapping of attribute name -> value (e.g. {"custom:roleName":"Editor"}).
    Returns AWS response dict and fetched user info under `user` key when available.
    """
    if password is None:
        password = "TempPass@123"  # choose a secure generator in prod

    # Build base attributes and merge any extras (extras override defaults when names conflict)
    user_attrs = {
        "email": email,
        "email_verified": "true",
        # "custom:role": role,
    }

    if extra_attributes:
        for k, v in extra_attributes.items():
            if v is None:
                continue
            user_attrs[str(k)] = str(v)

    attributes_list = [{"Name": k, "Value": v} for k, v in user_attrs.items()]

    try:
        resp = cognito.admin_create_user(
            UserPoolId=pool_id,
            Username=email,
            UserAttributes=attributes_list,
            MessageAction="SUPPRESS"  # suppress sending Cognito invite email
        )

        # Set permanent password
        cognito.admin_set_user_password(
            UserPoolId=pool_id,
            Username=email,
            Password=password,
            Permanent=True
        )

        # Ensure attributes are applied (custom attributes must exist in pool schema)
        try:
            if attributes_list:
                cognito.admin_update_user_attributes(
                    UserPoolId=pool_id,
                    Username=email,
                    UserAttributes=attributes_list
                )
        except Exception:
            pass

        # Fetch user to return effective attributes for verification
        try:
            get_resp = cognito.admin_get_user(UserPoolId=pool_id, Username=email)
        except Exception:
            get_resp = None

        return {"ok": True, "detail": resp, "user": get_resp}
    except cognito.exceptions.UsernameExistsException:
        return {"ok": False, "error": "User already exists"}
    except ClientError as e:
        return {"ok": False, "error": e.response.get("Error", {}).get("Message", str(e))}


def initiate_auth(username: str, password: str) -> dict:
    """Perform USER_PASSWORD_AUTH to get tokens. Handles client with or without secret."""
    params = {"USERNAME": username, "PASSWORD": password}
    
    # Add SECRET_HASH if client secret is configured
    secret_hash = compute_secret_hash(username, COGNITO_CLIENT_ID, COGNITO_CLIENT_SECRET)
    if secret_hash:
        params["SECRET_HASH"] = secret_hash
    
    try:
        resp = cognito.initiate_auth(
            ClientId=COGNITO_CLIENT_ID,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters=params
        )
        return resp
    except Exception as e:
        raise