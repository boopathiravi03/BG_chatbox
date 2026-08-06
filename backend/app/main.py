from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path

from app.agent.orchestrator import run_agent
from app.tools.get_schema import get_schema
from app.tools.get_relationship_graph import get_relationship_graph
from app.tools.dashboard_data import get_dashboard_data as get_analytics_data
from app.database.db import set_database, get_database_info, get_dashboard_data
from app.database.database_manager import connect_sqlite, connect_mysql, connect_postgres, get_current_db_type
from app.database.backup import create_backup, restore_backup, get_backup_dir
from app.tools.optimize_sql import optimize_sql
from fastapi.responses import FileResponse

app = FastAPI(title="BG AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str


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
        return run_agent(req.message)
    except Exception as e:
        return {
            "generated_sql": "",
            "result": {
                "success": False,
                "error": str(e)
            },
            "explanation": f"Error: {str(e)}"
        }


@app.post("/upload")
async def upload_database(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        upload_dir = Path(__file__).resolve().parents[2] / "database"
        upload_dir.mkdir(exist_ok=True)
        db_path = upload_dir / "ecommerce.db"
        db_path.write_bytes(contents)
        set_database(db_path)
        return {"status": "success", "message": "Database uploaded successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


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
        if req.db_type == "mysql":
            connect_mysql(
                req.host,
                req.port,
                req.database,
                req.username,
                req.password,
            )
        elif req.db_type == "postgres":
            connect_postgres(
                req.host,
                req.port,
                req.database,
                req.username,
                req.password,
            )
        else:
            return {"status": "error", "message": "Unsupported database type"}

        return {
            "status": "success",
            "database": req.db_type,
            "message": f"Connected to {req.db_type}",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


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
        db_path = Path(__file__).resolve().parents[2] / "database" / "ecommerce.db"
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

