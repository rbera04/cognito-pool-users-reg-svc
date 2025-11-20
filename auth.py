"""
Encapsulates Cognito operations used by the FastAPI app.
"""
import boto3
from botocore.exceptions import ClientError
from config import AWS_REGION, COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID

cognito = boto3.client("cognito-idp", region_name=AWS_REGION)


def admin_create_user(pool_id: str, email: str, role: str, temporary_password: str = None) -> dict:
    """Create a user in Cognito with custom:role attribute. Returns AWS response dict."""
    if temporary_password is None:
        temporary_password = "TempPass@123"  # choose a secure generator in prod

    try:
        resp = cognito.admin_create_user(
            UserPoolId=pool_id,
            Username=email,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
                {"Name": "custom:role", "Value": role},
            ],
            MessageAction="SUPPRESS"  # suppress sending Cognito invite email
        )

        # Set temporary password and force password reset
        cognito.admin_set_user_password(
            UserPoolId=pool_id,
            Username=email,
            Password=temporary_password,
            Permanent=False
        )

        return {"ok": True, "detail": resp}
    except cognito.exceptions.UsernameExistsException:
        return {"ok": False, "error": "User already exists"}
    except ClientError as e:
        return {"ok": False, "error": e.response.get("Error", {}).get("Message", str(e))}


def initiate_auth(username: str, password: str) -> dict:
    """Perform USER_PASSWORD_AUTH to get tokens. Requires client without secret or SRP flow.
    Note: If CLIENT_SECRET is configured you'll need to compute SECRET_HASH.
    """
    params = {"USERNAME": username, "PASSWORD": password}
    try:
        resp = boto3.client("cognito-idp", region_name=AWS_REGION).initiate_auth(
            ClientId=COGNITO_CLIENT_ID,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters=params
        )
        return resp
    except Exception as e:
        raise