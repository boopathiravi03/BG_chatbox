from app.agent.groq_agent import ask_groq


def explain_data(question, result):

    if not result:
        return "I couldn't get a result from the database."

    if not result.get("success", False):
        error = result.get("error", "")
        return (
            "I couldn't complete that request."
            + (f" {error}" if error else "")
        )

    columns = result.get("columns", [])
    rows = result.get("rows", [])

    rows_returned = result.get(
        "rows_returned",
        len(rows)
    )

    # ---------------------------------------------------------
    # No results
    # ---------------------------------------------------------

    if rows_returned == 0:

        return (
            "I couldn't find any records matching "
            "your request."
        )

    # ---------------------------------------------------------
    # Only send a SMALL preview to Groq
    # ---------------------------------------------------------

    preview = rows[:5]

    prompt = f"""
You are BG AI, a friendly AI database assistant.

User asked:
{question}

The database returned:
Columns: {columns}
Number of matching records: {rows_returned}
Preview:
{preview}

Respond naturally to the user.

Rules:
- Understand the user's original intention.
- Do not talk about internal system fields.
- Do not mention SQL.
- Do not explain "success", "rows_returned",
  "affected_rows", or database execution internals.
- Do not repeat the complete table.
- Mention the important result.
- If useful, mention the number of records.
- Keep the answer concise.
- Sound like a real AI assistant.
- Correct obvious spelling mistakes mentally.
"""

    try:
        return ask_groq(prompt).strip()

    except Exception:

        return (
            f"I found {rows_returned} "
            "record(s) matching your request."
        )
