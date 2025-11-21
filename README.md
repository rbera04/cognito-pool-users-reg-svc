# Cognito User Management Service - FastAPI

A production-ready FastAPI service for managing users in AWS Cognito User Pools. This service provides admin-protected endpoints for user creation, authentication, password management, and user administration with comprehensive JWT token verification and cookie-based session management.

## Features

- **User Management**: Create, list, and update users with custom attributes
- **Authentication**: Secure login with JWT tokens and HTTP-only cookie support
- **Password Management**: User password changes with old password verification
- **Admin Controls**: Admin-only endpoints for user listing and attribute updates
- **Token Verification**: Optional JWT signature verification using Cognito JWKS (production-recommended)
- **Role-Based Access Control**: Built-in role validation against configurable allowed roles
- **Multi-Pool Support**: Support for multiple Cognito user pools via custom headers
- **SECRET_HASH Support**: Automatic HMAC-SHA256 computation for clients with secrets
- **Error Handling**: Comprehensive error responses with meaningful messages

## Quick Start Flow

1. **Initial Setup**: Create an admin user in Cognito console with `custom:role=admin`
2. **Admin Login**: Admin authenticates via `/login` → receives ID token (set as HTTP-only cookie)
3. **Create Users**: Admin calls `/create-user` with token (header or cookie) → service creates user in Cognito
4. **User Operations**: Users can change passwords, view profile, admins can update attributes and list users

## Architecture

```
┌─────────────┐
│  main.py    │  FastAPI endpoints & request handlers
└──────┬──────┘
       │
       ├─→ auth.py ────────────────→ Cognito Operations (create_user, initiate_auth)
       ├─→ utils.py ───────────────→ Token extraction, Admin validation
       ├─→ jwk_utils.py ───────────→ JWKS fetching & JWT verification
       └─→ config.py ──────────────→ Environment configuration

┌──────────────────────────┐
│  AWS Cognito User Pool   │
│  - Authentication        │
│  - User Management       │
│  - Custom Attributes     │
└──────────────────────────┘
```

## Installation

### Requirements

- Python 3.10+ (3.11/3.13 recommended)
- pip / poetry
- AWS account with Cognito User Pool

### Setup Steps

1. **Clone and navigate to project**:
```bash
cd cognito-pool-users-reg-svc
```

2. **Create virtual environment**:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Configure environment (`.env` file)**:
```env
# AWS Configuration
AWS_REGION=ap-south-1
COGNITO_USER_POOL_ID=ap-south-1_xxx
COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxx
COGNITO_CLIENT_SECRET=your_client_secret_here  # Optional for public clients

# Application Configuration
APP_BASE_URL=http://localhost:8000
ALLOWED_ROLES=admin,user,editor  # Comma-separated roles
VERIFY_JWT_SIGNATURE=false        # Set to true in production

# Token Configuration
JWKS_CACHE_TTL=300               # Cache expiry in seconds
```

5. **Run the service**:
```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000` with interactive docs at `/docs`.

## API Endpoints

### Authentication Endpoints

#### `POST /login`
Authenticate a user and receive JWT tokens.

**Request:**
```json
{
  "username": "user@example.com",
  "password": "SecurePass@123"
}
```

**Response:**
```json
{
  "AuthenticationResult": {
    "AccessToken": "eyJkb2NzIjog...",
    "IdToken": "eyJSb2xlIjog...",
    "RefreshToken": "eyJSZWZyZXNo...",
    "ExpiresIn": 3600,
    "TokenType": "Bearer"
  }
}
```

**Example cURL:**
```bash
curl -X POST http://localhost:8000/login \
  -H 'Content-Type: application/json' \
  -d '{
    "username": "admin@example.com",
    "password": "Admin@123"
  }'
```

**Notes:**
- Sets HTTP-only `id_token` cookie (1-hour expiry, samesite=lax)
- Cookie used as fallback if Authorization header not provided
- Returns all Cognito tokens (AccessToken, IdToken, RefreshToken)

