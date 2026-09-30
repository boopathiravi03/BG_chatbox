# Phase 7.2 — FastAPI Swagger Documentation CSP Fix Report

## 1. Overview
The Swagger UI (`/docs`) and ReDoc (`/redoc`) documentation endpoints in FastAPI require external CDN assets (`cdn.jsdelivr.net`), inline scripts, and the FastAPI favicon (`fastapi.tiangolo.com`). The production `SecurityHeadersMiddleware` previously applied `Content-Security-Policy: default-src 'none'` globally, causing `/docs` to load a blank screen due to browser CSP enforcement.

A path-scoped CSP policy was implemented within `SecurityHeadersMiddleware` to permit Swagger UI and ReDoc to render normally, while strictly retaining the existing `default-src 'none'` policy for all application and API endpoints.

---

## 2. Exact Middleware Change
File modified: `backend/app/main.py`

```python
# ── Security headers middleware ───────────────────────────────────────────────
_DOCS_PATHS = {"/docs", "/redoc", "/docs/oauth2-redirect"}
_DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none';"
)
_STRICT_CSP = "default-src 'none'"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"

        path = request.url.path
        if path in _DOCS_PATHS or path.rstrip("/") in {"/docs", "/redoc"}:
            response.headers["Content-Security-Policy"] = _DOCS_CSP
        else:
            response.headers["Content-Security-Policy"] = _STRICT_CSP

        if os.getenv("BGAI_PRODUCTION", "false").lower() == "true":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)
```

---

## 3. Routes Receiving Docs CSP
The following exact documentation routes receive `_DOCS_CSP`:
- `/docs`
- `/docs/`
- `/redoc`
- `/redoc/`
- `/docs/oauth2-redirect`

**Header Value:**
```http
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none';
```

---

## 4. Routes Retaining Strict CSP
Every other application and API route strictly retains `_STRICT_CSP` (`default-src 'none'`). Verified via live probing:
- `GET /` -> `default-src 'none'`
- `GET /openapi.json` -> `default-src 'none'`
- `POST /auth/login` -> `default-src 'none'`
- `POST /auth/register` -> `default-src 'none'`
- `GET /auth/me` -> `default-src 'none'`
- `GET /agents` -> `default-src 'none'`
- `GET /agent-actions` -> `default-src 'none'`
- `GET /schema` -> `default-src 'none'`
- `POST /connect` -> `default-src 'none'`
- `GET /intelligence` -> `default-src 'none'`
- All `/chat`, `/query`, `/forecasting/*`, `/anomaly/*`, and database routes.

---

## 5. `/docs` Verification
- **URL:** `http://127.0.0.1:8001/docs`
- **HTTP Status:** `200 OK`
- **Content-Type:** `text/html; charset=utf-8`
- **CSP Received:** Scoped documentation CSP allowing `cdn.jsdelivr.net` and `'unsafe-inline'`.
- **Assets Permitted:**
  - Stylesheet: `https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css` (Allowed)
  - JavaScript Bundle: `https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js` (Allowed)
  - Inline Initialization: `<script>const ui = SwaggerUIBundle({...})</script>` (Allowed)
  - Favicon: `https://fastapi.tiangolo.com/img/favicon.png` (Allowed)
  - API Schema Connect: `/openapi.json` (Allowed via `'self'`)
- **Result:** Swagger UI renders completely without browser CSP blocking errors.

---

## 6. `/redoc` Verification
- **URL:** `http://127.0.0.1:8001/redoc`
- **HTTP Status:** `200 OK`
- **Content-Type:** `text/html; charset=utf-8`
- **CSP Received:** Scoped documentation CSP.
- **Result:** ReDoc documentation page loads and executes successfully.

---

## 7. Regression Test Results

| Test Suite | Command | Result |
|---|---|---|
| **Python Syntax/Compile** | `python -m compileall app` | **PASS (0 errors)** |
| **Phase 7 Security Suite** | `python scratch/test_phase7_security.py` | **35 / 35 PASS** |
| **Phase 7 Isolation Suite** | `python scratch/test_phase7_isolation.py` | **12 / 12 PASS** |
| **Phase 5 Agent Suite** | `python scratch/test_phase5_agents.py` | **32 / 32 PASS** |
| **Real Database Suite** | `python scratch/test_real_db_agents.py` | **A–F ALL PASS** |

---

## 8. Frontend Build Result
- **Command:** `npm run build`
- **Result:** **PASS (0 TypeScript errors, 0 Vite build errors)** in 3.07s.

---

## 9. Final Status: **PASS**
The Swagger UI CSP issue is fixed cleanly without weakening the strict production security posture of standard application routes. No code has been committed or pushed per instructions.
