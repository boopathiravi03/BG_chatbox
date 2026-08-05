from fastapi import APIRouter
from pydantic import BaseModel

from app.services.agent_service import agent
from app.schemas.chat import ChatResponse

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    question = request.message.lower()

    if "er diagram" in question or "schema" in question:
        return ChatResponse(
            generated_sql="",
            result={
                "success": True,
                "columns": [],
                "rows": []
            },
            explanation="Here is the Entity Relationship diagram of your database.",
            chart=None,
            flowchart=agent.generate_er()
        )

    result = agent.run_query(agent.get_database_schema())

    return ChatResponse(
        generated_sql="",
        result=result,
        explanation="",
        chart=None,
        flowchart=None
    )
