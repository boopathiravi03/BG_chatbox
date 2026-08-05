from fastapi import APIRouter
from app.tools.generate_flowchart import generate_flowchart


router = APIRouter()


@router.get("/flowchart")
def flowchart():
    return {
        "type": "mermaid",
        "diagram": generate_flowchart()
    }
