from fastapi import APIRouter
from app.tools.get_schema import get_schema

router = APIRouter()


@router.get("/schema")
def schema():
    return get_schema()
