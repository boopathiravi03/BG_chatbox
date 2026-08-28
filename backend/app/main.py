from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import re

from app.agent.orchestrator import run_agent, clear_pending_insert
from app.tools.get_schema import get_schema
from app.tools.execute_query import validate_sql, execute_query
from app.tools.get_relationship_graph import get_relationship_graph
from app.tools.dashboard_data import get_dashboard_data as get_analytics_data
from app.tools.analyze_database import analyze_database
from app.database.db import get_database_info, get_dashboard_data
from app.database.database_manager import connect_sqlite, connect_mysql, connect_postgres, get_current_db_type, get_engine, get_database_connection_info, disconnect_database
from app.database.database_context import refresh_database_profile, get_database_profile, clear_database_profile
from app.database.backup import create_backup, restore_backup, get_backup_dir
from app.tools.optimize_sql import optimize_sql
from fastapi.responses import FileResponse
from app.agent.orchestrator import generate_suggestions

app = FastAPI(title="BG AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    """
    Start BG AI without connecting to any database.
    The user must explicitly upload or connect a database.
    """
    clear_database_profile()


class ChatRequest(BaseModel):
    message: str = ""
    session_id: str = "default"
    input_values: dict | None = None
    pending_insert: bool = False


class ConfirmQueryRequest(BaseModel):
    sql: str


class DatabaseConnection(BaseModel):
    db_type: str
    host: str
    port: int
    database: str
    username: str
    password: str


class OptimizationRequest(BaseModel):
    sql: str


@app.get("/")
def home():
    return {"message": "Welcome to BG AI Backend"}


@app.post("/chat")
def chat(req: ChatRequest):
    try:
        return run_agent(
            req.message,
            req.session_id,
        )

    except Exception as e:
        return {
            "generated_sql": "",
            "result": {
                "success": False,
                "error": str(e),
            },
            "explanation": f"Error: {str(e)}",
            "followups": [],
        }


@app.post("/confirm-query")
def confirm_query(request: ConfirmQueryRequest):
    try:
        sql = request.sql.strip()

        if not sql:
            return {
                "success": False,
                "error": "No SQL query was provided."
            }

        # Remove markdown code fences
        sql = re.sub(
            r"```(?:sql|mysql|postgresql)?",
            "",
            sql,
            flags=re.IGNORECASE
        )
        sql = sql.replace("```", "").strip()

        # Remove final semicolon
        sql = sql.rstrip(";").strip()

        print("\n========== CONFIRM QUERY ==========")
        print("SQL:", sql)

        validation = validate_sql(sql)

        print("VALIDATION:", validation)

        if not validation.get("allowed"):
            return {
                "success": False,
                "error": validation.get(
                    "reason",
                    "Query is not allowed."
                ),
                "operation": validation.get(
                    "operation",
                    ""
                ),
            }

        if not validation.get("requires_confirmation"):
            return {
                "success": False,
                "error": (
                    "This query does not require confirmation."
                ),
            }

        # IMPORTANT:
        # Actually execute the confirmed DELETE/UPDATE/INSERT
        result = execute_query(sql)

        print("EXECUTION RESULT:", result)
        print("==================================\n")

        if result.get("success"):
            clear_pending_insert()

            return {
                **result,
                "confirmed": True,
                "message": "Database updated successfully.",
            }

        return {
            **result,
            "confirmed": False,
        }

    except Exception as e:
        import traceback
        traceback.print_exc()

        return {
            "success": False,
            "confirmed": False,
            "error": str(e),
        }


@app.post("/upload")
async def upload_database(file: UploadFile = File(...)):
    try:
        contents = await file.read()

        upload_dir = (
            Path(__file__).resolve().parents[2]
            / "database"
        )

        upload_dir.mkdir(exist_ok=True)

        safe_name = Path(file.filename).name
        db_path = upload_dir / safe_name
        db_path.write_bytes(contents)

        # Make uploaded SQLite the ACTIVE database
        connect_sqlite(str(db_path))

        profile = refresh_database_profile()

        return {
            "status": "success",
            "message": "Database uploaded successfully",
            "database": db_path.name,
            "tables": list(get_schema().keys()),
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


@app.post("/backup")
def backup_database():
    try:
        return create_backup()
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/restore")
async def restore_database(file: UploadFile = File(...)):
    try:
        backup_dir = get_backup_dir()
        backup_path = backup_dir / file.filename

        contents = await file.read()
        backup_path.write_bytes(contents)

        result = restore_backup(backup_path)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/download-backup")
def download_backup():
    try:
        backup_dir = get_backup_dir()
        backups = sorted(backup_dir.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)

        if not backups:
            return {"status": "error", "message": "No backups found"}

        latest = backups[0]
        return FileResponse(
            path=str(latest),
            filename=latest.name,
            media_type="application/octet-stream",
        )
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/connect")
def connect_database(req: DatabaseConnection):

    try:

        # Completely remove previous connection
        disconnect_database()

        if req.db_type == "mysql":

            connect_mysql(
                req.host,
                req.port,
                req.database,
                req.username,
                req.password,
            )

            # Verify the SAME engine used by query execution
            from app.database.database_manager import get_engine

            engine = get_engine()

            if engine is None:
                raise RuntimeError("MySQL engine was not created.")

            with engine.connect() as conn:
                conn.exec_driver_sql("SELECT 1")

        elif req.db_type == "postgres":

            connect_postgres(
                req.host,
                req.port,
                req.database,
                req.username,
                req.password,
            )

        else:
            return {
                "status": "error",
                "message": "Unsupported database type",
            }

        # Analyze ONLY the newly connected database
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
            "analysis": (
                profile.to_context()
                if profile
                else ""
            ),
        }
    except Exception as e:
        error_message = str(e)
        if "1045" in error_message:
            friendly_message = (
                "Access denied. Please check your "
                "username and password."
            )
        elif (
            "does not exist" in error_message
            and "database" in error_message.lower()
        ):
            friendly_message = (
                "Database does not exist. "
                "Please create the database first."
            )
        elif (
            "2003" in error_message
            or "Can't connect to MySQL server"
            in error_message
        ):
            friendly_message = (
                "Cannot connect to MySQL server. "
                "Check the server, host and port."
            )
        else:
            friendly_message = (
                f"Connection failed: {error_message}"
            )
        return {
            "status": "error",
            "message": friendly_message,
        }


@app.post("/disconnect")
def disconnect():
    try:
        disconnect_database()
        clear_database_profile()

        # Clear pending AI operations
        clear_pending_insert()

        # Clear conversation state
        try:
            from app.agent.orchestrator import conversation_state
            conversation_state.clear()
        except Exception:
            pass

        return {
            "status": "success",
            "message": "Database disconnected successfully",
            "db_type": "none",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


@app.post("/optimize")
def optimize_sql_endpoint(req: OptimizationRequest):
    try:
        result = optimize_sql(req.sql)
        return result
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "original_query": req.sql,
            "optimized_query": req.sql,
            "improvements": [],
            "estimated_improvement": "N/A",
        }


@app.get("/schema")
def schema():
    try:
        return get_schema()
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/clear-db")
def clear_db():
    try:
        from app.database.db import get_database_path
        db_path = get_database_path()
        if db_path.exists():
            db_path.unlink()
        return {"status": "success", "message": "Database cleared"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/database-info")
def database_info():
    try:
        return get_database_info()
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/database-type")
def database_type():
    try:
        return {"db_type": get_current_db_type()}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/database-connection-info")
def database_connection_info():
    try:
        return get_database_connection_info()
    except Exception as e:
        return {
            "connected": False,
            "db_type": "none",
            "error": str(e),
        }


@app.get("/suggestions")
def suggestions():
    try:
        schema = get_schema()
        profile = get_database_profile()
        database_context = profile.to_context() if profile and profile.analyzed else ""
        return {"suggestions": generate_suggestions(schema, database_context)}
    except Exception as e:
        return {"status": "error", "message": str(e), "suggestions": []}


@app.get("/dashboard")
def dashboard():
    try:
        return get_dashboard_data()
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/analytics")
def analytics():
    try:
        return get_analytics_data()
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/relationship-graph")
def relationship_graph():
    try:
        return get_relationship_graph()
    except Exception as e:
        return {"status": "error", "message": str(e)}


print("\n===== REGISTERED ROUTES =====")
for route in app.routes:
    print(route.path, route.methods)
print("=============================\n")

