from fastapi import APIRouter
from pydantic import BaseModel

from app.tools.execute_query import execute_query

router = APIRouter()


class QueryRequest(BaseModel):
    query: str


@router.post("/query")
def run_query(request: QueryRequest):
    return execute_query(request.query)
