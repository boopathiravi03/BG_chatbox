from app.agent.groq_agent import ask_groq


def explain_data(question, result):

    if not result:
        return "No result was returned."

    if not result.get("success", False):
        return (
            "The database operation could not be completed."
        )

    columns = result.get("columns", [])
    rows = result.get("rows", [])

    # NEVER send the entire database result to the LLM
    limited_rows = rows[:20]

    compact_result = {
        "columns": columns,
        "sample_rows": limited_rows,
        "rows_returned": result.get(
            "rows_returned",
            len(rows),
        ),
        "affected_rows": result.get(
            "affected_rows",
            0,
        ),
        "operation": result.get(
            "operation",
            "",
        ),
    }

    prompt = f"""
You are BG AI, a friendly database assistant.

User asked:
{question}

Database result:
{compact_result}

Explain the result in simple, natural English.

Rules:
- Do not mention SQL.
- Do not mention internal implementation.
- Do not say "the system told you".
- Do not invent information.
- If there are no rows, clearly say no matching records were found.
- If records exist, summarize what was found.
- Mention the number of records when available.
- Keep the answer concise.
- Sound like a real AI assistant.
"""

    try:
        return ask_groq(prompt).strip()

    except Exception:
        rows_count = result.get(
            "rows_returned",
            len(rows),
        )

        if rows_count == 0:
            return "I couldn't find any matching records."

        return (
            f"I found {rows_count} matching "
            f"record(s) in the database."
        )