---

#### `GET /whoami`
Return decoded claims from the current IdToken.

**Headers:**
- `Authorization: Bearer <ID_TOKEN>` (optional if cookie set)
- `X-Cognito-Pool-Id: <pool_id>` (optional, uses config default)
- `X-Cognito-Client-Id: <client_id>` (optional, uses config default)

**Response:**
```json
{
  "sub": "abc123def456",
  "aud": "xxxxxxxxxxxxxxxxxxxx",
  "email_verified": true,
  "cognito:username": "user@example.com",
  "email": "user@example.com",
  "custom:role": "admin",
  "exp": 1700000000,
  "iat": 1699996400
}
```

**Example cURL:**
```bash
curl -X GET http://localhost:8000/whoami \
  -H 'Authorization: Bearer YOUR_ID_TOKEN'
```

---

### User Management Endpoints

#### `POST /create-user` (Admin Only)
Create a new user in the Cognito pool.

**Headers:**
- `Authorization: Bearer <ID_TOKEN>` OR rely on cookie
- `X-Cognito-Pool-Id: <pool_id>` (optional)
- `X-Cognito-Client-Id: <client_id>` (optional)

**Request:**
```json
{
  "email": "newuser@example.com",
  "role": "user",
  "password": "User@12345",
  "role_name": "Editor",
  "role_id": "editor_001"
}
```

**Response:**
```json
{
  "message": "User created in Cognito. Permanent password set. User can now log in."
}
```

**Example cURL:**
```bash
curl -X POST http://localhost:8000/create-user \
  -H 'Authorization: Bearer YOUR_ADMIN_ID_TOKEN' \
  -H 'X-Cognito-Pool-Id: ap-south-1_xxx' \
  -H 'X-Cognito-Client-Id: xxxxxxxxxxxxxx' \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "newuser@example.com",
    "role": "user",
    "password": "User@12345",
    "role_name": "Editor",
    "role_id": "editor_001"
  }'
```

**Validation:**
- Admin role required (checked via `custom:role` attribute)
- Role must be in `ALLOWED_ROLES` configuration
- Email must be valid format
- Password must meet Cognito requirements
- User attributes stored as Cognito custom attributes

---

#### `GET /list-users` (Admin Only)
List all users in the Cognito pool with their attributes (paginated).

**Headers:**
- `Authorization: Bearer <ID_TOKEN>` OR rely on cookie
- `X-Cognito-Pool-Id: <pool_id>` (optional)
- `X-Cognito-Client-Id: <client_id>` (optional)

**Response:**
```json
{
  "total": 15,
  "users": [
    {
      "username": "user@example.com",
      "status": "CONFIRMED",
      "created": "2024-11-21 10:30:45.123456+00:00",
      "modified": "2024-11-21 10:30:45.123456+00:00",
      "attributes": {
        "sub": "abc123def456",
        "email": "user@example.com",
        "email_verified": "true",
        "custom:role": "user",
        "custom:roleName": "Editor",
        "custom:roleId": "editor_001"
      }
    }
  ]
}
```

**Example cURL:**
```bash
curl -X GET http://localhost:8000/list-users \
  -H 'Authorization: Bearer YOUR_ADMIN_ID_TOKEN'
```

---

#### `POST /update-user` (Admin Only)
Update user attributes (supports custom role fields).

**Headers:**
- `Authorization: Bearer <ID_TOKEN>` OR rely on cookie
- `X-Cognito-Pool-Id: <pool_id>` (optional)
- `X-Cognito-Client-Id: <client_id>` (optional)

**Request:**
```json
{
  "username": "user@example.com",
  "role_name": "Senior Editor",
  "role_id": "editor_002"
}
```

**Response:**
```json
{
  "message": "User updated successfully",
  "user": {
    "username": "user@example.com",
    "status": "CONFIRMED",
    "attributes": {
      "email": "user@example.com",
      "custom:roleName": "Senior Editor",
      "custom:roleId": "editor_002"
    }
  }
}
```

