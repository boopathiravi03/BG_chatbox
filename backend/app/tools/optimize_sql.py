from app.agent.groq_agent import ask_groq
import json
import re


def optimize_sql(sql: str) -> dict:
    prompt = f"""You are a SQL optimization expert. Analyze and optimize the following SQL query.

Rules:
1. Replace SELECT * with explicit column names where possible.
2. Suggest indexes if relevant.
3. Avoid unnecessary subqueries.
4. Keep the query semantically identical.
5. Return ONLY valid JSON in this exact format, no markdown, no explanation:

{{
  "original_query": "the original SQL",
  "optimized_query": "the improved SQL",
  "improvements": ["improvement 1", "improvement 2"],
  "estimated_improvement": "X% Faster"
}}

SQL:
{sql}
"""

    try:
        response = ask_groq(prompt).strip()

        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            return result

        return {
            "original_query": sql,
            "optimized_query": sql,
            "improvements": ["Unable to parse optimization result"],
            "estimated_improvement": "N/A",
        }
    except Exception as e:
        return {
            "original_query": sql,
            "optimized_query": sql,
            "improvements": [f"Optimization failed: {str(e)}"],
            "estimated_improvement": "N/A",
        }
