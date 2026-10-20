from __future__ import annotations

import os
import re
import logging
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, Any, Union, Dict, List
from starlette.middleware.base import BaseHTTPMiddleware

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.paths import get_app_data_dir

# ── App init & Rate Limiter ───────────────────────────────────────────────────
_desktop_mode = os.getenv("BGAI_DESKTOP_MODE") == "1"
limiter = Limiter(key_func=get_remote_address, enabled=not _desktop_mode)
app = FastAPI(title="BG AI", version="7.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
_PRODUCTION_ORIGINS = [
    "https://thebg.co.in",
    "https://thebg.con.in",
    "http://thebg.co.in",
    "http://thebg.con.in",
]
_DEV_ORIGINS = os.getenv("BGAI_EXTRA_ORIGINS", "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000").split(",")
_ALLOWED_ORIGINS = _PRODUCTION_ORIGINS + [o.strip() for o in _DEV_ORIGINS if o.strip()]
if os.getenv("BGAI_DESKTOP_MODE") == "1":
    if "*" not in _ALLOWED_ORIGINS:
        _ALLOWED_ORIGINS.extend(["null", "*"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-BGAI-Desktop-Secret"],
)


# ── Desktop Secret Auth Middleware ───────────────────────────────────────────
class DesktopSecretMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        desktop_secret = os.getenv("BGAI_DESKTOP_SECRET")
        if desktop_secret and os.getenv("BGAI_DESKTOP_MODE") == "1":
            path = request.url.path
            # Allow health checks, docs, and preflight OPTIONS without desktop secret
            if (
                request.method != "OPTIONS"
                and path not in {"/health", "/docs", "/redoc", "/openapi.json"}
                and not path.startswith("/docs")
            ):
                client_secret = request.headers.get("X-BGAI-Desktop-Secret")
                if not client_secret or client_secret != desktop_secret:
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"status": "error", "error": "Access Denied: Invalid desktop authentication secret."},
                    )
        return await call_next(request)


app.add_middleware(DesktopSecretMiddleware)


# ── Security headers middleware ───────────────────────────────────────────────
_DOCS_PATHS = {"/docs", "/redoc", "/docs/oauth2-redirect"}
_DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "font-src 'self' data:; "
    "connect-src 'self' https://cdn.jsdelivr.net http://127.0.0.1:8001 https://bg-chatbox.onrender.com; "
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


# ── IP Threat & Intrusion Detection Middleware ─────────────────────────────────
from app.security.ip_intelligence import (
    extract_client_ip,
    get_intrusion_engine,
    get_reputation_provider,
)


class IPThreatMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Safely extract client IP
        client_ip = extract_client_ip(request)
        request.state.client_ip = client_ip

        engine = get_intrusion_engine()

        # 2. Check if IP is actively blocked
        is_blocked, block = engine.is_ip_blocked(client_ip)
        if is_blocked and block:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "status": "error",
                    "error": "Access Denied: Your IP address is temporarily blocked due to detected security policy violations.",
                    "ip": client_ip,
                    "reason": block.reason,
                    "rule": block.rule_triggered,
                },
            )

        # 3. Monitor request velocity (burst detection) for all paths except static health checks
        path = request.url.path
        if path not in {"/", "/health", "/favicon.ico"}:
            engine.record_request_activity(client_ip, endpoint=path, user_id="system_edge")

        response = await call_next(request)

        # 4. Probe detection on 404 responses
        if response.status_code == 404:
            engine.record_probe_attempt(client_ip, path=path, user_id="scanner_probe")

        return response


app.add_middleware(IPThreatMiddleware)

# ── Auth & Context imports ────────────────────────────────────────────────────
from app.security.auth import create_access_token
from app.security.sessions import (
    get_current_user, AuthenticatedUser,
    register_user, authenticate_user, lookup_user_email, get_user_by_id,
)
from app.database.connection_context import (
    set_user_context_for_request,
    connect_sqlite_for_user,
    connect_mysql_for_user,
    connect_postgres_for_user,
    clear_user_context,
    get_user_context,
)
from app.security.user_cache import cache_clear_user

# ── Tool imports ──────────────────────────────────────────────────────────────
from app.agent.orchestrator import run_agent as _run_agent, clear_pending_insert, generate_suggestions
from app.tools.get_schema import get_schema
from app.tools.execute_query import validate_sql, execute_query
from app.tools.get_relationship_graph import get_relationship_graph
from app.tools.dashboard_data import get_dashboard_data as get_analytics_data
from app.tools.analyze_database import analyze_database
from app.database.db import get_database_info, get_dashboard_data
from app.database.database_manager import get_current_db_type, get_database_connection_info, get_engine
from app.database.database_context import refresh_database_profile, get_database_profile, clear_database_profile
from app.database.backup import create_backup, restore_backup, get_backup_dir
from app.tools.optimize_sql import optimize_sql


# ── Startup ────────────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    clear_database_profile()
    try:
        import app.agents.audit_db
        import app.security.models
    except Exception:
        pass


# ── Pydantic request models ────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str = ""


class LoginRequest(BaseModel):
    username: str
    password: str


class FirebaseLoginRequest(BaseModel):
    id_token: str
    username: Optional[str] = None
    email: Optional[str] = None


class LookupEmailRequest(BaseModel):
    username: str


class ChatRequest(BaseModel):
    message: str = ""
    session_id: str = "default"
    input_values: dict | None = None
    pending_insert: bool = False
    connection_id: str | None = None
    selected_source_ids: list[str] | None = None


class ConfirmQueryRequest(BaseModel):
    session_id: str
    fingerprint: Optional[str] = None
    high_risk_confirmed: bool = False


class DatabaseConnection(BaseModel):
    db_type: str
    host: str = ""
    port: int = 3306
    database: str = ""
    username: str = ""
    password: str = ""
    name: str | None = None


class MultiConnectionRequest(BaseModel):
    connector_type: str
    name: str | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    password: str | None = None
    file_path: str | None = None
    delimiter: str | None = None
    auth_source: str | None = None
    api_key: str | None = None
    tenant: str | None = None
    driver: str | None = None
    collection_name: str | None = None
    connection_string: str | None = None
    db: int | None = None
    ssl: bool = False
    is_read_only: bool = False
    set_as_active: bool = True
    config: dict[str, Any] | None = None


class RenameConnectionRequest(BaseModel):
    name: str


class UpdatePermissionRequest(BaseModel):
    is_read_only: bool


class CrossQueryRequest(BaseModel):
    message: str
    selected_source_ids: list[str] | None = None


class OptimizationRequest(BaseModel):
    sql: str


class QueryRequest(BaseModel):
    query: str
    connection_id: str | None = None


class AgentRunRequest(BaseModel):
    task: str
    agent_name: str | None = None
    context: dict | None = None


class AnalystAskRequest(BaseModel):
    question: str
    table: str | None = None
    metric: str | None = None


class ForecastRequest(BaseModel):
    table: str
    date_column: str
    metric_column: str | None = None
    frequency: str = "monthly"
    horizon: int = 3
    aggregation: str = "SUM"


def _activate(user: AuthenticatedUser, connection_id: str | None = None, request: Request | None = None):
    client_ip = getattr(request.state, "client_ip", None) if request and hasattr(request, "state") else None
    set_user_context_for_request(user.user_id, connection_id, client_ip=client_ip)


# =============================================================================
# PUBLIC ENDPOINTS
# =============================================================================

@app.get("/")
def home():
    return {"message": "BG AI Backend v7", "status": "operational"}


@app.get("/health")
def health():
    return {"status": "ok", "app": "BG AI", "version": "1.0.0"}


@app.post("/auth/register")
@limiter.limit("5/minute")
def auth_register(req: RegisterRequest, request: Request):
    try:
        if not req.username or len(req.username) < 3:
            raise HTTPException(status_code=400, detail="Username must be at least 3 characters.")
        if not req.password or len(req.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

        user = register_user(req.username, req.password, req.email)
        token = create_access_token(user["user_id"], user["username"])
        return {
            "access_token": token,
            "token_type": "bearer",
            "user_id": user["user_id"],
            "username": user["username"],
        }
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@app.post("/auth/lookup-email")
@limiter.limit("60/minute")
def auth_lookup_email(req: LookupEmailRequest, request: Request):
    clean = req.username.strip().lower()
    if not clean:
        return {"found": False, "email": None, "username": clean}
    info = lookup_user_email(clean)
    if info and info.get("email"):
        return {"found": True, "email": info["email"], "username": info["username"]}
    return {
        "found": False,
        "email": None,
        "username": info["username"] if info else clean,
    }


@app.post("/auth/login")
@limiter.limit("10/minute")
def auth_login(req: LoginRequest, request: Request):
    from app.security.sessions import authenticate_user_detailed
    user, reason = authenticate_user_detailed(req.username, req.password)
    if not user:
        client_ip = getattr(request.state, "client_ip", None) or extract_client_ip(request)
        get_intrusion_engine().record_auth_failure(
            ip_address=client_ip,
            username=req.username,
            user_id="auth_failure",
        )
        if reason == "ACCOUNT_INACTIVE":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive. Please contact your administrator.",
            )
        elif reason == "USER_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account not found. Please verify your username/email or register an account.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        elif reason.startswith("DATABASE_ERROR"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Local database connection error. Please restart BG AI.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect password. Please verify your credentials and try again.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    token = create_access_token(user["user_id"], user["username"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user["user_id"],
        "username": user["username"],
        "email": user.get("email"),
    }


@app.post("/auth/firebase")
@limiter.limit("20/minute")
def auth_firebase_login(req: FirebaseLoginRequest, request: Request):
    from app.security.firebase_auth import verify_firebase_id_token
    from app.security.sessions import sync_firebase_user

    payload = verify_firebase_id_token(req.id_token)
    if not payload:
        client_ip = getattr(request.state, "client_ip", None) or extract_client_ip(request)
        get_intrusion_engine().record_auth_failure(
            ip_address=client_ip,
            username=req.username or "firebase_user",
            user_id="auth_failure",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Firebase authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    uid = payload["uid"]
    email = payload.get("email") or req.email
    name = payload.get("name") or req.username

    user = sync_firebase_user(uid, email=email, display_name=name)
    token = create_access_token(user["user_id"], user["username"])

    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user["user_id"],
        "username": user["username"],
        "email": user.get("email"),
    }


@app.get("/auth/me")
def auth_me(user: AuthenticatedUser = Depends(get_current_user)):
    info = get_user_by_id(user.user_id)
    if not info:
        raise HTTPException(status_code=404, detail="User not found.")
    return info


# =============================================================================
# PROTECTED ENDPOINTS (require Bearer token)
# =============================================================================

@app.post("/chat")
@limiter.limit("60/minute")
def chat(req: ChatRequest, request: Request, user: AuthenticatedUser = Depends(get_current_user)):
    target_conn_id = req.connection_id or request.headers.get("X-Connection-ID")
    _activate(user, target_conn_id)
    try:
        from app.connectors.registry import get_connection_registry
        from app.intelligence.cross_db import CrossDatabaseEngine
        reg = get_connection_registry()
        user_conns = reg.list_connectors(user.user_id)

        # Multi-source routing or explicit selection
        should_cross = False
        if req.selected_source_ids and len(req.selected_source_ids) > 1:
            should_cross = True
        elif len(user_conns) > 1 and any(w in req.message.lower() for w in ["compare", "across", "both", "all databases", "all sources", "federate"]):
            should_cross = True
        elif any(w in req.message.lower() for w in ["semantic", "semantically", "vector", "similar documents", "embeddings"]):
            should_cross = True

        if should_cross:
            cross_res = CrossDatabaseEngine.process(
                user_id=user.user_id,
                message=req.message,
                selected_source_ids=req.selected_source_ids,
            )
            return {
                "generated_sql": cross_res.sub_results[0].query_text if cross_res.sub_results else "",
                "result": cross_res.combined_result or {
                    "success": not bool(cross_res.error),
                    "columns": [],
                    "rows": [],
                    "rows_returned": 0,
                    "error": cross_res.error,
                },
                "explanation": cross_res.explanation,
                "sources_used": cross_res.sources_used,
                "combination_strategy": cross_res.combination_strategy,
                "requires_disambiguation": cross_res.requires_disambiguation,
                "disambiguation_options": cross_res.disambiguation_options,
                "chart": cross_res.chart,
                "followups": [],
            }

        return _run_agent(
            req.message,
            f"{user.user_id}:{req.session_id}",
            input_values=req.input_values,
            pending_insert=req.pending_insert,
        )
    except Exception as e:
        logging.getLogger("bgai").error("Chat error: %s", str(e), exc_info=True)
        return {
            "generated_sql": "",
            "result": {"success": False, "error": "Internal error. Please try again."},
            "explanation": "An error occurred processing your request.",
            "followups": [],
        }


@app.post("/confirm-query")
def confirm_query(request: ConfirmQueryRequest, user: AuthenticatedUser = Depends(get_current_user)):
    _activate(user)
    try:
        from app.crud.service import execute_confirmed
        return execute_confirmed(
            f"{user.user_id}:{request.session_id}",
            fingerprint=request.fingerprint,
            high_risk_confirmed=request.high_risk_confirmed,
        )
    except Exception as e:
        return {"success": False, "confirmed": False, "error": str(e)}


