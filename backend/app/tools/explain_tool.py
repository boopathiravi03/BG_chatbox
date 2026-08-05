from app.agent.groq_agent import ask_groq


def explain_data(question: str, sql: str, result: dict):
    prompt = f"""
You are a business data analyst.

User Question:
{question}

Generated SQL:
{sql}

Database Result:
{result}

Write a short, clear explanation in simple English.

Do not mention SQL unless necessary.
If there are no rows, clearly say that no matching data was found.
"""

    return ask_groq(prompt)
