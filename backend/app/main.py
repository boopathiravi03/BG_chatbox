from __future__ import annotations

import os
import re
import logging
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# ── App init & Rate Limiter ───────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="BG AI", version="7.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
_PRODUCTION_ORIGINS = ["https://thebg.co.in"]
_DEV_ORIGINS = os.getenv("BGAI_EXTRA_ORIGINS", "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000").split(",")
_ALLOWED_ORIGINS = _PRODUCTION_ORIGINS + [o.strip() for o in _DEV_ORIGINS if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


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

# ── Auth & Context imports ────────────────────────────────────────────────────
from app.security.auth import create_access_token
from app.security.sessions import (
    get_current_user, AuthenticatedUser,
    register_user, authenticate_user, get_user_by_id,
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


class ChatRequest(BaseModel):
    message: str = ""
    session_id: str = "default"
    input_values: dict | None = None
    pending_insert: bool = False


class ConfirmQueryRequest(BaseModel):
    session_id: str


class DatabaseConnection(BaseModel):
    db_type: str
    host: str = ""
    port: int = 3306
    database: str = ""
    username: str = ""
    password: str = ""


class OptimizationRequest(BaseModel):
    sql: str


class QueryRequest(BaseModel):
    query: str


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


def _activate(user: AuthenticatedUser):
    set_user_context_for_request(user.user_id)


# =============================================================================
# PUBLIC ENDPOINTS
# =============================================================================

@app.get("/")
def home():
    return {"message": "BG AI Backend v7", "status": "operational"}


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


@app.post("/auth/login")
@limiter.limit("10/minute")
def auth_login(req: LoginRequest, request: Request):
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(user["user_id"], user["username"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user["user_id"],
        "username": user["username"],
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
    _activate(user)
    try:
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
        return execute_confirmed(f"{user.user_id}:{request.session_id}")
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

        upload_dir = Path(__file__).resolve().parents[2] / "database"
        upload_dir.mkdir(exist_ok=True)
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
def disconnect(user: AuthenticatedUser = Depends(get_current_user)):
    try:
        clear_user_context(user.user_id)
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
def schema_endpoint(user: AuthenticatedUser = Depends(get_current_user)):
    _activate(user)
    try:
        return get_schema()
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/database-info")
def database_info(user: AuthenticatedUser = Depends(get_current_user)):
    _activate(user)
    try:
        return get_database_info()
    except Exception as e:
        return {
            "connected": False,
            "db_type": "none",
            "database": "Not Connected",
            "tables": 0,
            "rows": 0,
            "columns": 0,
            "size": "0 B",
            "error": str(e),
        }


@app.get("/database-type")
def database_type(user: AuthenticatedUser = Depends(get_current_user)):
    _activate(user)
    try:
        eng = get_engine()
        db_t = get_current_db_type()
        return {
            "connected": eng is not None and db_t != "none",
            "db_type": db_t,
        }
    except Exception as e:
        return {"connected": False, "db_type": "none", "error": str(e)}


@app.get("/database-connection-info")
def database_connection_info(user: AuthenticatedUser = Depends(get_current_user)):
    _activate(user)
    try:
        return get_database_connection_info()
    except Exception as e:
        return {"connected": False, "db_type": "none", "error": str(e)}


@app.post("/query")
@limiter.limit("30/minute")
def run_query(request: Request, req: QueryRequest, user: AuthenticatedUser = Depends(get_current_user)):
    _activate(user)
    try:
        return execute_query(req.query)
    except Exception as e:
        return {"success": False, "columns": [], "rows": [], "error": str(e), "rows_returned": 0}


@app.post("/optimize")
def optimize_sql_endpoint(req: OptimizationRequest, user: AuthenticatedUser = Depends(get_current_user)):
    _activate(user)
    try:
        return optimize_sql(req.sql)
    except Exception as e:
        return {"status": "error", "message": str(e), "original_query": req.sql, "optimized_query": req.sql, "improvements": []}


@app.get("/dashboard")
def dashboard(user: AuthenticatedUser = Depends(get_current_user)):
    _activate(user)
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
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        from app.intelligence.anomaly.detector import detect_anomalies
        report = detect_anomalies(force_refresh=force_refresh)
        return {"status": "success", "report": report.to_dict() if hasattr(report, "to_dict") else report}
    except Exception as e:
        return {"status": "error", "message": str(e), "report": None}


@app.get("/anomaly/summary")
def anomaly_summary_endpoint(
    user: AuthenticatedUser = Depends(get_current_user),
):
    _activate(user)
    try:
        from app.intelligence.anomaly.detector import detect_anomalies
        report = detect_anomalies(force_refresh=False)
        rep_dict = report.to_dict() if hasattr(report, "to_dict") else report
        return {
            "status": "success",
            "critical_count": rep_dict.get("summary", {}).get("critical_count", 0),
            "warning_count": rep_dict.get("summary", {}).get("warning_count", 0),
            "info_count": rep_dict.get("summary", {}).get("info_count", 0),
            "total_count": rep_dict.get("total_anomalies", 0),
            "clean_tables": rep_dict.get("clean_tables", []),
            "anomalies": rep_dict.get("anomalies", []),
        }
    except Exception as e:
        return {
            "status": "error",
            "critical_count": 0,
            "warning_count": 0,
            "info_count": 0,
            "total_count": 0,
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