@app.post("/upload")
@limiter.limit("10/minute")
async def upload_database(
    request: Request,
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        contents = await file.read()
        safe_name = Path(file.filename).name

        if not safe_name.lower().endswith((".db", ".sqlite", ".sqlite3")):
            raise HTTPException(status_code=400, detail="Only .db / .sqlite / .sqlite3 files are accepted.")

        if os.getenv("BGAI_DESKTOP_MODE") == "1":
            upload_dir = get_app_data_dir() / "database"
        else:
            upload_dir = Path(__file__).resolve().parents[2] / "database"
        upload_dir.mkdir(parents=True, exist_ok=True)
        db_path = upload_dir / safe_name
        db_path.write_bytes(contents)

        ctx = connect_sqlite_for_user(user.user_id, str(db_path))
        set_user_context_for_request(user.user_id)

        profile = refresh_database_profile()
        return {
            "status": "success",
            "message": "Database uploaded successfully",
            "database": db_path.name,
            "tables": list(get_schema().keys()),
            "context_id": ctx.context_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/connect")
@limiter.limit("10/minute")
def connect_database(
    req: DatabaseConnection,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        cache_clear_user(user.user_id)
        clear_pending_insert()
        try:
            from app.agent.orchestrator import conversation_state
            conversation_state.pop(f"{user.user_id}:default", None)
        except Exception:
            pass

        if req.db_type == "mysql":
            ctx = connect_mysql_for_user(
                user.user_id, req.host, req.port, req.database, req.username, req.password
            )
        elif req.db_type == "postgres":
            ctx = connect_postgres_for_user(
                user.user_id, req.host, req.port, req.database, req.username, req.password
            )
        elif req.db_type == "sqlite":
            ctx = connect_sqlite_for_user(user.user_id, req.database)
        else:
            return {"status": "error", "message": "Unsupported database type"}

        set_user_context_for_request(user.user_id)
        profile = refresh_database_profile()
        schema = get_schema()

        return {
            "status": "success",
            "database": req.db_type,
            "message": f"Connected to {req.db_type} successfully",
            "database_info": get_database_info(),
            "schema": schema,
            "tables": list(schema.keys()),
            "table_count": len(schema),
            "context_id": ctx.context_id,
            "analysis": profile.to_context() if profile else "",
        }
    except Exception as e:
        err = str(e)
        if "1045" in err:
            msg = "Access denied. Check username and password."
        elif "2003" in err or "Can't connect" in err:
            msg = "Cannot reach database server. Check host and port."
        elif "does not exist" in err and "database" in err.lower():
            msg = "Database does not exist."
        else:
            msg = f"Connection failed: {err}"
        return {"status": "error", "message": msg}


@app.post("/disconnect")
def disconnect(
    connection_id: Optional[str] = None,
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        clear_user_context(user.user_id, connection_id=connection_id)
        cache_clear_user(user.user_id)
        clear_database_profile()
        clear_pending_insert()

        try:
            from app.agent.orchestrator import conversation_state
            to_del = [k for k in list(conversation_state.keys()) if k.startswith(user.user_id)]
            for k in to_del:
                conversation_state.pop(k, None)
        except Exception:
            pass

        try:
            from app.intelligence.anomaly.detector import clear_cached_anomaly_report
            clear_cached_anomaly_report()
        except Exception:
            pass

        return {"status": "success", "message": "Database disconnected successfully", "db_type": "none"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/schema")
def schema_endpoint(
    request: Request,
    connection_id: Optional[str] = None,
    user: AuthenticatedUser = Depends(get_current_user),
):
    target_conn_id = connection_id or request.headers.get("X-Connection-ID")
    _activate(user, target_conn_id)
    try:
        return get_schema(target_conn_id)
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/database-info")
def database_info(
    request: Request,
    connection_id: Optional[str] = None,
    user: AuthenticatedUser = Depends(get_current_user),
):
    target_conn_id = connection_id or request.headers.get("X-Connection-ID")
    _activate(user, target_conn_id)
    try:
        from app.connectors.registry import get_connection_registry, ConnectorStatus
        reg = get_connection_registry()
        active = None
        if target_conn_id:
            active = reg.get_connector(user.user_id, target_conn_id)
        if not active:
            active = reg.get_active_connector(user.user_id)

        if active:
            is_conn = (active.status == ConnectorStatus.CONNECTED)
            if not is_conn and hasattr(active, "connect"):
                try:
                    is_conn = bool(active.connect())
                except Exception:
                    is_conn = False
            stats = active.get_stats() if is_conn else {}
            tables = stats.get("tables", stats.get("collections", stats.get("tables_count", 0)))
            rows = stats.get("rows", stats.get("documents", stats.get("total_keys", stats.get("total_points", stats.get("total_documents", 0)))))
            cols = stats.get("columns", 0)

            # If active connector returned 0 tables or rows for relational category, fallback to get_database_info()
            if active.category.value == "relational" and (tables == 0 or rows == 0):
                try:
                    fb = get_database_info()
                    if fb.get("connected"):
                        if tables == 0 and fb.get("tables", 0) > 0:
                            tables = fb.get("tables", 0)
                        if rows == 0 and fb.get("rows", 0) > 0:
                            rows = fb.get("rows", 0)
                        if cols == 0 and fb.get("columns", 0) > 0:
                            cols = fb.get("columns", 0)
                except Exception:
                    pass

            return {
                "connected": is_conn,
                "db_type": active.connector_type,
                "database": active.name,
                "database_name": getattr(active, "database", active.name),
                "connection_id": active.connection_id,
                "tables": tables,
                "collections": stats.get("collections", tables if active.category.value == "document" else 0),
                "rows": rows,
                "documents": stats.get("documents", rows if active.category.value == "document" else 0),
                "columns": cols,
                "size": stats.get("size", stats.get("used_memory", "Remote Database" if active.category.value != "file" else "Local File")),
                "status": active.status.value,
                "category": active.category.value,
                "is_exact": True,
            }

        fb = get_database_info()
        fb.setdefault("status", "connected" if fb.get("connected") else "disconnected")
        fb.setdefault("category", "relational")
        fb.setdefault("collections", 0)
        fb.setdefault("documents", 0)
        fb.setdefault("is_exact", True)
        return fb
    except Exception as e:
        return {
            "connected": False,
            "db_type": "none",
            "database": "Not Connected",
            "tables": 0,
            "collections": 0,
            "rows": 0,
            "documents": 0,
            "columns": 0,
            "size": "0 B",
            "status": "error",
            "category": "none",
            "is_exact": False,
            "error": str(e),
        }


@app.get("/database-type")
def database_type(
    request: Request,
    connection_id: Optional[str] = None,
    user: AuthenticatedUser = Depends(get_current_user),
):
    target_conn_id = connection_id or request.headers.get("X-Connection-ID")
    _activate(user, target_conn_id)
    try:
        from app.connectors.registry import get_connection_registry, ConnectorStatus
        reg = get_connection_registry()
        active = None
        if target_conn_id:
            active = reg.get_connector(user.user_id, target_conn_id)
        if not active:
            active = reg.get_active_connector(user.user_id)

        if active:
            is_conn = (active.status == ConnectorStatus.CONNECTED)
            return {
                "connected": is_conn,
                "db_type": active.connector_type,
                "connection_id": active.connection_id,
                "name": active.name,
                "category": active.category.value,
            }

        eng = get_engine()
        db_t = get_current_db_type()
        return {
            "connected": eng is not None and db_t != "none",
            "db_type": db_t,
        }
    except Exception as e:
        return {"connected": False, "db_type": "none", "error": str(e)}


@app.get("/database-connection-info")
def database_connection_info(
    request: Request,
    connection_id: Optional[str] = None,
    user: AuthenticatedUser = Depends(get_current_user),
):
    target_conn_id = connection_id or request.headers.get("X-Connection-ID")
    _activate(user, target_conn_id)
    try:
        from app.connectors.registry import get_connection_registry, ConnectorStatus
        reg = get_connection_registry()
        active = None
        if target_conn_id:
            active = reg.get_connector(user.user_id, target_conn_id)
        if not active:
            active = reg.get_active_connector(user.user_id)

        if active:
            is_conn = (active.status == ConnectorStatus.CONNECTED)
            cfg = active.to_sanitized_config()
            driver_name = (
                "pymongo"
                if active.connector_type == "mongodb"
                else "redis-py"
                if active.connector_type == "redis"
                else active.connector_type
            )
            return {
                "connected": is_conn,
                "db_type": active.connector_type,
                "connection_id": active.connection_id,
                "name": active.name,
                "host": cfg.get("host"),
                "port": cfg.get("port"),
                "database": cfg.get("database"),
                "username": cfg.get("username"),
                "driver": driver_name,
            }

        return get_database_connection_info()
    except Exception as e:
        return {"connected": False, "db_type": "none", "error": str(e)}


@app.post("/query")
@limiter.limit("30/minute")
def run_query(request: Request, req: QueryRequest, user: AuthenticatedUser = Depends(get_current_user)):
    target_conn_id = req.connection_id or request.headers.get("X-Connection-ID")
    _activate(user, target_conn_id, request=request)
    try:
        return execute_query(req.query, connection_id=target_conn_id)
    except Exception as e:
        return {"success": False, "columns": [], "rows": [], "error": str(e), "rows_returned": 0}


# =============================================================================
# MULTI-DATABASE CONNECTIONS API (BG AI 2.0)
# =============================================================================

@app.get("/connections/catalog")
def get_catalog():
    from app.connectors.registry import get_supported_connectors_catalog
    return {"status": "success", "catalog": get_supported_connectors_catalog()}


@app.get("/connections")
def list_connections(user: AuthenticatedUser = Depends(get_current_user)):
    _activate(user)
    try:
        from app.connectors.registry import get_connection_registry
        reg = get_connection_registry()
        conns = reg.list_connectors(user.user_id)
        active = reg.get_active_connector(user.user_id)
        active_id = active.connection_id if active else None

        results = []
        for c in conns:
            d = c.to_dict()
            d["is_active"] = (c.connection_id == active_id)
            results.append(d)

        return {
            "status": "success",
            "connections": results,
            "total_connections": len(results),
            "active_connection_id": active_id,
        }
    except Exception as e:
        return {"status": "error", "message": str(e), "connections": []}


@app.post("/connections")
@limiter.limit("20/minute")
def create_connection(
    req: MultiConnectionRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        from app.connectors.registry import get_connection_registry
        reg = get_connection_registry()

        cfg = req.dict(exclude_unset=True)
        if req.config and isinstance(req.config, dict):
            cfg.update(req.config)
        connector = reg.create_connector_from_config(user.user_id, cfg, auto_register=False)
        ok = connector.connect()

        if not ok:
            return {
                "status": "error",
                "message": connector.last_error or "Failed to connect to database.",
                "connection": connector.to_dict(),
            }

        # Only register connector on successful connection
        reg.register_connector(connector)

        if req.set_as_active:
            reg.set_active_connector(user.user_id, connector.connection_id)
            _activate(user, connector.connection_id)
            try:
                refresh_database_profile()
            except Exception:
                pass

        return {
            "status": "success",
            "message": f"Successfully connected to {connector.name}",
            "connection": connector.to_dict(include_schema=True),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/connections/upload-file")
@limiter.limit("10/minute")
async def upload_file_source(
    request: Request,
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    is_read_only: bool = Form(False),
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        filename = Path(file.filename).name
        ext = filename.split(".")[-1].lower() if "." in filename else ""

        if ext not in ("csv", "tsv", "xlsx", "xls", "json"):
            raise HTTPException(
                status_code=400,
                detail="Supported data file formats are: .csv, .tsv, .xlsx, .xls, .json",
            )

        if os.getenv("BGAI_DESKTOP_MODE") == "1":
            upload_dir = get_app_data_dir() / "database" / "files"
        else:
            upload_dir = Path(__file__).resolve().parents[2] / "database" / "files"
        upload_dir.mkdir(parents=True, exist_ok=True)
        target_path = upload_dir / f"{uuid.uuid4().hex[:8]}_{filename}"
        contents = await file.read()
        target_path.write_bytes(contents)

        from app.connectors.registry import get_connection_registry
        reg = get_connection_registry()

        connector_type = "csv" if ext in ("csv", "tsv") else ("excel" if ext in ("xlsx", "xls") else "json")
        disp_name = name or f"File: {filename}"
        delimiter = "\t" if ext == "tsv" else ","

        cfg = {
            "connector_type": connector_type,
            "name": disp_name,
            "file_path": str(target_path),
            "delimiter": delimiter,
            "is_read_only": is_read_only,
        }

        conn = reg.create_connector_from_config(user.user_id, cfg)
        ok = conn.connect()
        if not ok:
            return {"status": "error", "message": conn.last_error or "Failed to load data file"}

        reg.set_active_connector(user.user_id, conn.connection_id)
        _activate(user, conn.connection_id)

        return {
            "status": "success",
            "message": f"Data file '{filename}' loaded into SQL workspace successfully",
            "connection": conn.to_dict(include_schema=True),
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/connections/{connection_id}")
def get_connection_details(
    connection_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user, connection_id)
    try:
        from app.connectors.registry import get_connection_registry
        reg = get_connection_registry()
        conn = reg.get_connector(user.user_id, connection_id)
        if not conn:
            raise HTTPException(status_code=404, detail="Connection not found")

        active = reg.get_active_connector(user.user_id)
        d = conn.to_dict(include_schema=True)
        d["is_active"] = (active and active.connection_id == conn.connection_id)
        return {"status": "success", "connection": d}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/connections/test-config")
@limiter.limit("30/minute")
def test_connection_config_endpoint(
    req: MultiConnectionRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        from app.connectors.registry import get_connection_registry
        reg = get_connection_registry()
        cfg = req.dict(exclude_unset=True)
        if req.config and isinstance(req.config, dict):
            cfg.update(req.config)
        cfg["connection_id"] = f"test_{uuid.uuid4().hex[:8]}"
        cfg["name"] = "Temporary Test Connection"

        # Instantiate connector temporarily
        connector = reg.create_connector_from_config(user.user_id, cfg)
        try:
            test_res = connector.test_connection()
            return {"status": "success" if test_res.get("connected") else "error", "test": test_res}
        finally:
            reg.remove_connector(user.user_id, connector.connection_id)
    except Exception as e:
        return {"status": "error", "message": str(e), "test": {"connected": False, "error": str(e)}}


@app.post("/connections/{connection_id}/test")
def test_connection_endpoint(
    connection_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        from app.connectors.registry import get_connection_registry
        reg = get_connection_registry()
        conn = reg.get_connector(user.user_id, connection_id)
        if not conn:
            raise HTTPException(status_code=404, detail="Connection not found")
        test_res = conn.test_connection()
        return {"status": "success" if test_res.get("connected") else "error", "test": test_res}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/connections/{connection_id}/reconnect")
def reconnect_connection_endpoint(
    connection_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        from app.connectors.registry import get_connection_registry
        reg = get_connection_registry()
        conn = reg.get_connector(user.user_id, connection_id)
        if not conn:
            raise HTTPException(status_code=404, detail="Connection not found")
        conn.disconnect()
        ok = conn.connect()
        return {
            "status": "success" if ok else "error",
            "message": "Reconnected successfully" if ok else (conn.last_error or "Reconnect failed"),
            "connection": conn.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.patch("/connections/{connection_id}")
def update_connection_settings(
    connection_id: str,
    req: Dict[str, Any],
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        from app.connectors.registry import get_connection_registry
        reg = get_connection_registry()
        conn = reg.get_connector(user.user_id, connection_id)
        if not conn:
            raise HTTPException(status_code=404, detail="Connection not found")

        if "name" in req and req["name"]:
            conn.name = str(req["name"]).strip()
        if "is_read_only" in req:
            conn.is_read_only = bool(req["is_read_only"])

        return {"status": "success", "connection": conn.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.delete("/connections/{connection_id}")
def delete_connection_endpoint(
    connection_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        from app.connectors.registry import get_connection_registry
        reg = get_connection_registry()
        ok = reg.remove_connector(user.user_id, connection_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Connection not found")

        _activate(user)
        return {"status": "success", "message": f"Connection {connection_id} disconnected and removed."}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/connections/{connection_id}/active")
def set_active_connection_endpoint(
    connection_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        from app.connectors.registry import get_connection_registry
        reg = get_connection_registry()
        ok = reg.set_active_connector(user.user_id, connection_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Connection not found")

        conn = reg.get_connector(user.user_id, connection_id)
        if conn and conn.status.value != "connected":
            try:
                conn.connect()
            except Exception:
                pass

        _activate(user, connection_id)

        # Invalidate old connection schema caches
        try:
            from app.tools.get_schema import clear_engine_schema_cache
            clear_engine_schema_cache()
        except Exception:
            pass

        try:
            refresh_database_profile()
        except Exception:
            pass

        return {"status": "success", "active_connection_id": connection_id}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/connections/disconnect-all")
def disconnect_all_connections(user: AuthenticatedUser = Depends(get_current_user)):
    try:
        from app.connectors.registry import get_connection_registry
        reg = get_connection_registry()
        reg.disconnect_all(user.user_id)
        clear_user_context(user.user_id)
        clear_database_profile()
        return {"status": "success", "message": "All database connections disconnected successfully."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/connections/{connection_id}/query")
def execute_connection_query(
    connection_id: str,
    req: QueryRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user, connection_id)
    try:
        return execute_query(req.query, connection_id=connection_id)
    except Exception as e:
        return {"success": False, "columns": [], "rows": [], "error": str(e)}


@app.post("/cross-query")
@limiter.limit("30/minute")
def execute_cross_query(
    req: CrossQueryRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        from app.intelligence.cross_db import CrossDatabaseEngine
        res = CrossDatabaseEngine.process(
            user_id=user.user_id,
            message=req.message,
            selected_source_ids=req.selected_source_ids,
        )
        return {"status": "success", "result": res.to_dict()}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# =============================================================================
# COMPLETE DATABASE MANAGEMENT & CRUD API (PHASE 1 - 3)
# =============================================================================

class CreateRecordRequest(BaseModel):
    table: str
    data: Dict[str, Any]
    connection_id: Optional[str] = None


class UpdateRecordRequest(BaseModel):
    table: str
    primary_key: Dict[str, Any]
    data: Dict[str, Any]
    connection_id: Optional[str] = None


class DeleteRecordRequest(BaseModel):
    table: str
    primary_key: Dict[str, Any]
    connection_id: Optional[str] = None


class CreateEntityRequest(BaseModel):
    name: str
    definition: Optional[Dict[str, Any]] = None
    connection_id: Optional[str] = None


class RenameEntityRequest(BaseModel):
    old_name: str
    new_name: str
    connection_id: Optional[str] = None


class DropEntityRequest(BaseModel):
    name: str
    connection_id: Optional[str] = None


class CreateIndexRequest(BaseModel):
    table_name: str
    column_names: List[str]
    index_name: Optional[str] = None
    unique: bool = False
    connection_id: Optional[str] = None


class DropIndexRequest(BaseModel):
    table_name: str
    index_name: str
    connection_id: Optional[str] = None


@app.get("/database/records")
def get_database_records_endpoint(
    table: str,
    connection_id: Optional[str] = None,
    limit: int = 25,
    offset: int = 0,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    search: Optional[str] = None,
    request: Request = None,
    user: AuthenticatedUser = Depends(get_current_user),
):
    target_conn_id = connection_id or (request.headers.get("X-Connection-ID") if request else None)
    _activate(user, target_conn_id)
    try:
        from app.connectors.registry import get_connection_registry
        reg = get_connection_registry()
        conn = reg.get_connector(user.user_id, target_conn_id) if target_conn_id else None
        if not conn:
            conn = reg.get_active_connector(user.user_id)

        if conn:
            return conn.get_records(
                entity=table,
                limit=limit,
                offset=offset,
                sort_by=sort_by,
                sort_dir=sort_dir,
                search=search,
            )

        from app.intelligence.table_explorer import get_table_sample
        sample = get_table_sample(
            table_name=table,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_dir=sort_dir,
            search=search,
        )
        return {
            "success": True,
            "entity": table,
            "records": sample.get("rows", []),
            "columns": sample.get("columns", []),
            "total_count": sample.get("total_rows", 0),
            "limit": limit,
            "offset": offset,
            "primary_keys": [],
            "is_read_only": False,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "records": [], "columns": [], "total_count": 0}


@app.post("/database/records")
def create_database_record_endpoint(
    req: CreateRecordRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user, req.connection_id)
    try:
        from app.connectors.registry import get_connection_registry
        reg = get_connection_registry()
        conn = reg.get_connector(user.user_id, req.connection_id) if req.connection_id else None
        if not conn:
            conn = reg.get_active_connector(user.user_id)

        if not conn:
            raise HTTPException(status_code=400, detail="No active database connected.")

        result = conn.create_record(entity=req.table, data=req.data)

        # Audit Ledger (Phase 6)
        try:
            from app.governance.audit_ledger import get_audit_ledger
            get_audit_ledger().record_event(
                event_type="DATA_MUTATION",
                user_id=user.user_id,
                resource_id=req.table,
                details=f"Inserted record into '{req.table}' via {conn.name}",
            )
        except Exception:
            pass

        try:
            from app.intelligence.anomaly.detector import clear_cached_anomaly_report
            clear_cached_anomaly_report()
        except Exception:
            pass

        return {"status": "success", "result": result}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/database/records")
def update_database_record_endpoint(
    req: UpdateRecordRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user, req.connection_id)
    try:
        from app.connectors.registry import get_connection_registry
        reg = get_connection_registry()
        conn = reg.get_connector(user.user_id, req.connection_id) if req.connection_id else None
        if not conn:
            conn = reg.get_active_connector(user.user_id)

        if not conn:
            raise HTTPException(status_code=400, detail="No active database connected.")

        result = conn.update_record(entity=req.table, primary_key=req.primary_key, data=req.data)

        # Audit Ledger (Phase 6)
        try:
            from app.governance.audit_ledger import get_audit_ledger
            get_audit_ledger().record_event(
                event_type="DATA_MUTATION",
                user_id=user.user_id,
                resource_id=req.table,
                details=f"Updated record in '{req.table}' via {conn.name}: {req.primary_key}",
            )
        except Exception:
            pass

        try:
            from app.intelligence.anomaly.detector import clear_cached_anomaly_report
            clear_cached_anomaly_report()
        except Exception:
            pass

        return {"status": "success", "result": result}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/database/records")
def delete_database_record_endpoint(
    req: DeleteRecordRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user, req.connection_id)
    try:
        from app.connectors.registry import get_connection_registry
        reg = get_connection_registry()
        conn = reg.get_connector(user.user_id, req.connection_id) if req.connection_id else None
        if not conn:
            conn = reg.get_active_connector(user.user_id)

        if not conn:
            raise HTTPException(status_code=400, detail="No active database connected.")

        result = conn.delete_record(entity=req.table, primary_key=req.primary_key)

        # Audit Ledger (Phase 6)
        try:
            from app.governance.audit_ledger import get_audit_ledger
            get_audit_ledger().record_event(
                event_type="DATA_DELETION",
                user_id=user.user_id,
                resource_id=req.table,
                details=f"Deleted record in '{req.table}' via {conn.name}: {req.primary_key}",
            )
        except Exception:
            pass

        try:
            from app.intelligence.anomaly.detector import clear_cached_anomaly_report
            clear_cached_anomaly_report()
        except Exception:
            pass

        return {"status": "success", "result": result}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/database/structure/create")
def create_structure_endpoint(
    req: CreateEntityRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user, req.connection_id)
    try:
        from app.connectors.registry import get_connection_registry
        reg = get_connection_registry()
        conn = reg.get_connector(user.user_id, req.connection_id) if req.connection_id else None
        if not conn:
            conn = reg.get_active_connector(user.user_id)

        if not conn:
            raise HTTPException(status_code=400, detail="No active database connected.")

        result = conn.create_entity(req.name, req.definition)

        try:
            from app.governance.audit_ledger import get_audit_ledger
            get_audit_ledger().record_event(
                event_type="SCHEMA_MODIFICATION",
                user_id=user.user_id,
                resource_id=req.name,
                details=f"Created table/collection '{req.name}' on {conn.name}",
            )
        except Exception:
            pass

        return {"status": "success", "result": result}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/database/structure/rename")
def rename_structure_endpoint(
    req: RenameEntityRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user, req.connection_id)
    try:
        from app.connectors.registry import get_connection_registry
        reg = get_connection_registry()
        conn = reg.get_connector(user.user_id, req.connection_id) if req.connection_id else None
        if not conn:
            conn = reg.get_active_connector(user.user_id)

        if not conn:
            raise HTTPException(status_code=400, detail="No active database connected.")

        result = conn.rename_entity(req.old_name, req.new_name)

        try:
            from app.governance.audit_ledger import get_audit_ledger
            get_audit_ledger().record_event(
                event_type="SCHEMA_MODIFICATION",
                user_id=user.user_id,
                resource_id=req.old_name,
                details=f"Renamed '{req.old_name}' to '{req.new_name}' on {conn.name}",
            )
        except Exception:
            pass

        return {"status": "success", "result": result}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/database/structure/drop")
def drop_structure_endpoint(
    req: DropEntityRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user, req.connection_id)
    try:
        from app.connectors.registry import get_connection_registry
        reg = get_connection_registry()
        conn = reg.get_connector(user.user_id, req.connection_id) if req.connection_id else None
        if not conn:
            conn = reg.get_active_connector(user.user_id)

        if not conn:
            raise HTTPException(status_code=400, detail="No active database connected.")

        result = conn.drop_entity(req.name)

        try:
            from app.governance.audit_ledger import get_audit_ledger
            get_audit_ledger().record_event(
                event_type="SCHEMA_MODIFICATION",
                user_id=user.user_id,
                resource_id=req.name,
                details=f"Dropped table/collection '{req.name}' on {conn.name}",
            )
        except Exception:
            pass

        return {"status": "success", "result": result}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/database/indexes/create")
def create_index_endpoint(
    req: CreateIndexRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user, req.connection_id)
    try:
        from app.connectors.registry import get_connection_registry
        reg = get_connection_registry()
        conn = reg.get_connector(user.user_id, req.connection_id) if req.connection_id else None
        if not conn:
            conn = reg.get_active_connector(user.user_id)

        if not conn:
            raise HTTPException(status_code=400, detail="No active database connected.")

        result = conn.create_index(req.table_name, req.column_names, req.index_name, req.unique)

        try:
            from app.governance.audit_ledger import get_audit_ledger
            get_audit_ledger().record_event(
                event_type="SCHEMA_MODIFICATION",
                user_id=user.user_id,
                resource_id=req.table_name,
                details=f"Created index on '{req.table_name}' ({', '.join(req.column_names)}) on {conn.name}",
            )
        except Exception:
            pass

        return {"status": "success", "result": result}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/database/indexes/drop")
def drop_index_endpoint(
    req: DropIndexRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user, req.connection_id)
    try:
        from app.connectors.registry import get_connection_registry
        reg = get_connection_registry()
        conn = reg.get_connector(user.user_id, req.connection_id) if req.connection_id else None
        if not conn:
            conn = reg.get_active_connector(user.user_id)

        if not conn:
            raise HTTPException(status_code=400, detail="No active database connected.")

        result = conn.drop_index(req.table_name, req.index_name)

        try:
            from app.governance.audit_ledger import get_audit_ledger
            get_audit_ledger().record_event(
                event_type="SCHEMA_MODIFICATION",
                user_id=user.user_id,
                resource_id=req.table_name,
                details=f"Dropped index '{req.index_name}' on '{req.table_name}' on {conn.name}",
            )
        except Exception:
            pass

        return {"status": "success", "result": result}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/optimize")
def optimize_sql_endpoint(req: OptimizationRequest, user: AuthenticatedUser = Depends(get_current_user)):
    _activate(user)
    try:
        return optimize_sql(req.sql)
    except Exception as e:
        return {"status": "error", "message": str(e), "original_query": req.sql, "optimized_query": req.sql, "improvements": []}


@app.get("/dashboard")
def dashboard(
    request: Request,
    connection_id: Optional[str] = None,
    user: AuthenticatedUser = Depends(get_current_user),
):
    target_conn_id = connection_id or request.headers.get("X-Connection-ID")
    _activate(user, target_conn_id)
    try:
        return get_dashboard_data()
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/analytics")
def analytics(user: AuthenticatedUser = Depends(get_current_user)):
    _activate(user)
    try:
        return get_analytics_data()
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/relationship-graph")
def relationship_graph(user: AuthenticatedUser = Depends(get_current_user)):
    _activate(user)
    try:
        return get_relationship_graph()
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/suggestions")
def suggestions(user: AuthenticatedUser = Depends(get_current_user)):
    _activate(user)
    try:
        s = get_schema()
        profile = get_database_profile()
        db_ctx = profile.to_context() if profile and profile.analyzed else ""
        return {"suggestions": generate_suggestions(s, db_ctx)}
    except Exception as e:
        return {"status": "error", "message": str(e), "suggestions": []}


@app.get("/analyze-business")
@app.post("/analyze-business")
def analyze_business_endpoint(user: AuthenticatedUser = Depends(get_current_user)):
    _activate(user)
    try:
        from app.tools.ai_analyst import analyze_business
        return analyze_business()
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/backup")
@limiter.limit("5/minute")
def backup_database(request: Request, user: AuthenticatedUser = Depends(get_current_user)):
    _activate(user)
    try:
        result = create_backup()
        if isinstance(result, dict):
            result.pop("backup_path", None)
            result.pop("path", None)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/restore")
@limiter.limit("3/minute")
async def restore_database(
    request: Request,
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        safe_name = Path(file.filename).name
        if not safe_name.lower().endswith(".db"):
            raise HTTPException(status_code=400, detail="Only .db files are supported for restore.")

        backup_dir = get_backup_dir()
        backup_path = backup_dir / safe_name
        contents = await file.read()
        backup_path.write_bytes(contents)

        result = restore_backup(backup_path)
        return result
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/download-backup")
def download_backup(user: AuthenticatedUser = Depends(get_current_user)):
    _activate(user)
    try:
        backup_dir = get_backup_dir()
        backups = sorted(backup_dir.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not backups:
            return {"status": "error", "message": "No backups found"}
        latest = backups[0]
        return FileResponse(path=str(latest), filename=latest.name, media_type="application/octet-stream")
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/intelligence")
@app.get("/intelligence/report")
@limiter.limit("20/minute")
def intelligence_report_endpoint(
    request: Request,
    force_refresh: bool = False,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        from app.intelligence.scanner import run_database_intelligence_scan
        report = run_database_intelligence_scan(force_refresh=force_refresh)
        if report is None:
            return {"status": "error", "message": "No database connected.", "report": None}
        return {"status": "success", "report": report.to_dict() if hasattr(report, "to_dict") else report}
    except Exception as e:
        return {"status": "error", "message": str(e), "report": None}


@app.post("/intelligence/scan")
@limiter.limit("10/minute")
def intelligence_scan_post(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        from app.intelligence.scanner import run_database_intelligence_scan
        report = run_database_intelligence_scan(force_refresh=True)
        if report is None:
            return {"status": "error", "message": "No database connected.", "report": None}
        return {"status": "success", "report": report.to_dict() if hasattr(report, "to_dict") else report}
    except Exception as e:
        return {"status": "error", "message": str(e), "report": None}


@app.get("/intelligence/table/{table_name}")
def get_table_profile_endpoint(
    table_name: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        from app.intelligence.table_explorer import get_table_profile
        profile = get_table_profile(table_name)
        return {"status": "success", "table": profile}
    except Exception as e:
        return {"status": "error", "message": str(e), "table": None}


@app.get("/intelligence/table/{table_name}/sample")
def get_table_sample_endpoint(
    table_name: str,
    limit: int = 50,
    offset: int = 0,
    sort_by: str | None = None,
    sort_dir: str = "asc",
    search: str | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        from app.intelligence.table_explorer import get_table_sample
        sample = get_table_sample(
            table_name=table_name,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_dir=sort_dir,
            search=search,
        )
        return {"status": "success", "sample": sample}
    except Exception as e:
        return {"status": "error", "message": str(e), "sample": None}


@app.get("/intelligence/column/{table_name}/{column_name}")
def get_column_profile_endpoint(
    table_name: str,
    column_name: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        from app.intelligence.table_explorer import get_column_profile
        profile = get_column_profile(table_name, column_name)
        return {"status": "success", "column": profile}
    except Exception as e:
        return {"status": "error", "message": str(e), "column": None}


@app.post("/analyst/ask")
@limiter.limit("30/minute")
def analyst_ask_endpoint(
    request: Request,
    req: AnalystAskRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        from app.intelligence.ai_analyst.analyst import run_ai_analysis
        result = run_ai_analysis(
            question=req.question,
            target_table=req.table,
            target_metric=req.metric,
        )
        return {"status": "success", "analysis": result.to_dict() if hasattr(result, "to_dict") else result}
    except Exception as e:
        return {"status": "error", "message": str(e), "analysis": None}


@app.get("/analyst/quick-actions")
def analyst_quick_actions_endpoint(
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        from app.intelligence.ai_analyst.analyst import generate_quick_actions
        actions = generate_quick_actions()
        return {"status": "success", "actions": [a.to_dict() if hasattr(a, "to_dict") else a for a in actions]}
    except Exception as e:
        return {"status": "error", "message": str(e), "actions": []}


@app.get("/forecasting/candidates")
def forecasting_candidates_endpoint(
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        from app.intelligence.forecasting.detector import detect_forecast_candidates
        candidates, message = detect_forecast_candidates()
        return {
            "status": "success" if candidates else "no_candidates",
            "candidates": [c.to_dict() if hasattr(c, "to_dict") else c for c in candidates],
            "message": message,
        }
    except Exception as e:
        return {"status": "error", "candidates": [], "message": str(e)}


@app.post("/forecasting/generate")
@limiter.limit("20/minute")
def forecasting_generate_endpoint(
    request: Request,
    req: ForecastRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        from app.intelligence.forecasting.forecaster import run_forecast
        forecast = run_forecast(
            table=req.table,
            date_column=req.date_column,
            metric_column=req.metric_column,
            frequency=req.frequency,
            horizon=req.horizon,
            aggregation=req.aggregation,
        )
        return {"status": "success", "forecast": forecast.to_dict() if hasattr(forecast, "to_dict") else forecast}
    except Exception as e:
        return {"status": "error", "message": str(e), "forecast": None}


@app.get("/anomaly/report")
@limiter.limit("20/minute")
def anomaly_report_endpoint(
    request: Request,
    force_refresh: bool = False,
    connection_id: str | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
):
    target_conn_id = connection_id or request.headers.get("X-Connection-ID")
    _activate(user, target_conn_id)
    try:
        from app.database.database_manager import get_engine, get_current_db_type
        engine = get_engine()
        db_type = get_current_db_type()
        if engine is None or db_type == "none":
            return {
                "status": "error",
                "scan_state": "not_scanned",
                "message": "No database currently connected.",
                "report": None,
            }

        from app.intelligence.anomaly.detector import detect_anomalies
        report = detect_anomalies(force_refresh=force_refresh)
        rep_dict = report.to_dict() if hasattr(report, "to_dict") else report
        tot = rep_dict.get("total_anomalies", 0) if isinstance(rep_dict, dict) else 0
        scan_state = "completed_with_findings" if tot > 0 else "completed_no_findings"
        return {"status": "success", "scan_state": scan_state, "report": rep_dict}
    except Exception as e:
        return {"status": "error", "scan_state": "scan_failed", "message": str(e), "report": None}


@app.get("/anomaly/summary")
def anomaly_summary_endpoint(
    request: Request,
    force_refresh: bool = False,
    connection_id: str | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
):
    target_conn_id = connection_id or request.headers.get("X-Connection-ID")
    _activate(user, target_conn_id)
    try:
        from app.database.database_manager import get_engine, get_current_db_type
        engine = get_engine()
        db_type = get_current_db_type()
        if engine is None or db_type == "none":
            return {
                "status": "success",
                "scan_state": "not_scanned",
                "critical_count": 0,
                "warning_count": 0,
                "info_count": 0,
                "total_count": 0,
                "total_anomalies": 0,
                "scan_timestamp": "",
                "database_name": "Not Connected",
                "database_type": "none",
                "clean_tables": [],
                "anomalies": [],
            }

        from app.intelligence.anomaly.detector import detect_anomalies
        report = detect_anomalies(force_refresh=force_refresh)
        rep_dict = report.to_dict() if hasattr(report, "to_dict") else report
        crit = rep_dict.get("critical_count", 0) if isinstance(rep_dict, dict) else 0
        warn = rep_dict.get("warning_count", 0) if isinstance(rep_dict, dict) else 0
        info = rep_dict.get("info_count", 0) if isinstance(rep_dict, dict) else 0
        tot = rep_dict.get("total_anomalies", 0) if isinstance(rep_dict, dict) else 0
        scan_state = "completed_with_findings" if tot > 0 else "completed_no_findings"

        return {
            "status": "success",
            "scan_state": scan_state,
            "critical_count": crit,
            "warning_count": warn,
            "info_count": info,
            "total_count": tot,
            "total_anomalies": tot,
            "scan_timestamp": rep_dict.get("scan_timestamp", "") if isinstance(rep_dict, dict) else "",
            "database_name": rep_dict.get("database_name", "Connected DB") if isinstance(rep_dict, dict) else "Connected DB",
            "database_type": rep_dict.get("database_type", db_type) if isinstance(rep_dict, dict) else db_type,
            "clean_tables": rep_dict.get("clean_tables", []) if isinstance(rep_dict, dict) else [],
            "anomalies": rep_dict.get("anomalies", []) if isinstance(rep_dict, dict) else [],
        }
    except Exception as e:
        return {
            "status": "error",
            "scan_state": "scan_failed",
            "critical_count": 0,
            "warning_count": 0,
            "info_count": 0,
            "total_count": 0,
            "total_anomalies": 0,
            "scan_timestamp": "",
            "database_name": "unknown",
            "database_type": "none",
            "clean_tables": [],
            "anomalies": [],
            "error": str(e),
        }


@app.get("/intelligence/insights")
@limiter.limit("20/minute")
def business_insights_endpoint(
    request: Request,
    force_refresh: bool = False,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        from app.intelligence.business_intelligence.insight_engine import generate_business_intelligence_report
        report = generate_business_intelligence_report(user_id=user.user_id, force_refresh=force_refresh)
        return report.to_dict()
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "database_name": "unknown",
            "database_type": "none",
            "summary": {"total_insights": 0, "critical": 0, "warning": 0, "info": 0, "opportunity": 0},
            "insights": [],
            "generated_at": "",
        }


@app.post("/intelligence/insights/refresh")
@limiter.limit("10/minute")
def business_insights_refresh_endpoint(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        from app.intelligence.business_intelligence.insight_engine import generate_business_intelligence_report
        report = generate_business_intelligence_report(user_id=user.user_id, force_refresh=True)
        return report.to_dict()
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "database_name": "unknown",
            "database_type": "none",
            "summary": {"total_insights": 0, "critical": 0, "warning": 0, "info": 0, "opportunity": 0},
            "insights": [],
            "generated_at": "",
        }


# ── Phase 8.2 Multi-Table Business Intelligence Endpoints ───────────────────

class BiQueryRequest(BaseModel):
    question: str


@app.get("/intelligence/relationships")
def get_relationships_endpoint(user: AuthenticatedUser = Depends(get_current_user)):
    _activate(user)
    try:
        from app.database.database_manager import get_engine, get_current_db_type
        from app.intelligence.schema_analyzer import analyze_schema
        from app.intelligence.business_intelligence.join_path import build_relationship_graph
        engine = get_engine()
        db_type = get_current_db_type()
        if engine is None or db_type == "none":
            return {"status": "error", "message": "No database connected.", "relationships": []}
        schema_info = analyze_schema(engine, db_type)
        graph = build_relationship_graph(schema_info)
        rel_list = []
        for tbl, edges in graph.items():
            for edge in edges:
                if not edge.is_reverse:
                    rel_list.append(edge.to_dict())
        return {"status": "success", "relationships": rel_list, "total": len(rel_list)}
    except Exception as e:
        return {"status": "error", "message": str(e), "relationships": []}


@app.get("/intelligence/join-paths")
def get_join_paths_endpoint(
    source: str | None = None,
    target: str | None = None,
    max_depth: int = 3,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        from app.database.database_manager import get_engine, get_current_db_type
        from app.intelligence.schema_analyzer import analyze_schema
        from app.intelligence.business_intelligence.join_path import (
            build_relationship_graph,
            find_join_path,
            find_all_join_paths,
        )
        engine = get_engine()
        db_type = get_current_db_type()
        if engine is None or db_type == "none":
            return {"status": "error", "message": "No database connected.", "paths": []}
        schema_info = analyze_schema(engine, db_type)
        graph = build_relationship_graph(schema_info)
        if source and target:
            path = find_join_path(graph, source, target, max_depth=max_depth, db_type=db_type)
            return {"status": "success", "paths": [path.to_dict()] if path else []}
        all_paths = find_all_join_paths(graph, max_depth=max_depth, db_type=db_type)
        return {"status": "success", "paths": [p.to_dict() for p in all_paths]}
    except Exception as e:
        return {"status": "error", "message": str(e), "paths": []}


@app.post("/intelligence/bi-query")
@limiter.limit("30/minute")
def bi_query_endpoint(
    request: Request,
    req: BiQueryRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        from app.intelligence.business_intelligence.multitable_engine import query_multitable_bi
        res = query_multitable_bi(req.question, user_id=user.user_id)
        return res
    except Exception as e:
        return {"status": "error", "message": str(e), "data": None, "lineage": [], "sql": None}


# ── Phase 5 Agent API ──────────────────────────────────────────────────────────

from app.agents.registry import get_available_agents, run_agent_task, route_to_agent
from app.agents.audit import (
    get_action, list_actions, confirm_and_execute_action,
    cancel_action, get_current_db_identity,
)
from app.agents.models import AgentTask


@app.get("/agents")
def list_agents(user: AuthenticatedUser = Depends(get_current_user)):
    _activate(user)
    try:
        agents = get_available_agents()
        return {"agents": [agent.to_dict() for agent in agents]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/agents/run")
@limiter.limit("20/minute")
def run_agent_endpoint(
    req: AgentRunRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        result = run_agent_task(req.task, req.agent_name, req.context or {})

        if result.proposed_action is not None:
            try:
                ctx = get_user_context(user.user_id)
                from app.agents.audit_db import store_action_persistent
                store_action_persistent(result.proposed_action, user.user_id, ctx.context_id)
            except Exception:
                pass

        return {"result": result.to_dict()}
    except Exception as e:
        logging.getLogger("bgai").error("Agent run error: %s", str(e), exc_info=True)
        return {"status": "error", "message": str(e)}


@app.post("/agents/route")
def route_agent(req: AgentRunRequest, user: AuthenticatedUser = Depends(get_current_user)):
    _activate(user)
    try:
        agent_name = route_to_agent(req.task)
        return {"agent": agent_name, "task": req.task}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/agent-actions")
def list_agent_actions(user: AuthenticatedUser = Depends(get_current_user)):
    _activate(user)
    try:
        curr_identity = get_current_db_identity()
        if curr_identity == "none":
            return {"actions": []}
        actions = list_actions(db_identity_only=True)
        return {"actions": [a.to_dict() for a in actions if a.database_identity == curr_identity]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/agent-actions/{action_id}")
def get_agent_action(action_id: str, user: AuthenticatedUser = Depends(get_current_user)):
    _activate(user)
    try:
        action = get_action(action_id)
        if action is None:
            raise HTTPException(status_code=404, detail="Action not found.")
        curr_identity = get_current_db_identity()
        if action.database_identity != curr_identity:
            raise HTTPException(status_code=403, detail="Access denied.")
        return {"action": action.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/agent-actions/{action_id}/confirm")
def confirm_agent_action(action_id: str, user: AuthenticatedUser = Depends(get_current_user)):
    _activate(user)
    try:
        action = get_action(action_id)
        if action is None:
            raise HTTPException(status_code=404, detail="Action not found.")

        curr_identity = get_current_db_identity()
        if action.database_identity != curr_identity:
            raise HTTPException(status_code=403, detail="Access denied: action belongs to a different database context.")

        try:
            from app.agents.audit_db import is_action_expired
            if is_action_expired(action_id):
                action.status = "EXPIRED"
                return {"success": False, "error": "Action has expired. Please create a new action plan."}
        except Exception:
            pass

        result = confirm_and_execute_action(action_id)

        if result.get("success"):
            try:
                from app.security.user_cache import (
                    cache_delete, CACHE_INSIGHTS_REPORT, CACHE_ANALYTICS, CACHE_DATABASE_PROFILE
                )
                cache_delete(user.user_id, CACHE_INSIGHTS_REPORT)
                cache_delete(user.user_id, CACHE_ANALYTICS)
                cache_delete(user.user_id, CACHE_DATABASE_PROFILE)
            except Exception:
                pass

        try:
            action_updated = get_action(action_id)
            if action_updated:
                from app.agents.audit_db import update_action_persistent
                update_action_persistent(action_updated)
        except Exception:
            pass

        return result
    except HTTPException:
        raise
    except Exception as e:
        logging.getLogger("bgai").error("Confirm action error: %s", str(e), exc_info=True)
        return {"status": "error", "message": str(e)}


@app.post("/agent-actions/{action_id}/cancel")
def cancel_agent_action(action_id: str, user: AuthenticatedUser = Depends(get_current_user)):
    _activate(user)
    try:
        action = get_action(action_id)
        if action is None:
            raise HTTPException(status_code=404, detail="Action not found.")

        curr_identity = get_current_db_identity()
        if action.database_identity != curr_identity:
            raise HTTPException(status_code=403, detail="Access denied.")

        result = cancel_action(action_id)

        try:
            action_updated = get_action(action_id)
            if action_updated:
                from app.agents.audit_db import update_action_persistent
                update_action_persistent(action_updated)
        except Exception:
            pass

        return result
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/audit-history")
def audit_history(user: AuthenticatedUser = Depends(get_current_user)):
    try:
        from app.agents.audit_db import list_audit_events
        return {"events": list_audit_events(user.user_id)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/clear-db")
def clear_db(user: AuthenticatedUser = Depends(get_current_user)):
    try:
        from app.database.db import get_database_path
        db_path = get_database_path()
        if db_path.exists():
            db_path.unlink()
        return {"status": "success", "message": "Database cleared"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── Phase 8.3 Proactive Intelligence Endpoints ───────────────────────────────

from datetime import datetime
from app.intelligence.proactive.models import AlertStatus
from app.intelligence.proactive.alert_store import (
    get_alerts,
    get_alert,
    update_alert_status,
)
from app.intelligence.proactive.evaluator import evaluate_proactive_metrics
from app.intelligence.proactive.action_bridge import prepare_action_proposal


class ProactiveEvaluateRequest(BaseModel):
    force: bool = False


@app.get("/proactive/alerts")
def list_proactive_alerts(
    status: str | None = None,
    severity: str | None = None,
    category: str | None = None,
    limit: int = 50,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        bounded_limit = max(1, min(limit, 100))
        alerts = get_alerts(
            user_id=user.user_id,
            status=status,
            severity=severity,
            category=category,
            limit=bounded_limit,
        )
        if not alerts:
            from app.database.database_manager import get_engine, get_current_db_type
            engine = get_engine()
            db_type = get_current_db_type()
            if engine is not None and db_type != "none":
                try:
                    evaluate_proactive_metrics(
                        engine=engine,
                        db_type=db_type,
                        user_id=user.user_id,
                        deduplicate=True,
                        save_to_store=True,
                    )
                    alerts = get_alerts(
                        user_id=user.user_id,
                        status=status,
                        severity=severity,
                        category=category,
                        limit=bounded_limit,
                    )
                except Exception:
                    pass

        return {
            "alerts": [a.to_dict() for a in alerts],
            "count": len(alerts),
        }
    except Exception as e:
        return {"status": "error", "message": str(e), "alerts": [], "count": 0}


@app.post("/proactive/evaluate")
@limiter.limit("10/minute")
def evaluate_proactive_intelligence(
    request: Request,
    req: ProactiveEvaluateRequest | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        engine = get_engine()
        db_type = get_current_db_type()
        if engine is None or db_type == "none":
            return {
                "status": "disconnected",
                "message": "No database currently connected.",
                "alerts": [],
                "count": 0,
                "database_name": "none",
                "database_type": "none",
                "timestamp": datetime.utcnow().isoformat(),
            }

        res = evaluate_proactive_metrics(
            engine=engine,
            db_type=db_type,
            user_id=user.user_id,
            deduplicate=True,
            save_to_store=True,
        )

        db_info = get_database_connection_info()
        db_name = db_info.get("database") or "database"
        alerts = res.get("alerts", [])

        return {
            "status": res.get("status", "success"),
            "alerts": alerts,
            "count": len(alerts),
            "database_name": db_name,
            "database_type": db_type,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logging.getLogger("bgai.proactive").error("Proactive evaluate error: %s", str(e), exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "alerts": [],
            "count": 0,
            "timestamp": datetime.utcnow().isoformat(),
        }


@app.get("/proactive/alerts/{alert_id}")
def get_proactive_alert(
    alert_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        alert = get_alert(alert_id, user_id=user.user_id)
        if alert is None:
            raise HTTPException(status_code=404, detail="Alert not found")
        return {"alert": alert.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "message": str(e), "alert": None}


@app.post("/proactive/alerts/{alert_id}/acknowledge")
def acknowledge_proactive_alert(
    alert_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        alert = get_alert(alert_id, user_id=user.user_id)
        if alert is None:
            raise HTTPException(status_code=404, detail="Alert not found")
        if alert.status == AlertStatus.RESOLVED:
            raise HTTPException(status_code=400, detail="Cannot acknowledge a resolved alert")
        if alert.status == AlertStatus.ACKNOWLEDGED:
            return {"alert": alert.to_dict()}
        updated = update_alert_status(alert_id, AlertStatus.ACKNOWLEDGED, user_id=user.user_id)
        return {"alert": updated.to_dict() if updated else alert.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "message": str(e), "alert": None}


@app.post("/proactive/alerts/{alert_id}/resolve")
def resolve_proactive_alert(
    alert_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        alert = get_alert(alert_id, user_id=user.user_id)
        if alert is None:
            raise HTTPException(status_code=404, detail="Alert not found")
        updated = update_alert_status(alert_id, AlertStatus.RESOLVED, user_id=user.user_id)
        return {"alert": updated.to_dict() if updated else alert.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "message": str(e), "alert": None}


@app.post("/proactive/alerts/{alert_id}/propose-action")
def propose_action_for_proactive_alert(
    alert_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        alert = get_alert(alert_id, user_id=user.user_id)
        if alert is None:
            raise HTTPException(status_code=404, detail="Alert not found")
        engine = get_engine()
        db_type = get_current_db_type()
        proposal = prepare_action_proposal(alert, user_id=user.user_id, engine=engine, db_type=db_type)
        if proposal is None:
            return {
                "available": False,
                "reason": "No supported safe action is available for this alert.",
            }
        return {
            "available": True,
            "proposal": proposal,
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"available": False, "reason": str(e)}


# ── Phase 8.4 AI Decision & Planning Intelligence Endpoints ────────────────

class DecisionQueryRequest(BaseModel):
    question: str


@app.post("/intelligence/decision")
@limiter.limit("10/minute")
def decision_intelligence_endpoint(
    request: Request,
    body: DecisionQueryRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        from app.intelligence.decision.decision_engine import run_decision_analysis
        from app.database.database_manager import get_engine, get_current_db_type

        engine = get_engine()
        db_type = get_current_db_type()

        if engine is None or db_type == "none":
            return {
                "status": "disconnected",
                "message": "No active database connected. Please connect a database to run decision intelligence.",
                "question": body.question,
                "problem_statement": "No database connected.",
                "findings": [],
                "evidence": [],
                "hypotheses": [],
                "recommended_investigations": [],
                "decision_plan": [],
                "confidence": None,
                "source_tables": [],
            }

        analysis = run_decision_analysis(
            question=body.question,
            user_id=user.user_id,
            engine=engine,
            db_type=db_type,
        )
        return analysis.to_dict()
    except Exception as e:
        import traceback
        logging.getLogger("bgai").error("Decision analysis error: %s\n%s", str(e), traceback.format_exc())
        return {
            "status": "error",
            "message": str(e),
            "question": body.question,
            "problem_statement": f"Error running decision analysis: {str(e)}",
            "findings": [],
            "evidence": [],
            "hypotheses": [],
            "recommended_investigations": [],
            "decision_plan": [],
            "confidence": None,
            "source_tables": [],
        }


# ── Phase 8.5 Outcome & Learning Intelligence Endpoints ─────────────────────

class RecordOutcomeRequest(BaseModel):
    action_type: str = "GENERAL"
    expected_outcome: str = ""
    actual_outcome: str = ""
    status: str = "UNKNOWN"
    decision_id: Optional[str] = None
    question: Optional[str] = None
    action_id: Optional[str] = None
    plan_step: Optional[int] = None
    evidence: Optional[Any] = None
    notes: Optional[str] = None


class RecordFeedbackRequest(BaseModel):
    target_type: str = "DECISION"
    target_id: Optional[str] = None
    question: Optional[str] = None
    useful: Optional[bool] = None
    accepted: Optional[bool] = None
    comment: Optional[str] = None


@app.post("/intelligence/outcomes")
@limiter.limit("20/minute")
def record_outcome_endpoint(
    request: Request,
    body: RecordOutcomeRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        from app.intelligence.learning.models import OutcomeRecord
        from app.intelligence.learning.outcome_store import save_outcome

        record = OutcomeRecord(
            user_id=user.user_id,
            action_type=body.action_type,
            expected_outcome=body.expected_outcome,
            actual_outcome=body.actual_outcome,
            status=body.status,
            decision_id=body.decision_id,
            question=body.question,
            action_id=body.action_id,
            plan_step=body.plan_step,
            evidence=body.evidence,
            notes=body.notes,
        )
        saved = save_outcome(record)
        return {"status": "success", "outcome": saved.to_dict()}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/intelligence/outcomes")
@limiter.limit("30/minute")
def list_outcomes_endpoint(
    request: Request,
    limit: int = 50,
    action_type: Optional[str] = None,
    status: Optional[str] = None,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        from app.intelligence.learning.outcome_store import list_outcomes
        outcomes = list_outcomes(user_id=user.user_id, limit=limit, action_type=action_type, status=status)
        return {"status": "success", "outcomes": [o.to_dict() for o in outcomes], "total": len(outcomes)}
    except Exception as e:
        return {"status": "error", "message": str(e), "outcomes": [], "total": 0}


@app.post("/intelligence/feedback")
@limiter.limit("20/minute")
def record_feedback_endpoint(
    request: Request,
    body: RecordFeedbackRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        from app.intelligence.learning.feedback import record_user_feedback
        saved = record_user_feedback(
            user_id=user.user_id,
            target_type=body.target_type,
            target_id=body.target_id,
            question=body.question,
            useful=body.useful,
            accepted=body.accepted,
            comment=body.comment,
        )
        return {"status": "success", "feedback": saved.to_dict()}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/intelligence/learning-summary")
@limiter.limit("20/minute")
def learning_summary_endpoint(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        from app.intelligence.learning.outcome_engine import synthesize_learning_summary
        summary = synthesize_learning_summary(user_id=user.user_id)
        return {"status": "success", "summary": summary.to_dict()}
    except Exception as e:
        return {"status": "error", "message": str(e), "summary": None}


# ── Phase 8.6: Continuous Intelligence & Executive Monitoring ─────────────────
# Per-user in-memory cache: { user_id -> MonitoringReport }
# No persistence needed; each scan returns fresh data.
import threading as _threading
_monitoring_cache: Dict[str, Any] = {}
_monitoring_lock = _threading.Lock()


@app.post("/intelligence/monitoring/evaluate")
@limiter.limit("5/minute")
def monitoring_evaluate_endpoint(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Trigger an on-demand intelligence scan for the connected database."""
    _activate(user)
    try:
        engine = get_engine()
        db_type = get_current_db_type()
        if engine is None or db_type == "none":
            return {
                "status": "disconnected",
                "message": "No database is currently connected. Please connect a database first.",
                "report": None,
            }
        from app.intelligence.monitoring.monitor_engine import run_monitoring_scan
        report = run_monitoring_scan(engine=engine, db_type=db_type, user_id=user.user_id)
        with _monitoring_lock:
            _monitoring_cache[user.user_id] = report
        return {"status": "success", "report": report.to_dict()}
    except Exception as e:
        return {"status": "error", "message": str(e), "report": None}


@app.get("/intelligence/monitoring/status")
@limiter.limit("20/minute")
def monitoring_status_endpoint(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Return the last scan timestamp and item counts for the authenticated user."""
    _activate(user)
    try:
        with _monitoring_lock:
            report = _monitoring_cache.get(user.user_id)
        if report is None:
            return {
                "status": "no_scan",
                "message": "No monitoring scan has been run yet. Use POST /intelligence/monitoring/evaluate.",
                "last_scanned_at": None,
                "item_counts": None,
            }
        es = report.executive_summary
        return {
            "status": "ok",
            "last_scanned_at": report.scanned_at,
            "db_type": report.db_type,
            "scan_duration_ms": report.scan_duration_ms,
            "item_counts": {
                "total": len(report.items),
                "critical": es.critical_count if es else 0,
                "warning": es.warning_count if es else 0,
                "info": es.info_count if es else 0,
            },
            "overall_status": es.overall_status if es else "unknown",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/intelligence/monitoring/summary")
@limiter.limit("20/minute")
def monitoring_summary_endpoint(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Return the executive summary from the last scan for the authenticated user."""
    _activate(user)
    try:
        with _monitoring_lock:
            report = _monitoring_cache.get(user.user_id)
        if report is None:
            return {
                "status": "no_scan",
                "message": "No monitoring scan has been run yet.",
                "summary": None,
            }
        return {
            "status": "success",
            "summary": report.executive_summary.to_dict() if report.executive_summary else None,
            "items": [i.to_dict() for i in report.items],
            "scanned_at": report.scanned_at,
        }
    except Exception as e:
        return {"status": "error", "message": str(e), "summary": None}


# ── Phase 8.7: Root-Cause Investigation ───────────────────────────────────────
from app.intelligence.investigation.investigator import investigate_signal

class InvestigateSignalRequest(BaseModel):
    signal_id: Optional[str] = None
    signal_title: Optional[str] = None
    signal_type: Optional[str] = None
    metric_name: Optional[str] = None
    source_table: Optional[str] = None
    direction: Optional[str] = "drop"
    magnitude_pct: Optional[float] = None
    detected_at: Optional[str] = None
    current_value: Optional[float] = None
    previous_value: Optional[float] = None

@app.post("/intelligence/investigate")
@limiter.limit("10/minute")
def investigate_signal_endpoint(
    req: InvestigateSignalRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Deep-dive investigation of an observed business anomaly, drop, or spike."""
    _activate(user)
    try:
        # Check signal ownership if signal_id is provided
        if req.signal_id:
            from app.intelligence.proactive.alert_store import _get_session, AlertRecord
            session = _get_session()
            try:
                rec = session.query(AlertRecord).filter(AlertRecord.alert_id == req.signal_id).first()
                if rec and rec.user_id != user.user_id:
                    raise HTTPException(status_code=403, detail="Forbidden: You do not own this alert.")
            finally:
                session.close()

        from app.database.database_manager import get_engine
        engine = get_engine()
        if engine is None:
            return {
                "status": "disconnected",
                "message": "No active database connection.",
                "investigation": None,
            }

        result = investigate_signal(
            engine=engine,
            signal_id=req.signal_id,
            signal_title=req.signal_title,
            signal_type=req.signal_type,
            metric_name=req.metric_name,
            source_table=req.source_table,
            direction=req.direction or "drop",
            magnitude_pct=req.magnitude_pct,
            detected_at=req.detected_at,
            current_value=req.current_value,
            previous_value=req.previous_value,
            user_id=user.user_id,
        )
        return {
            "status": "success" if not result.insufficient_evidence else "insufficient_evidence",
            "investigation": result.to_dict(),
        }
    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logging.error(f"Investigation error: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "investigation": None,
        }


# ── Phase 8.8: Controlled Business Actions & Action Intelligence ──────────────
from app.intelligence.actions import (
    build_action_proposal,
    calculate_impact_preview,
    generate_confirmation_token,
    execute_action,
    save_action,
    get_action as get_action_proposal,
    list_actions as list_action_proposals,
    ActionStatus,
    ActionRisk,
    ActionExecutionConflict,
    ActionExecutionError,
)

def _get_active_db_identity() -> str:
    from app.database.connection_context import get_request_user_id, get_user_context
    uid = get_request_user_id()
    if uid:
        ctx = get_user_context(uid)
        if ctx and ctx.database_identity and ctx.database_identity != "none":
            return ctx.database_identity
    from app.database.database_manager import get_engine
    eng = get_engine()
    if eng is None:
        return "none"
    try:
        return eng.url.render_as_string(hide_password=True)
    except Exception:
        return "unknown"


class ProposeActionRequest(BaseModel):
    action_type: str  # INSERT, UPDATE, DELETE
    target_table: str
    changes: list[dict[str, Any]]
    condition_sql: Optional[str] = None
    condition_params: Optional[dict[str, Any]] = None
    reason: Optional[str] = None
    source_signal_id: Optional[str] = None

class ConfirmActionRequest(BaseModel):
    high_risk_acknowledged: Optional[bool] = False

class ExecuteActionRequest(BaseModel):
    confirmation_token: Optional[str] = None

@app.post("/intelligence/actions/propose")
@limiter.limit("10/minute")
def action_propose_endpoint(
    req: ProposeActionRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Propose a safe, structured business action with initial multi-layer validation."""
    _activate(user)
    try:
        from app.database.database_manager import get_engine, get_current_db_type
        engine = get_engine()
        db_type = get_current_db_type() or "sqlite"
        db_ident = _get_active_db_identity()

        proposal = build_action_proposal(
            user_id=user.user_id,
            action_type=req.action_type,
            target_table=req.target_table,
            changes=req.changes,
            condition_sql=req.condition_sql,
            condition_params=req.condition_params,
            reason=req.reason or "",
            source_signal_id=req.source_signal_id,
            engine=engine,
            db_type=db_type,
            database_identity=db_ident,
        )

        save_action(proposal)
        return {
            "status": proposal.status,
            "action": proposal.to_dict(),
        }
    except Exception as e:
        logging.error(f"Action proposal error: {e}", exc_info=True)
        return {"status": "error", "message": str(e), "action": None}


@app.post("/intelligence/actions/{action_id}/preview")
@limiter.limit("20/minute")
def action_preview_endpoint(
    action_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Dry-run impact preview calculating affected rows and dependent references."""
    _activate(user)
    action = get_action_proposal(action_id, user_id=user.user_id)
    if not action:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found.")

    try:
        from app.database.database_manager import get_engine, get_current_db_type
        engine = get_engine()
        db_type = get_current_db_type() or "sqlite"

        impact, risk = calculate_impact_preview(action, engine=engine, db_type=db_type)
        action.impact = impact
        action.risk = risk.value

        if risk == ActionRisk.BLOCKED or impact.is_excessive:
            action.status = ActionStatus.BLOCKED.value
        elif action.status not in (ActionStatus.CONFIRMED.value, ActionStatus.EXECUTED.value, ActionStatus.VERIFIED.value):
            action.status = ActionStatus.READY_FOR_CONFIRMATION.value

        save_action(action)
        return {
            "status": action.status,
            "impact": impact.to_dict(),
            "risk": risk.value,
            "action": action.to_dict(),
        }
    except Exception as e:
        logging.error(f"Action preview error: {e}", exc_info=True)
        return {"status": "error", "message": str(e), "action": action.to_dict()}


@app.post("/intelligence/actions/{action_id}/confirm")
@limiter.limit("10/minute")
def action_confirm_endpoint(
    action_id: str,
    req: ConfirmActionRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Explicit human confirmation generating an HMAC-SHA256 confirmation token."""
    _activate(user)
    action = get_action_proposal(action_id, user_id=user.user_id)
    if not action:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found.")

    if action.status in (ActionStatus.EXECUTED.value, ActionStatus.VERIFIED.value):
        raise HTTPException(status_code=409, detail="Action has already been executed.")

    if action.status == ActionStatus.BLOCKED.value:
        raise HTTPException(status_code=400, detail="Cannot confirm a blocked action.")

    if action.risk == ActionRisk.HIGH.value and not req.high_risk_acknowledged:
        raise HTTPException(
            status_code=400,
            detail="High-risk actions require explicit high-risk acknowledgement checkbox."
        )

    db_ident = _get_active_db_identity()
    conf = generate_confirmation_token(
        proposal=action,
        user_id=user.user_id,
        db_identity=db_ident,
        high_risk_acknowledged=bool(req.high_risk_acknowledged),
    )

    action.confirmation = conf
    action.status = ActionStatus.CONFIRMED.value
    save_action(action)

    return {
        "status": "confirmed",
        "confirmation_token": conf.confirmation_token,
        "expires_at": conf.expires_at,
        "action": action.to_dict(),
    }


@app.post("/intelligence/actions/{action_id}/execute")
@limiter.limit("5/minute")
def action_execute_endpoint(
    action_id: str,
    req: ExecuteActionRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Atomic transactional execution with verification and audit logging."""
    _activate(user)
    action = get_action_proposal(action_id, user_id=user.user_id)
    if not action:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found.")

    if action.status in (ActionStatus.EXECUTED.value, ActionStatus.VERIFIED.value):
        raise HTTPException(status_code=409, detail="Action has already been executed (duplicate execution blocked).")

    if action.status != ActionStatus.CONFIRMED.value:
        raise HTTPException(status_code=400, detail=f"Action is in state '{action.status}'. Explicit confirmation required before execution.")

    from app.database.database_manager import get_engine, get_current_db_type
    engine = get_engine()
    if engine is None:
        return {"status": "disconnected", "message": "No active database connection.", "action": action.to_dict()}

    db_type = get_current_db_type() or "sqlite"
    db_ident = _get_active_db_identity()

    token = req.confirmation_token or (action.confirmation.confirmation_token if action.confirmation else "")

    try:
        res = execute_action(
            proposal=action,
            engine=engine,
            user_id=user.user_id,
            confirmation_token=token,
            current_db_identity=db_ident,
            db_type=db_type,
        )
        return {
            "status": action.status,
            "result": res.to_dict(),
            "action": action.to_dict(),
        }
    except ActionExecutionConflict as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ActionExecutionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.error(f"Unexpected execution error: {e}", exc_info=True)
        return {"status": "error", "message": str(e), "action": action.to_dict()}


@app.get("/intelligence/actions/{action_id}")
@limiter.limit("30/minute")
def action_get_endpoint(
    action_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Fetch action proposal details for the requesting user."""
    _activate(user)
    action = get_action_proposal(action_id, user_id=user.user_id)
    if not action:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found.")
    return {"status": "success", "action": action.to_dict()}


@app.get("/intelligence/actions")
@limiter.limit("30/minute")
def action_list_endpoint(
    request: Request,
    status: Optional[str] = None,
    limit: int = 50,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """List action proposals for the authenticated user."""
    _activate(user)
    actions = list_action_proposals(user_id=user.user_id, status=status, limit=limit)
    return {
        "status": "success",
        "actions": [a.to_dict() for a in actions],
        "count": len(actions),
    }


@app.post("/intelligence/actions/{action_id}/cancel")
@limiter.limit("10/minute")
def action_cancel_endpoint(
    action_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Cancel a proposed or confirmed action."""
    _activate(user)
    action = get_action_proposal(action_id, user_id=user.user_id)
    if not action:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found.")

    if action.status in (ActionStatus.EXECUTED.value, ActionStatus.VERIFIED.value):
        raise HTTPException(status_code=400, detail="Cannot cancel an already executed action.")

    action.status = ActionStatus.CANCELLED.value
    save_action(action)
    return {"status": "cancelled", "action": action.to_dict()}


# ── Phase 8.9: Closed-Loop Outcome Optimization & Adaptive Recommendations ────

class MeasureOutcomeRequest(BaseModel):
    action_id: str
    metric_name: Optional[str] = None
    source_table: Optional[str] = None
    source_column: Optional[str] = None
    aggregation: Optional[str] = "SUM"
    window: Optional[str] = "7d"
    force_remeasure: Optional[bool] = False


@app.post("/intelligence/outcomes/measure")
@limiter.limit("10/minute")
def measure_outcome_endpoint(
    req: MeasureOutcomeRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Trigger outcome measurement for a Phase 8.8 action.
    Measures before/after metric changes using real database data.
    Returns observed associations — causation is NOT claimed.
    """
    _activate(user)
    try:
        from app.intelligence.outcome_optimization.analysis_engine import run_outcome_analysis
        from app.intelligence.outcome_optimization.models import MeasurementWindow

        engine = get_engine()
        db_type = get_current_db_type()

        window = req.window or MeasurementWindow.D7
        if window not in MeasurementWindow.ALL:
            window = MeasurementWindow.D7

        analysis = run_outcome_analysis(
            user_id=user.user_id,
            action_id=req.action_id,
            engine=engine,
            db_type=db_type,
            window=window,
            force_remeasure=bool(req.force_remeasure),
        )

        return {
            "status": "success" if analysis.measurements else "insufficient_data",
            "analysis": analysis.to_dict(),
        }
    except Exception as e:
        logging.error(f"Outcome measure error: {e}", exc_info=True)
        return {"status": "error", "message": str(e), "analysis": None}


@app.get("/intelligence/outcomes/{outcome_id}")
@limiter.limit("30/minute")
def get_outcome_by_id_endpoint(
    outcome_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Retrieve a specific Phase 8.9 outcome measurement by ID.
    Strict user isolation: returns 404 if measurement belongs to another user.
    """
    _activate(user)
    try:
        from app.intelligence.outcome_optimization.outcome_tracker import get_measurement
        m = get_measurement(measurement_id=outcome_id, user_id=user.user_id)
        if m is None:
            raise HTTPException(status_code=404, detail=f"Outcome measurement '{outcome_id}' not found.")
        return {"status": "success", "measurement": m.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "message": str(e), "measurement": None}


@app.get("/intelligence/outcomes/{outcome_id}/analysis")
@limiter.limit("20/minute")
def get_outcome_analysis_endpoint(
    outcome_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Retrieve all measurements for a given action_id (treated as outcome_id here).
    Builds and returns a full OutcomeAnalysis for the action.
    """
    _activate(user)
    try:
        from app.intelligence.outcome_optimization.outcome_tracker import list_measurements
        from app.intelligence.outcome_optimization.analysis_engine import (
            _aggregate_effectiveness, _aggregate_confidence, _aggregate_attribution, _build_summary
        )
        from app.intelligence.outcome_optimization.models import OutcomeAnalysis

        measurements = list_measurements(
            user_id=user.user_id,
            action_id=outcome_id,
            limit=50,
        )

        analysis = OutcomeAnalysis(
            action_id=outcome_id,
            user_id=user.user_id,
            measurements=measurements,
        )

        if measurements:
            analysis.overall_effectiveness = _aggregate_effectiveness(measurements)
            analysis.overall_confidence = _aggregate_confidence(measurements)
            analysis.attribution_summary = _aggregate_attribution(measurements)
            analysis.summary = _build_summary(analysis, measurements)

        return {
            "status": "success" if measurements else "no_measurements",
            "analysis": analysis.to_dict(),
        }
    except Exception as e:
        return {"status": "error", "message": str(e), "analysis": None}


@app.get("/intelligence/recommendations/adaptive")
@limiter.limit("20/minute")
def get_adaptive_recommendations_endpoint(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Generate adaptive recommendations from real historical outcomes and measurements.
    Returns evidence-based recommendations. Never auto-executes.
    All recommendations require Phase 8.8 confirmation flow.
    """
    _activate(user)
    try:
        from app.intelligence.outcome_optimization.recommendation_engine import (
            generate_adaptive_recommendations,
        )
        recs = generate_adaptive_recommendations(user_id=user.user_id)
        return {
            "status": "success",
            "recommendations": [r.to_dict() for r in recs],
            "total": len(recs),
            "note": (
                "Recommendations are based on observed historical patterns only. "
                "All actions require human confirmation via Phase 8.8."
            ),
        }
    except Exception as e:
        logging.error(f"Adaptive recommendations error: {e}", exc_info=True)
        return {"status": "error", "message": str(e), "recommendations": [], "total": 0}


@app.post("/intelligence/recommendations/{recommendation_id}/explain")
@limiter.limit("20/minute")
def explain_recommendation_endpoint(
    recommendation_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Generate a structured explanation for a specific adaptive recommendation.
    Groq may rephrase pre-computed explanation text (no new facts generated).
    """
    _activate(user)
    try:
        from app.intelligence.outcome_optimization.outcome_tracker import get_recommendation
        from app.intelligence.outcome_optimization.explainer import explain_recommendation

        rec = get_recommendation(recommendation_id=recommendation_id, user_id=user.user_id)
        if rec is None:
            raise HTTPException(
                status_code=404,
                detail=f"Recommendation '{recommendation_id}' not found.",
            )

        explanation = explain_recommendation(rec=rec, use_groq=False)
        return {
            "status": "success",
            "recommendation_id": recommendation_id,
            "explanation": explanation.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "message": str(e), "explanation": None}


# ── Phase 9.0: Advanced Predictive & Simulation Intelligence ──────────────────

class PredictRequest(BaseModel):
    table: str
    date_column: Optional[str] = None
    metric_column: Optional[str] = None
    metric_name: Optional[str] = None
    aggregation: Optional[str] = "SUM"
    frequency: Optional[str] = "monthly"
    horizon_days: Optional[int] = 30
    force_method: Optional[str] = None


class ScenarioSimRequest(BaseModel):
    prediction_id: str
    change_percent: Optional[float] = None
    absolute_change: Optional[float] = None
    scenario_name: Optional[str] = None
    scenario_type: Optional[str] = "CUSTOM"


class ScenarioCompareRequest(BaseModel):
    prediction_id: str
    scenarios: list[dict[str, Any]] = []


@app.post("/intelligence/predict")
@limiter.limit("20/minute")
def run_predict_endpoint(
    req: PredictRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Executes statistical forecasting across candidate models with holdout backtesting
    and prediction intervals on real connected database data.
    """
    _activate(user)
    try:
        from app.intelligence.predictive.predictor import run_prediction

        result = run_prediction(
            user_id=user.user_id,
            table=req.table,
            date_column=req.date_column,
            metric_column=req.metric_column,
            metric_name=req.metric_name,
            aggregation=req.aggregation or "SUM",
            frequency=req.frequency or "monthly",
            horizon_days=req.horizon_days if req.horizon_days is not None else 30,
            force_method=req.force_method,
            engine=get_engine(),
            db_type=get_current_db_type(),
        )

        return {
            "status": result.status,
            "prediction": result.to_dict(),
        }
    except Exception as e:
        logging.error(f"Prediction error: {e}", exc_info=True)
        return {"status": "error", "message": str(e), "prediction": None}


@app.get("/intelligence/predict/candidates")
@limiter.limit("30/minute")
def get_predict_candidates_endpoint(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Discovers candidate metrics and date columns eligible for time-series forecasting.
    """
    _activate(user)
    try:
        from app.intelligence.predictive.data_quality import discover_predictive_candidates

        candidates = discover_predictive_candidates(
            engine=get_engine(), db_type=get_current_db_type()
        )
        return {
            "status": "success",
            "candidates": [
                {
                    "table": c.table,
                    "date_column": c.date_column,
                    "metric_column": c.metric_column,
                    "metric_name": c.metric_name,
                    "aggregation": c.aggregation,
                    "frequency": c.frequency,
                }
                for c in candidates
            ],
            "total": len(candidates),
        }
    except Exception as e:
        logging.error(f"Prediction candidates discovery error: {e}", exc_info=True)
        return {"status": "error", "message": str(e), "candidates": [], "total": 0}


@app.post("/intelligence/predict/scenario")
@limiter.limit("20/minute")
def run_scenario_endpoint(
    req: ScenarioSimRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Simulates a what-if scenario on a pre-existing baseline forecast.
    """
    _activate(user)
    try:
        from app.intelligence.predictive.store import get_prediction
        from app.intelligence.predictive.scenario_engine import simulate_what_if_scenario

        pred = get_prediction(req.prediction_id, user_id=user.user_id)
        if not pred:
            raise HTTPException(
                status_code=404,
                detail=f"Baseline prediction '{req.prediction_id}' not found.",
            )

        scenario = simulate_what_if_scenario(
            baseline_result=pred,
            change_percent=req.change_percent,
            absolute_change=req.absolute_change,
            scenario_name=req.scenario_name,
            scenario_type=req.scenario_type or "CUSTOM",
        )

        return {
            "status": "success",
            "scenario": scenario.to_dict(),
        }
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logging.error(f"Scenario simulation error: {e}", exc_info=True)
        return {"status": "error", "message": str(e), "scenario": None}


@app.post("/intelligence/predict/compare")
@limiter.limit("20/minute")
def run_compare_endpoint(
    req: ScenarioCompareRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Conducts multi-scenario comparative simulation against baseline forecast.
    """
    _activate(user)
    try:
        from app.intelligence.predictive.store import get_prediction
        from app.intelligence.predictive.scenario_engine import compare_scenarios

        pred = get_prediction(req.prediction_id, user_id=user.user_id)
        if not pred:
            raise HTTPException(
                status_code=404,
                detail=f"Baseline prediction '{req.prediction_id}' not found.",
            )

        comparison = compare_scenarios(
            baseline_result=pred,
            scenario_specs=req.scenarios,
        )

        return {
            "status": "success",
            "comparison": comparison.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Scenario comparison error: {e}", exc_info=True)
        return {"status": "error", "message": str(e), "comparison": None}


@app.get("/intelligence/predict/history")
@limiter.limit("30/minute")
def list_predictions_endpoint(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Lists recent forecast results generated by the user.
    """
    _activate(user)
    try:
        from app.intelligence.predictive.store import list_predictions

        results = list_predictions(user_id=user.user_id, limit=20)
        return {
            "status": "success",
            "predictions": [p.to_dict() for p in results],
            "total": len(results),
        }
    except Exception as e:
        logging.error(f"Predictions list error: {e}", exc_info=True)
        return {"status": "error", "message": str(e), "predictions": [], "total": 0}


@app.get("/intelligence/predict/{prediction_id}")
@limiter.limit("30/minute")
def get_prediction_endpoint(
    prediction_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Retrieves a specific prediction verifying user ownership.
    """
    _activate(user)
    try:
        from app.intelligence.predictive.store import get_prediction

        pred = get_prediction(prediction_id=prediction_id, user_id=user.user_id)
        if not pred:
            raise HTTPException(
                status_code=404,
                detail=f"Prediction '{prediction_id}' not found.",
            )

        return {
            "status": "success",
            "prediction": pred.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Prediction get error: {e}", exc_info=True)
        return {"status": "error", "message": str(e), "prediction": None}


@app.post("/intelligence/predict/{prediction_id}/explain")
@limiter.limit("20/minute")
def explain_prediction_endpoint(
    prediction_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Generates a structured, transparent explanation of predictive evidence lineage,
    method selection rationale, and uncertainty constraints.
    """
    _activate(user)
    try:
        from app.intelligence.predictive.store import get_prediction
        from app.intelligence.predictive.explainer import explain_prediction_narrative

        pred = get_prediction(prediction_id=prediction_id, user_id=user.user_id)
        if not pred:
            raise HTTPException(
                status_code=404,
                detail=f"Prediction '{prediction_id}' not found.",
            )

        explanation = explain_prediction_narrative(pred=pred, use_groq=False)
        return {
            "status": "success",
            "explanation": explanation.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Prediction explanation error: {e}", exc_info=True)
        return {"status": "error", "message": str(e), "explanation": None}


# ── Phase 9.1: Enterprise Knowledge & Context Intelligence Endpoints ──────────

class ContextParseRequest(BaseModel):
    statement: str


class DefinitionCreateRequest(BaseModel):
    item_type: str  # "METRIC", "ENTITY", "RULE"
    name: str
    description: Optional[str] = ""
    table_name: str
    column_name: Optional[str] = None
    aggregation: Optional[str] = "SUM"
    filter_expression: Optional[str] = None
    rule_type: Optional[str] = "EXCLUSION"
    expression: Optional[str] = None
    status: Optional[str] = "PROPOSED"


class ConflictResolveRequest(BaseModel):
    resolution_choice: str  # "CHOOSE_A", "CHOOSE_B", "CUSTOM"
    resolution_notes: Optional[str] = ""


@app.get("/intelligence/knowledge")
@limiter.limit("30/minute")
def get_knowledge_summary_endpoint(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Returns an aggregated summary of the Enterprise Knowledge base for the active database.
    """
    _activate(user)
    try:
        from app.intelligence.knowledge.knowledge_store import (
            get_knowledge_summary,
            list_entities,
            list_metrics,
            list_rules,
            list_conflicts,
        )
        from app.intelligence.knowledge.entity_registry import discover_and_sync_entities
        from app.intelligence.knowledge.metric_registry import discover_and_sync_metrics

        db_id = _get_active_db_identity()
        eng = get_engine()
        db_t = get_current_db_type()

        # Discover & sync entities and metrics if connected
        if eng is not None and db_t != "none":
            discover_and_sync_entities(engine=eng, db_type=db_t, user_id=user.user_id, database_identity=db_id)
            discover_and_sync_metrics(engine=eng, db_type=db_t, user_id=user.user_id, database_identity=db_id)

        summary = get_knowledge_summary(user_id=user.user_id, database_identity=db_id)
        entities = list_entities(user_id=user.user_id, database_identity=db_id)
        metrics = list_metrics(user_id=user.user_id, database_identity=db_id)
        rules = list_rules(user_id=user.user_id, database_identity=db_id)
        conflicts = list_conflicts(user_id=user.user_id, database_identity=db_id)

        return {
            "status": "success",
            "summary": summary.to_dict(),
            "entities": [e.to_dict() for e in entities],
            "metrics": [m.to_dict() for m in metrics],
            "rules": [r.to_dict() for r in rules],
            "conflicts": [c.to_dict() for c in conflicts],
        }
    except Exception as e:
        logging.error(f"Knowledge summary error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.get("/intelligence/knowledge/entities")
@limiter.limit("30/minute")
def get_knowledge_entities_endpoint(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Lists discovered and user-confirmed business entities for the active database.
    """
    _activate(user)
    try:
        from app.intelligence.knowledge.entity_registry import discover_and_sync_entities
        db_id = _get_active_db_identity()
        eng = get_engine()
        db_t = get_current_db_type()

        entities = discover_and_sync_entities(
            engine=eng,
            db_type=db_t,
            user_id=user.user_id,
            database_identity=db_id,
        )
        return {
            "status": "success",
            "entities": [e.to_dict() for e in entities],
            "total": len(entities),
        }
    except Exception as e:
        logging.error(f"Knowledge entities error: {e}", exc_info=True)
        return {"status": "error", "message": str(e), "entities": [], "total": 0}


@app.get("/intelligence/knowledge/metrics")
@limiter.limit("30/minute")
def get_knowledge_metrics_endpoint(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Lists business metrics, definitions, and active rule bindings.
    """
    _activate(user)
    try:
        from app.intelligence.knowledge.metric_registry import discover_and_sync_metrics
        db_id = _get_active_db_identity()
        eng = get_engine()
        db_t = get_current_db_type()

        metrics = discover_and_sync_metrics(
            engine=eng,
            db_type=db_t,
            user_id=user.user_id,
            database_identity=db_id,
        )
        return {
            "status": "success",
            "metrics": [m.to_dict() for m in metrics],
            "total": len(metrics),
        }
    except Exception as e:
        logging.error(f"Knowledge metrics error: {e}", exc_info=True)
        return {"status": "error", "message": str(e), "metrics": [], "total": 0}


@app.get("/intelligence/knowledge/rules")
@limiter.limit("30/minute")
def get_knowledge_rules_endpoint(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Lists business rules and their confirmation lifecycle status.
    """
    _activate(user)
    try:
        from app.intelligence.knowledge.knowledge_store import list_rules
        db_id = _get_active_db_identity()

        rules = list_rules(user_id=user.user_id, database_identity=db_id)
        return {
            "status": "success",
            "rules": [r.to_dict() for r in rules],
            "total": len(rules),
        }
    except Exception as e:
        logging.error(f"Knowledge rules error: {e}", exc_info=True)
        return {"status": "error", "message": str(e), "rules": [], "total": 0}


@app.post("/intelligence/knowledge/context")
@limiter.limit("20/minute")
def parse_context_endpoint(
    req: ContextParseRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Parses a natural-language business context statement and proposes a structured rule.
    Requires explicit confirmation before taking effect.
    """
    _activate(user)
    try:
        from app.intelligence.knowledge.context_engine import parse_and_propose_context
        db_id = _get_active_db_identity()
        eng = get_engine()
        db_t = get_current_db_type()

        result = parse_and_propose_context(
            statement=req.statement,
            user_id=user.user_id,
            database_identity=db_id,
            engine=eng,
            db_type=db_t,
        )
        return {
            "status": "success" if result.parsed_successfully else "failed",
            "parse_result": result.to_dict(),
        }
    except Exception as e:
        logging.error(f"Context parse error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.post("/intelligence/knowledge/definitions")
@limiter.limit("20/minute")
def create_or_update_definition_endpoint(
    req: DefinitionCreateRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Directly creates or updates a business definition, metric, or rule.
    Validates schema conformance and SQL safety.
    """
    _activate(user)
    try:
        import uuid
        from app.intelligence.knowledge.business_rules import validate_rule_safety
        from app.intelligence.knowledge.knowledge_store import save_rule, save_metric, save_entity
        from app.intelligence.knowledge.models import (
            BusinessRule, BusinessMetric, BusinessEntity,
            KnowledgeProvenance, KnowledgeStatus, RuleScope
        )
        from app.intelligence.schema_analyzer import analyze_schema

        db_id = _get_active_db_identity()
        eng = get_engine()
        db_t = get_current_db_type()
        schema_info = analyze_schema(eng, db_t) if eng and db_t != "none" else {}

        item_type = req.item_type.upper()
        if item_type == "RULE":
            expr = req.expression or req.filter_expression or ""
            is_valid, err = validate_rule_safety(
                expression=expr,
                target_table=req.table_name,
                target_column=req.column_name,
                schema_info=schema_info,
            )
            if not is_valid:
                raise HTTPException(status_code=400, detail=f"Rule safety validation failed: {err}")

            rule = BusinessRule(
                rule_id=f"rule_{uuid.uuid4().hex[:12]}",
                name=req.name,
                description=req.description or "",
                scope=RuleScope.METRIC.value,
                target_table=req.table_name,
                target_column=req.column_name,
                rule_type=req.rule_type or "EXCLUSION",
                expression=expr,
                status=req.status or KnowledgeStatus.CONFIRMED.value,
                provenance=KnowledgeProvenance.USER_PROVIDED.value,
                version=1,
                affected_metrics=[req.name],
                user_id=user.user_id,
                database_identity=db_id,
            )
            saved = save_rule(rule)
            return {"status": "success", "item": saved.to_dict(), "item_type": "RULE"}

        elif item_type == "METRIC":
            metric = BusinessMetric(
                metric_id=f"met_{uuid.uuid4().hex[:12]}",
                name=req.name,
                description=req.description or "",
                table_name=req.table_name,
                column_name=req.column_name,
                aggregation=req.aggregation or "SUM",
                filter_expression=req.filter_expression,
                conditions=[req.filter_expression] if req.filter_expression else [],
                rules_applied=[],
                version=1,
                provenance=KnowledgeProvenance.USER_PROVIDED.value,
                status=req.status or KnowledgeStatus.CONFIRMED.value,
                confidence=1.0,
                user_id=user.user_id,
                database_identity=db_id,
            )
            saved = save_metric(metric)
            return {"status": "success", "item": saved.to_dict(), "item_type": "METRIC"}

        else:
            entity = BusinessEntity(
                entity_id=f"ent_{req.table_name}",
                name=req.name,
                plural_name=req.name + "s",
                table_name=req.table_name,
                description=req.description or "",
                provenance=KnowledgeProvenance.USER_PROVIDED.value,
                status=req.status or KnowledgeStatus.CONFIRMED.value,
                confidence=1.0,
                user_id=user.user_id,
                database_identity=db_id,
            )
            saved = save_entity(entity)
            return {"status": "success", "item": saved.to_dict(), "item_type": "ENTITY"}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Knowledge definition creation error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.post("/intelligence/knowledge/{knowledge_id}/confirm")
@limiter.limit("30/minute")
def confirm_knowledge_endpoint(
    knowledge_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Confirms an unconfirmed or proposed knowledge item (rule, entity, or metric).
    Transitions status to CONFIRMED.
    """
    _activate(user)
    try:
        from app.intelligence.knowledge.knowledge_store import confirm_knowledge_item
        db_id = _get_active_db_identity()

        success = confirm_knowledge_item(
            item_id=knowledge_id,
            user_id=user.user_id,
            database_identity=db_id,
        )
        if not success:
            raise HTTPException(status_code=404, detail=f"Knowledge item '{knowledge_id}' not found.")

        return {"status": "success", "message": f"Knowledge item '{knowledge_id}' confirmed."}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Knowledge confirm error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.post("/intelligence/knowledge/{knowledge_id}/disable")
@limiter.limit("30/minute")
def disable_knowledge_endpoint(
    knowledge_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Disables an active or proposed knowledge item.
    """
    _activate(user)
    try:
        from app.intelligence.knowledge.knowledge_store import disable_knowledge_item
        db_id = _get_active_db_identity()

        success = disable_knowledge_item(
            item_id=knowledge_id,
            user_id=user.user_id,
            database_identity=db_id,
        )
        if not success:
            raise HTTPException(status_code=404, detail=f"Knowledge item '{knowledge_id}' not found.")

        return {"status": "success", "message": f"Knowledge item '{knowledge_id}' disabled."}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Knowledge disable error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.post("/intelligence/knowledge/{knowledge_id}/resolve")
@limiter.limit("20/minute")
def resolve_conflict_endpoint(
    knowledge_id: str,
    req: ConflictResolveRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Resolves a recorded conflict by choosing definition A or B, updating conflict status.
    """
    _activate(user)
    try:
        from app.intelligence.knowledge.knowledge_store import resolve_knowledge_conflict
        db_id = _get_active_db_identity()

        success = resolve_knowledge_conflict(
            conflict_id=knowledge_id,
            resolution_choice=req.resolution_choice,
            resolution_notes=req.resolution_notes or "",
            user_id=user.user_id,
            database_identity=db_id,
        )
        if not success:
            raise HTTPException(status_code=404, detail=f"Conflict '{knowledge_id}' not found.")

        return {"status": "success", "message": f"Conflict '{knowledge_id}' resolved."}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Conflict resolve error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.get("/intelligence/knowledge/search")
@limiter.limit("30/minute")
def search_knowledge_endpoint(
    q: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Searches the knowledge registry for entities, metrics, or rules.
    """
    _activate(user)
    try:
        from app.intelligence.knowledge.knowledge_resolver import search_knowledge
        db_id = _get_active_db_identity()

        result = search_knowledge(query=q, user_id=user.user_id, database_identity=db_id)
        return {"status": "success", **result}
    except Exception as e:
        logging.error(f"Knowledge search error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.get("/intelligence/knowledge/{knowledge_id}")
@limiter.limit("30/minute")
def get_knowledge_item_endpoint(
    knowledge_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Retrieves details for a specific metric, rule, or entity.
    """
    _activate(user)
    try:
        from app.intelligence.knowledge.knowledge_store import (
            get_metric, get_rule, get_entity
        )
        db_id = _get_active_db_identity()

        item = get_metric(knowledge_id, user_id=user.user_id, database_identity=db_id)
        item_type = "METRIC"
        if not item:
            item = get_rule(knowledge_id, user_id=user.user_id, database_identity=db_id)
            item_type = "RULE"
        if not item:
            item = get_entity(knowledge_id, user_id=user.user_id, database_identity=db_id)
            item_type = "ENTITY"

        if not item:
            raise HTTPException(status_code=404, detail=f"Knowledge item '{knowledge_id}' not found.")

        return {
            "status": "success",
            "item_type": item_type,
            "item": item.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Knowledge item get error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.get("/intelligence/knowledge/{knowledge_id}/lineage")
@limiter.limit("30/minute")
def get_knowledge_lineage_endpoint(
    knowledge_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Retrieves complete end-to-end lineage for a business metric or concept.
    """
    _activate(user)
    try:
        from app.intelligence.knowledge.knowledge_resolver import build_metric_lineage
        db_id = _get_active_db_identity()
        db_t = get_current_db_type()

        lineage = build_metric_lineage(
            metric_id_or_name=knowledge_id,
            user_id=user.user_id,
            database_identity=db_id,
            db_type=db_t,
        )
        return {
            "status": "success",
            "lineage": lineage.to_dict(),
        }
    except Exception as e:
        logging.error(f"Knowledge lineage error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.get("/intelligence/knowledge/{knowledge_id}/explain")
@limiter.limit("30/minute")
def explain_knowledge_item_endpoint(
    knowledge_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Produces transparent facts vs inferences vs assumptions explanation for a knowledge item.
    """
    _activate(user)
    try:
        from app.intelligence.knowledge.knowledge_explainer import explain_knowledge_item
        db_id = _get_active_db_identity()

        explanation = explain_knowledge_item(
            knowledge_id=knowledge_id,
            user_id=user.user_id,
            database_identity=db_id,
        )
        return {
            "status": "success",
            "explanation": explanation.to_dict(),
        }
    except Exception as e:
        logging.error(f"Knowledge explainer error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


# ── Phase 9.2: Advanced Agent Orchestration Endpoints ─────────────────────────

class OrchestrateRequest(BaseModel):
    goal: str


@app.post("/intelligence/orchestrate")
@limiter.limit("20/minute")
def initiate_orchestration_endpoint(
    req: OrchestrateRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Initiates full multi-agent orchestration for a natural language goal.
    """
    _activate(user)
    try:
        from app.intelligence.orchestration.orchestrator import orchestrate_goal
        db_id = _get_active_db_identity()
        db_t = get_current_db_type()
        engine = get_engine()

        run = orchestrate_goal(
            goal=req.goal,
            user_id=user.user_id,
            database_identity=db_id,
            engine=engine,
            db_type=db_t,
        )
        return {
            "status": "success",
            "orchestration": run.to_dict(),
        }
    except Exception as e:
        logging.error(f"Orchestration initiation error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.get("/intelligence/orchestrate")
@limiter.limit("30/minute")
def list_orchestrations_endpoint(
    request: Request,
    limit: int = 20,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Lists historical orchestration runs for current tenant and database.
    """
    _activate(user)
    try:
        from app.intelligence.orchestration.store import list_orchestration_runs
        db_id = _get_active_db_identity()

        runs = list_orchestration_runs(user_id=user.user_id, database_identity=db_id, limit=limit)
        return {
            "status": "success",
            "runs": [r.to_dict() for r in runs],
        }
    except Exception as e:
        logging.error(f"List orchestrations error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.get("/intelligence/orchestrate/agents")
@limiter.limit("30/minute")
def list_orchestration_agents_endpoint(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Lists registered specialist agents and their permission tiers.
    """
    _activate(user)
    try:
        from app.intelligence.orchestration.agent_registry import list_registered_agents
        agents = list_registered_agents()
        return {
            "status": "success",
            "agents": [a.to_dict() for a in agents],
        }
    except Exception as e:
        logging.error(f"List orchestration agents error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.get("/intelligence/orchestrate/{orchestration_id}")
@limiter.limit("30/minute")
def get_orchestration_endpoint(
    orchestration_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Retrieves a specific orchestration run with its task graph, evidence ledger, and conflicts.
    """
    _activate(user)
    try:
        from app.intelligence.orchestration.store import get_orchestration_run
        db_id = _get_active_db_identity()

        run = get_orchestration_run(orchestration_id, user_id=user.user_id, database_identity=db_id)
        if not run:
            raise HTTPException(status_code=404, detail=f"Orchestration '{orchestration_id}' not found.")

        return {
            "status": "success",
            "orchestration": run.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Get orchestration error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.get("/intelligence/orchestrate/{orchestration_id}/evidence")
@limiter.limit("30/minute")
def get_orchestration_evidence_endpoint(
    orchestration_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Retrieves the verified evidence ledger for an orchestration run.
    """
    _activate(user)
    try:
        from app.intelligence.orchestration.store import get_orchestration_run
        db_id = _get_active_db_identity()

        run = get_orchestration_run(orchestration_id, user_id=user.user_id, database_identity=db_id)
        if not run:
            raise HTTPException(status_code=404, detail=f"Orchestration '{orchestration_id}' not found.")

        return {
            "status": "success",
            "orchestration_id": orchestration_id,
            "evidence": [e.to_dict() for e in run.evidence_ledger],
            "total_items": len(run.evidence_ledger),
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Get orchestration evidence error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.post("/intelligence/orchestrate/{orchestration_id}/cancel")
@limiter.limit("20/minute")
def cancel_orchestration_endpoint(
    orchestration_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Cancels an active or waiting orchestration run.
    """
    _activate(user)
    try:
        from app.intelligence.orchestration.store import get_orchestration_run, save_orchestration_run
        from app.intelligence.orchestration.models import OrchestrationStatus
        db_id = _get_active_db_identity()

        run = get_orchestration_run(orchestration_id, user_id=user.user_id, database_identity=db_id)
        if not run:
            raise HTTPException(status_code=404, detail=f"Orchestration '{orchestration_id}' not found.")

        run.status = OrchestrationStatus.CANCELLED
        save_orchestration_run(run)

        return {
            "status": "success",
            "message": f"Orchestration '{orchestration_id}' cancelled.",
            "orchestration": run.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Cancel orchestration error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


# ── Phase 9.3: Enterprise Governance & Observability Endpoints ───────────────
from app.intelligence.governance import (
    ActorType,
    GovernanceEventType,
    PolicyCategory,
    PolicyScope,
    PolicyDecision,
    RiskLevel,
    SecurityEventType,
    SecurityEventSeverity,
    GovernanceAuditEvent,
    SecurityEventRecord,
    GovernancePolicy,
    RiskAssessment,
    DataAccessEvent,
    AgentTraceRecord,
    AgentObservabilityMetric,
    GovernanceSummary,
    ComplianceReport,
    get_audit_store,
    list_policies,
    get_policy,
    set_policy_status,
    PolicyModificationError,
    PolicyEngine,
    GovernanceRiskEngine,
    DataAccessTracker,
    SecurityEventManager,
    AgentTraceStore,
    get_governance_summary,
    get_agent_observability_metrics,
    generate_compliance_report,
    get_governance_engine,
)


class EvaluatePolicyRequest(BaseModel):
    category: str
    operation: str
    context: Optional[dict[str, Any]] = None
    operation_type: Optional[str] = "READ_ONLY"
    affected_rows: Optional[int] = 0
    agent_permission: Optional[str] = "READ_ONLY"


class AssessRiskRequest(BaseModel):
    operation: str
    operation_type: Optional[str] = "READ_ONLY"
    affected_rows: Optional[int] = 0
    agent_permission: Optional[str] = "READ_ONLY"
    context: Optional[dict[str, Any]] = None


class SetPolicyStatusRequest(BaseModel):
    policy_id: str
    enabled: bool


@app.get("/intelligence/governance/summary")
@limiter.limit("30/minute")
def get_governance_summary_endpoint(
    request: Request,
    days: int = 7,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Retrieves synthesized operational governance metrics and hash chain verification status."""
    _activate(user)
    try:
        db_id = _get_active_db_identity()
        summary = get_governance_summary(user_id=user.user_id, database_identity=db_id, days=days)
        return {
            "status": "success",
            "summary": summary.to_dict(),
        }
    except Exception as e:
        logging.error(f"Governance summary error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.get("/intelligence/governance/audit")
@limiter.limit("60/minute")
def list_governance_audit_endpoint(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    event_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Retrieves paginated audit log events from the tamper-evident hash chain."""
    _activate(user)
    try:
        db_id = _get_active_db_identity()
        store = get_audit_store()
        bounded_limit = min(max(1, limit), 200)

        ev_enum = GovernanceEventType(event_type) if event_type else None
        risk_enum = RiskLevel(risk_level) if risk_level else None

        events = store.list_audit_events(
            user_id=user.user_id,
            database_identity=db_id,
            event_type=ev_enum,
            risk_level=risk_enum,
            start_time=start_time,
            end_time=end_time,
            limit=bounded_limit,
            offset=offset,
        )
        is_valid, count, error_detail = store.verify_audit_chain(user_id=user.user_id)

        return {
            "status": "success",
            "events": [e.to_dict() for e in events],
            "total_returned": len(events),
            "chain_verified": is_valid,
            "chain_events_verified": count,
            "chain_verification_error": error_detail,
        }
    except Exception as e:
        logging.error(f"Governance audit list error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.get("/intelligence/governance/security-events")
@limiter.limit("60/minute")
def list_governance_security_events_endpoint(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    ip_address: Optional[str] = None,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Retrieves logged security events (blocked DDL, injection attempts, etc.)."""
    _activate(user)
    try:
        db_id = _get_active_db_identity()
        store = get_audit_store()
        bounded_limit = min(max(1, limit), 200)

        sev_enum = SecurityEventSeverity(severity) if severity else None
        ev_enum = SecurityEventType(event_type) if event_type else None

        events = store.list_security_events(
            user_id=user.user_id,
            database_identity=db_id,
            severity=sev_enum,
            event_type=ev_enum,
            ip_address=ip_address,
            limit=bounded_limit,
            offset=offset,
        )
        return {
            "status": "success",
            "security_events": [e.to_dict() for e in events],
            "total_returned": len(events),
        }
    except Exception as e:
        logging.error(f"Governance security events error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.get("/intelligence/governance/agents")
@limiter.limit("60/minute")
def get_governance_agent_observability_endpoint(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Retrieves factual execution telemetry for all registered agents."""
    _activate(user)
    try:
        db_id = _get_active_db_identity()
        metrics = get_agent_observability_metrics(user_id=user.user_id, database_identity=db_id)
        return {
            "status": "success",
            "agents": [m.to_dict() for m in metrics],
        }
    except Exception as e:
        logging.error(f"Agent observability error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.get("/intelligence/governance/policies")
@limiter.limit("60/minute")
def list_governance_policies_endpoint(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Lists registered governance policies including protected system policies."""
    _activate(user)
    try:
        policies = list_policies(user_id=user.user_id)
        return {
            "status": "success",
            "policies": [p.to_dict() for p in policies],
        }
    except Exception as e:
        logging.error(f"List policies error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.post("/intelligence/governance/policies/status")
@limiter.limit("30/minute")
def set_policy_status_endpoint(
    req: SetPolicyStatusRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Updates status of a user-defined policy. Rejects attempts to modify SYSTEM policies."""
    _activate(user)
    try:
        updated = set_policy_status(policy_id=req.policy_id, enabled=req.enabled, user_id=user.user_id)
        return {
            "status": "success" if updated else "not_found",
            "policy_id": req.policy_id,
            "enabled": req.enabled,
        }
    except PolicyModificationError as pme:
        raise HTTPException(status_code=403, detail=str(pme))
    except Exception as e:
        logging.error(f"Set policy status error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.post("/intelligence/governance/policies/evaluate")
@limiter.limit("30/minute")
def evaluate_policy_endpoint(
    req: EvaluatePolicyRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Deterministic policy evaluation and audit logging."""
    _activate(user)
    try:
        db_id = _get_active_db_identity()
        engine = get_governance_engine()

        cat_enum = PolicyCategory(req.category) if req.category in [c.value for c in PolicyCategory] else PolicyCategory.SECURITY

        decision, risk, audit_event = engine.evaluate_and_record(
            category=cat_enum,
            operation=req.operation,
            actor_type=ActorType.USER,
            actor_id=user.user_id,
            user_id=user.user_id,
            database_identity=db_id,
            context=req.context or {},
            operation_type=req.operation_type or "READ_ONLY",
            affected_rows=req.affected_rows or 0,
            agent_permission=req.agent_permission or "READ_ONLY",
        )

        return {
            "status": "success",
            "decision": decision.value,
            "risk": risk.to_dict(),
            "audit_event_id": audit_event.event_id,
        }
    except Exception as e:
        logging.error(f"Policy evaluation error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.post("/intelligence/governance/risk")
@limiter.limit("30/minute")
def assess_risk_endpoint(
    req: AssessRiskRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Computes transparent risk tier, contributing factors, and required controls."""
    _activate(user)
    try:
        risk = GovernanceRiskEngine.assess_risk(
            operation=req.operation,
            operation_type=req.operation_type or "READ_ONLY",
            affected_rows=req.affected_rows or 0,
            agent_permission=req.agent_permission or "READ_ONLY",
            context=req.context or {},
        )
        return {
            "status": "success",
            "risk": risk.to_dict(),
        }
    except Exception as e:
        logging.error(f"Risk assessment error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.get("/intelligence/governance/traces/{trace_id}")
@limiter.limit("60/minute")
def get_trace_endpoint(
    trace_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Retrieves an individual agent execution trace record."""
    _activate(user)
    try:
        from app.intelligence.governance.audit_store import get_agent_trace
        trace = get_agent_trace(trace_id, user_id=user.user_id)
        if not trace:
            raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found.")
        return {
            "status": "success",
            "trace": trace.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Get trace error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.get("/intelligence/governance/orchestrations/{orchestration_id}")
@limiter.limit("60/minute")
def get_orchestration_traces_endpoint(
    orchestration_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Retrieves all agent execution traces correlated with an orchestration run."""
    _activate(user)
    try:
        traces = AgentTraceStore.get_traces_for_orchestration(
            orchestration_id=orchestration_id,
            user_id=user.user_id,
        )
        return {
            "status": "success",
            "orchestration_id": orchestration_id,
            "traces": [t.to_dict() for t in traces],
            "total_traces": len(traces),
        }
    except Exception as e:
        logging.error(f"Get orchestration traces error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.get("/intelligence/governance/report")
@limiter.limit("20/minute")
def get_compliance_report_endpoint(
    request: Request,
    period_hours: int = 24,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Generates an audit-ready compliance report."""
    _activate(user)
    try:
        db_id = _get_active_db_identity()
        bounded_hours = min(max(1, period_hours), 720)  # Max 30 days
        report = generate_compliance_report(
            user_id=user.user_id,
            database_identity=db_id,
            period_hours=bounded_hours,
        )
        return {
            "status": "success",
            "report": report.to_dict(),
        }
    except Exception as e:
        logging.error(f"Compliance report error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.post("/intelligence/governance/audit/verify")
@limiter.limit("30/minute")
def verify_audit_chain_endpoint(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Performs real-time cryptographic hash verification over the audit event log."""
    _activate(user)
    try:
        store = get_audit_store()
        is_valid, count, error_detail = store.verify_audit_chain(user_id=user.user_id)
        return {
            "status": "success",
            "verified": is_valid,
            "events_verified": count,
            "error_detail": error_detail,
        }
    except Exception as e:
        logging.error(f"Verify audit chain error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


class SecurityScanRequest(BaseModel):
    connection_id: Optional[str] = None
    tables: Optional[list[str]] = None


@app.post("/security/scan")
@limiter.limit("20/minute")
def security_scan_endpoint(
    req: SecurityScanRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Executes a read-only database cybersecurity and sensitive-data exposure audit
    on the user's active or specified database connection.
    """
    _activate(user, req.connection_id)
    try:
        from app.connectors.registry import get_connection_registry
        from app.security.posture_scanner import DatabasePostureScanner

        reg = get_connection_registry()
        conn = reg.get_connector(user.user_id, req.connection_id) if req.connection_id else None
        if not conn:
            conn = reg.get_active_connector(user.user_id)

        if not conn:
            return {
                "status": "error",
                "message": "No active database connected to scan.",
                "connection_id": "",
                "database_type": "none",
                "database_name": "none",
                "scanned_at": datetime.now(timezone.utc).isoformat(),
                "posture_score": None,
                "risk_level": "UNKNOWN",
                "score_explanation": "No database connected.",
                "tls_status": "UNKNOWN",
                "privilege_status": "UNKNOWN",
                "tables_scanned": 0,
                "total_findings": 0,
                "findings": [],
            }

        scanner = DatabasePostureScanner(
            connector=conn,
            user_id=user.user_id,
            selected_tables=req.tables,
        )
        result = scanner.run_full_scan()
        return result
    except Exception as e:
        logging.error(f"Database security scan error: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Security scan failed: {str(e)}",
            "connection_id": req.connection_id or "",
            "database_type": "error",
            "database_name": "error",
            "scanned_at": datetime.now(timezone.utc).isoformat(),
            "posture_score": None,
            "risk_level": "UNKNOWN",
            "score_explanation": "Scan failed due to an error.",
            "tls_status": "UNKNOWN",
            "privilege_status": "UNKNOWN",
            "tables_scanned": 0,
            "total_findings": 0,
            "findings": [],
        }


class SecurityExplainRequest(BaseModel):
    finding: dict[str, Any]


@app.post("/security/explain")
@limiter.limit("30/minute")
def security_explain_endpoint(
    req: SecurityExplainRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Generates a structured, actionable AI explanation and prioritized remediation advice
    for a specific security finding, with zero raw secret exposure.
    """
    _activate(user)
    try:
        from app.security.posture_scanner import explain_security_finding
        explanation = explain_security_finding(req.finding, use_llm=True)
        return {
            "status": "success",
            "explanation": explanation,
        }
    except Exception as e:
        logging.error(f"Security explain error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


# ── IP Threat Intelligence & Intrusion Detection Endpoints ────────────────────
class IPReputationQueryRequest(BaseModel):
    ip_address: str


class IPUnblockRequest(BaseModel):
    ip_address: str


@app.get("/security/ip-threats")
@limiter.limit("60/minute")
def list_ip_threats_endpoint(
    request: Request,
    ip_address: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Returns recorded IP threat alerts and intrusion events from the SecurityEventManager.
    """
    _activate(user)
    try:
        store = get_audit_store()
        sev_enum = SecurityEventSeverity(severity) if severity else None
        events = store.list_security_events(
            user_id=user.user_id,
            severity=sev_enum,
            ip_address=ip_address,
            limit=limit,
            offset=offset,
        )

        # Filter events that have source_ip in metadata or are intrusion/threat events
        threat_events = []
        for e in events:
            meta = e.metadata or {}
            ip = meta.get("source_ip")
            if ip or e.event_type in (
                SecurityEventType.BRUTE_FORCE_DETECTED,
                SecurityEventType.SUSPICIOUS_BURST_DETECTED,
                SecurityEventType.ENDPOINT_SCAN_DETECTED,
                SecurityEventType.IP_BLOCKED,
                SecurityEventType.AUTH_FAILURE,
                SecurityEventType.INJECTION_PATTERN_DETECTED,
                SecurityEventType.RATE_LIMIT_EXCEEDED,
                SecurityEventType.UNAUTHORIZED_ACCESS,
            ):
                threat_events.append(e.to_dict())

        engine = get_intrusion_engine()
        active_blocks = engine.list_active_blocks()

        return {
            "status": "success",
            "threat_events": threat_events,
            "active_blocks": active_blocks,
            "total_returned": len(threat_events),
        }
    except Exception as e:
        logging.error(f"IP threats listing error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.post("/security/ip-threats/reputation")
@limiter.limit("30/minute")
def query_ip_reputation_endpoint(
    req: IPReputationQueryRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Queries local evidence or optional threat intelligence provider for IP reputation.
    """
    _activate(user)
    try:
        provider = get_reputation_provider()
        rep = provider.query_reputation(req.ip_address)
        return {"status": "success", "reputation": rep}
    except Exception as e:
        logging.error(f"IP reputation query error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.post("/security/ip-threats/unblock")
@limiter.limit("20/minute")
def unblock_ip_endpoint(
    req: IPUnblockRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Administrative endpoint to remove an active temporary IP block.
    """
    _activate(user)
    try:
        engine = get_intrusion_engine()
        success = engine.remove_block(req.ip_address, admin_user_id=user.user_id)
        return {
            "status": "success" if success else "not_found",
            "message": f"IP {req.ip_address} unblocked." if success else f"No active block found for {req.ip_address}.",
            "unblocked": success,
        }
    except Exception as e:
        logging.error(f"IP unblock error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


# =============================================================================
# ── AI DATABASE GUARDIAN ROUTES ──────────────────────────────────────────────
# =============================================================================
from app.guardian.service import GuardianService
from app.guardian.models import IncidentStatus, IncidentSeverity
from app.connectors.registry import get_connection_registry


class GuardianIncidentStatusRequest(BaseModel):
    status: str  # acknowledged | resolved
    notes: Optional[str] = None


@app.get("/guardian/metrics")
@limiter.limit("60/minute")
def get_guardian_metrics(
    request: Request,
    connection_id: Optional[str] = None,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Returns real live engine telemetry metrics for the active connection.
    Guarantees: Zero fabricated metrics; reports unsupported as unavailable.
    """
    _activate(user, connection_id=connection_id, request=request)
    try:
        reg = get_connection_registry()
        connector = reg.get_connector(user.user_id, connection_id) if connection_id else reg.get_active_connector(user.user_id)
        
        engine = get_engine()
        db_type = get_current_db_type()
        identity = (connector.name if connector else None) or get_database_connection_info() or db_type
        
        telemetry = GuardianService.get_live_telemetry(
            user_id=user.user_id,
            engine=engine,
            db_type=db_type,
            identity=identity,
            connector=connector,
        )
        return {
            "status": "success",
            "telemetry": telemetry.to_dict(),
        }
    except Exception as e:
        logging.error(f"Guardian metrics error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.post("/guardian/diagnose")
@limiter.limit("30/minute")
def run_guardian_diagnosis(
    request: Request,
    connection_id: Optional[str] = None,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Triggers an on-demand comprehensive operational diagnosis.
    Separates facts, rule-based detections, root cause hypotheses, and safe verification steps.
    """
    _activate(user, connection_id=connection_id, request=request)
    try:
        reg = get_connection_registry()
        connector = reg.get_connector(user.user_id, connection_id) if connection_id else reg.get_active_connector(user.user_id)
        
        engine = get_engine()
        db_type = get_current_db_type()
        identity = (connector.name if connector else None) or get_database_connection_info() or db_type
        
        report = GuardianService.run_diagnosis(
            user_id=user.user_id,
            engine=engine,
            db_type=db_type,
            identity=identity,
            connector=connector,
        )
        return {
            "status": "success",
            "report": report.to_dict(),
        }
    except Exception as e:
        logging.error(f"Guardian diagnosis error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.get("/guardian/incidents")
@limiter.limit("60/minute")
def list_guardian_incidents(
    request: Request,
    database_identity: Optional[str] = None,
    status_filter: Optional[str] = None,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Lists user-isolated operational incidents from durable SQLite storage.
    """
    _activate(user, request=request)
    try:
        incidents = GuardianService.list_user_incidents(
            user_id=user.user_id,
            database_identity=database_identity,
            status_filter=status_filter,
        )
        return {
            "status": "success",
            "incidents": [inc.to_dict() for inc in incidents],
            "total": len(incidents),
        }
    except Exception as e:
        logging.error(f"Guardian incidents query error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.post("/guardian/incidents/{incident_id}/status")
@limiter.limit("30/minute")
def update_guardian_incident_status(
    incident_id: str,
    req: GuardianIncidentStatusRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Acknowledge or resolve an incident. Never performs automatic mutations.
    """
    _activate(user, request=request)
    try:
        norm_status = req.status.lower().strip()
        if norm_status not in ("acknowledged", "resolved"):
            raise HTTPException(status_code=400, detail="Invalid status. Must be 'acknowledged' or 'resolved'.")
        
        new_status = IncidentStatus.ACKNOWLEDGED if norm_status == "acknowledged" else IncidentStatus.RESOLVED
        updated = GuardianService.update_incident_status(
            user_id=user.user_id,
            incident_id=incident_id,
            new_status=new_status,
            actor_name=user.username,
            notes=req.notes,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Incident not found or unauthorized.")
        
        return {
            "status": "success",
            "incident": updated.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Guardian incident update error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}



