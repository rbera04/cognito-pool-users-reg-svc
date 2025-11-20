# Cognito Admin Create User - FastAPI

Lightweight FastAPI service to create and manage users in an AWS Cognito User Pool. This project demonstrates:

- Admin-protected `POST /create-user` endpoint that creates users with a `custom:role` attribute.
- `POST /login` endpoint that authenticates a user and sets an HTTP-only `id_token` cookie.
- JWT verification (optional; recommended in production) using Cognito JWKS.

**Quick flow**
1. Create an initial admin user in the Cognito console and set `custom:role = admin`.
2. Admin authenticates (via `/login` or Cognito Hosted UI) and receives tokens. `/login` sets an `id_token` cookie.
3. Admin calls `/create-user` with either `Authorization: Bearer <id_token>` header or the `id_token` cookie.
4. Service verifies the token, checks `custom:role`, and calls Cognito `admin_create_user` to create the new user.

**Repository files**
- `main.py` — FastAPI app and endpoints.
- `auth.py` — Cognito helper functions (create user, initiate auth).
- `utils.py` — helpers for extracting tokens, admin checks, and cookie fallback.
- `jwk_utils.py` — JWKS fetching and token verification logic.
- `config.py` — environment-driven configuration.
- `docs/workflow.mmd` — Mermaid workflow diagram for the request flow.

Getting started
--------------

Requirements

- Python 3.10+ (3.11/3.13 recommended)
- AWS credentials with permissions to manage Cognito (for integration tests)

Local setup

1. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows: adjust to your shell
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root (a template is provided). Example values:

```env
AWS_REGION=ap-south-1
COGNITO_USER_POOL_ID=ap-south-1_xxx
COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxx
COGNITO_CLIENT_SECRET=your_client_secret_here  # optional - required if your client has a secret
APP_BASE_URL=http://localhost:8000
VERIFY_JWT_SIGNATURE=false
JWKS_CACHE_TTL=300
```

4. Run the app:

```bash
uvicorn main:app --reload
```

API endpoints and examples
--------------------------

POST /login

Authenticate a user. Request body:

```json
{ "username": "user@example.com", "password": "User@12345" }
```

On success, the endpoint returns the Cognito auth response and sets an HTTP-only `id_token` cookie. Example curl:

```bash
curl -i -X POST http://127.0.0.1:8000/login \
	-H 'Content-Type: application/json' \
	-d '{"username":"admin@example.com","password":"Admin@123"}'
```

POST /create-user (admin-only)

Creates a user in the specified Cognito user pool. You must be authenticated as an admin. The endpoint accepts a JSON body with `email`, `role`, and `password`.

Headers (one of these auth mechanisms must be present):
- `Authorization: Bearer <ID_TOKEN>`
- or rely on the browser to provide the HTTP-only `id_token` cookie set by `/login`.
- `X-Cognito-Pool-Id`: pool id (e.g. `ap-south-1_xxx`)
- `X-Cognito-Client-Id`: client id

Body example:

```json
{
	"email": "newuser@example.com",
	"role": "user",
	"password": "User@12345"
}
```

Example curl:

```bash
curl -X POST 'http://127.0.0.1:8000/create-user' \
	-H 'Authorization: Bearer YOUR_ADMIN_ID_TOKEN' \
	-H 'X-Cognito-Pool-Id: ap-south-1_xxx' \
	-H 'X-Cognito-Client-Id: xxxxxxxxxxxxxx' \
	-H 'Content-Type: application/json' \
	-d '{"email":"newuser@example.com","role":"user","password":"User@12345"}'
```

GET /whoami

Returns decoded claims from the IdToken. If `VERIFY_JWT_SIGNATURE=false` the claims are returned without signature verification (NOT FOR PROD).

Security notes
--------------

- Always enable `VERIFY_JWT_SIGNATURE=true` in production so tokens are validated against Cognito JWKS.
- Use HTTPS in production and set the cookie `secure=True` (the code sets `secure=False` for local testing).
- Keep `COGNITO_CLIENT_SECRET` private — if your Cognito app client uses a secret, add it to `.env` so this service can compute the required `SECRET_HASH`.
- Currently `admin_create_user` sets the provided password as permanent by default. If you need a temporary password and a forced reset on first login, change the `Permanent` flag when calling `admin_set_user_password` in `auth.py`.

Troubleshooting
---------------

- `NotAuthorizedException: SECRET_HASH was not received` — set `COGNITO_CLIENT_SECRET` in `.env` for clients that use a secret.
- `Invalid token: verify_cognito_token() got an unexpected keyword argument 'pool_id'` — make sure `jwk_utils.py` is updated to accept `pool_id` (this repo includes that change).
- If you see missing-header errors, ensure `X-Cognito-Pool-Id` and `X-Cognito-Client-Id` are included in the request.

Diagram
-------

See `docs/workflow.png` for the workflow diagram (PNG export of the Mermaid flowchart). You can preview the original Mermaid source in `docs/workflow.mmd` or paste it into https://mermaid.live to export a PNG.

Next improvements
-----------------

- Add integration tests (use `moto` or a Cognito emulator / mocks)
- Add OpenAPI security definitions for the id_token cookie and Bearer header
- Add a small frontend example that uses the cookie-based flow

If you want, I can export the Mermaid diagram to a PNG (saved to `docs/user_auth_creation.svg`) and add sample Postman/Insomnia collections. Tell me which you'd prefer.