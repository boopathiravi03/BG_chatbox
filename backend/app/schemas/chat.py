from pydantic import BaseModel


class ChatResponse(BaseModel):
    generated_sql: str
    result: dict
    explanation: str
    chart: dict | None = None
    diagram: str | None = None