**Example cURL:**
```bash
curl -X POST http://localhost:8000/update-user \
  -H 'Authorization: Bearer YOUR_ADMIN_ID_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{
    "username": "user@example.com",
    "role_name": "Senior Editor",
    "role_id": "editor_002"
  }'
```

---

#### `POST /change-password`
Change password for the authenticated user.

**Headers:**
- `Authorization: Bearer <ID_TOKEN>` OR rely on cookie
- `X-Cognito-Pool-Id: <pool_id>` (optional)
- `X-Cognito-Client-Id: <client_id>` (optional)

**Request:**
```json
{
  "old_password": "CurrentPass@123",
  "new_password": "NewPass@456"
}
```

**Response:**
```json
{
  "message": "Password changed successfully"
}
```

**Example cURL:**
```bash
curl -X POST http://localhost:8000/change-password \
  -H 'Authorization: Bearer YOUR_ID_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{
    "old_password": "CurrentPass@123",
    "new_password": "NewPass@456"
  }'
```

**Flow:**
1. User provides old password
2. Service re-authenticates user with old password
3. If successful, extracts AccessToken from Cognito
4. Uses AccessToken to call `change_password()` API
5. Validates new password meets Cognito requirements

---

## Error Responses

All error responses follow this format:

```json
{
  "detail": "Error message describing the issue"
}
```

### Common Status Codes

| Status | Meaning | Example |
|--------|---------|---------|
| 200 | Success | User created, password changed |
| 400 | Bad Request | Invalid role, invalid password, user already exists |
| 401 | Unauthorized | Missing/invalid token, incorrect old password |
| 403 | Forbidden | Non-admin user attempting admin operation |
| 404 | Not Found | User not found in pool |
| 500 | Server Error | AWS API error, network failure |

---

## Configuration

All configuration is environment-driven via `.env` file:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AWS_REGION` | Yes | - | AWS region (e.g., `ap-south-1`) |
| `COGNITO_USER_POOL_ID` | Yes | - | Cognito User Pool ID |
| `COGNITO_CLIENT_ID` | Yes | - | Cognito App Client ID |
| `COGNITO_CLIENT_SECRET` | No | - | App Client Secret (if client has secret enabled) |
| `ALLOWED_ROLES` | No | `admin,user` | Comma-separated allowed roles |
| `VERIFY_JWT_SIGNATURE` | No | `false` | Verify JWT signatures (always true in production) |
| `JWKS_CACHE_TTL` | No | `300` | JWKS cache expiry in seconds |
| `APP_BASE_URL` | No | `http://localhost:8000` | Application base URL |

---

## Security Considerations

### Production Checklist

- [ ] Set `VERIFY_JWT_SIGNATURE=true` to validate tokens against Cognito JWKS
- [ ] Enable HTTPS and set cookie `secure=True` in code
- [ ] Use strong password policies in Cognito user pool settings
- [ ] Store `COGNITO_CLIENT_SECRET` securely (not in code, use environment variables)
- [ ] Enable MFA in Cognito for admin accounts
- [ ] Use IAM policies to restrict who can call Cognito APIs
- [ ] Enable CloudTrail logging for audit trails
- [ ] Implement rate limiting on login endpoint
- [ ] Use secrets manager for credentials
- [ ] Regularly rotate application credentials

### Token Management

- **ID Token**: Used for user identification and authorization. Contains user claims including custom attributes.
- **Access Token**: Used for API access and password management. Different from ID token.
- **Refresh Token**: Used to obtain new tokens without re-authenticating.
- **Token Expiration**: Enforced even when signature verification is disabled.

### Cookie Security

- **HttpOnly**: True (prevents JavaScript access)
- **Secure**: False (set to True in production with HTTPS)
- **SameSite**: `lax` (CSRF protection)
- **Max-Age**: 3600 seconds (1 hour)

