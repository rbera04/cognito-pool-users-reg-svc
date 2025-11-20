# Cognito Admin Create User - FastAPI

Minimal example to create Cognito users from FastAPI endpoints protected by Cognito JWTs. Uses Cognito custom attribute `custom:role` to implement admin-only creation.

### Flow
1. Create one initial admin user manually in Cognito (set `custom:role = admin`).
2. Admin logs in (via Cognito hosted UI or via `/login` if you have CLIENT_SECRET disabled) and obtains an **id_token** or **access_token**.
3. Admin calls `/create-user` with `Authorization: Bearer <id_token>`.
4. FastAPI validates the token and checks `custom:role` claim; if `admin`, it calls Cognito `admin_create_user` to create a new user with specified role.

### Features
- No external DB
- Role stored in Cognito custom attribute `custom:role`
- Token decoding (signature verification optional; instructions included)

### Files
- `main.py` - FastAPI routes
- `auth.py` - Cognito interaction helpers
- `config.py` - Env configuration
- `jwk_utils.py` - JWKS fetcher and (optional) token verification tools
- `utils.py` - small helpers

### Setup
1. Copy `.env.example` to `.env` and fill values.
2. Install dependencies: `pip install -r requirements.txt`
3. Run: `uvicorn main:app --reload --host 0.0.0.0 --port 8000`

### Important Security Notes
- In production, you **must** verify the JWT signatures using Cognito's JWKS (see `jwk_utils.py`) and validate the token audience.
- Use HTTPS for all endpoints.
- Ensure the `custom:role` attribute is only writable by admins (control via IAM / admin APIs).