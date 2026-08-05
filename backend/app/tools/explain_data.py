from app.agent.groq_agent import ask_groq


def explain_data(question, result):

    prompt = f"""
User Question:
{question}

Database Result:
{result}

Explain this result in simple English.

Mention important insights.

Don't mention SQL.
"""

    return ask_groq(prompt)