---

## Code Organization

### `main.py`
- FastAPI application setup
- Endpoint definitions
- Request/response models (Pydantic)
- Dependency injection for admin authorization

### `auth.py`
- Cognito client operations
- `admin_create_user()` - Create users with custom attributes
- `initiate_auth()` - Authenticate users
- `compute_secret_hash()` - HMAC-SHA256 for SECRET_HASH

### `utils.py`
- `get_cognito_client()` - Singleton boto3 client
- `get_token()` - Extract token from header/cookie
- `extract_cognito_context()` - Get pool/client IDs from headers
- `require_admin()` - Admin authorization dependency

### `jwk_utils.py`
- `verify_cognito_token()` - JWT verification with optional signature checking
- `_fetch_jwks()` - Fetch and cache JWKS from Cognito
- Per-URL JWKS caching for multi-pool support

### `config.py`
- Environment variable loading
- Configuration validation
- Default values

---

## Troubleshooting

### Common Issues

**Error: "SECRET_HASH was not received"**
- **Cause**: Cognito app client has a secret, but `COGNITO_CLIENT_SECRET` not set
- **Solution**: Add `COGNITO_CLIENT_SECRET` to `.env` file

**Error: "Invalid token: Token expired"**
- **Cause**: ID token has expired (default 1 hour)
- **Solution**: Use `/login` to get new tokens or use Refresh Token

**Error: "Missing IdToken. Please sign in first"**
- **Cause**: Authorization header missing and no id_token cookie found
- **Solution**: Include `Authorization: Bearer <TOKEN>` header or login first to set cookie

**Error: "Admin role required"**
- **Cause**: User doesn't have `custom:role=admin` in Cognito
- **Solution**: Update user attributes in Cognito console or use admin endpoint

**Error: "Invalid role. Allowed roles: ..."**
- **Cause**: Provided role not in `ALLOWED_ROLES` configuration
- **Solution**: Check `ALLOWED_ROLES` environment variable or use one of the allowed roles

**Error: "X-Cognito-Pool-Id and X-Cognito-Client-Id headers required"**
- **Cause**: Custom headers missing (if not using defaults from config)
- **Solution**: Include headers in request OR ensure `.env` has default values

---

## Development & Testing

### Run Tests
```bash
pytest tests/
```

### Run with Auto-Reload
```bash
uvicorn main:app --reload
```

### View Interactive API Docs
Open `http://localhost:8000/docs` in browser (Swagger UI)

### Export OpenAPI Schema
```bash
curl http://localhost:8000/openapi.json > openapi.json
```

---

## Performance & Optimization

- **Singleton Cognito Client**: Single boto3 client reused across all endpoints
- **JWKS Caching**: 5-minute default cache (configurable) per JWKS URL
- **Dict Comprehensions**: Optimized attribute extraction
- **Centralized Token Logic**: Unified token extraction and validation
- **Connection Pooling**: Boto3 handles connection reuse automatically

See `OPTIMIZATIONS.md` for detailed optimization notes.

---

## Future Enhancements

- [ ] Integration tests with moto or local Cognito emulator
- [ ] Admin password reset endpoint (without old password)
- [ ] User deletion endpoint
- [ ] User enable/disable endpoints
- [ ] Request rate limiting
- [ ] OpenAPI security scheme definitions
- [ ] Frontend example with cookie-based auth flow
- [ ] Postman/Insomnia collection examples
- [ ] Comprehensive unit tests with mocking
- [ ] Docker containerization

---

## Support & Documentation

- **Cognito Docs**: https://docs.aws.amazon.com/cognito/
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **Boto3 Cognito**: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cognito-idp.html
- **Workflow Diagram**: See `docs/workflow.mmd` (Mermaid flowchart)

---

## License

[Add your license here]

## Contributing

Contributions welcome! Please follow the existing code style and add tests for new features.
