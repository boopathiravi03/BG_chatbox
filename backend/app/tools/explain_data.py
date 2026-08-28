from app.agent.groq_agent import ask_groq


def explain_data(question, result):
    """
    Generate a short human-friendly explanation without
    sending the entire database result to the LLM.
    """

    if not result:
        return "No result was returned."

    if not result.get("success", False):
        return "I couldn't retrieve the requested data."

    columns = result.get("columns", [])
    rows = result.get("rows", [])
    rows_returned = result.get(
        "rows_returned",
        len(rows)
    )

    preview_rows = rows[:5]

    compact_result = {
        "columns": columns,
        "rows": preview_rows,
        "rows_returned": rows_returned,
    }

    prompt = f"""
You are BG AI, a database assistant.

User Question:
{question}

Database Result Summary:
{compact_result}

Give a short, clear explanation in simple English.

Rules:
- Do NOT mention SQL.
- Do NOT repeat the entire table.
- Mention the number of records returned.
- Mention 1-3 useful insights if visible.
- Keep the response under 100 words.
- If there are no rows, clearly say that no matching records were found.
"""

    try:
        return ask_groq(prompt).strip()

    except Exception:
        if rows_returned == 0:
            return "No matching records were found."

        return (
            f"I found {rows_returned} record(s) "
            "matching your request."
        )
