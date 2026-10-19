import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b"
)

_client = None


def get_groq_client() -> Groq:
    """Returns the Groq client instance, initializing it lazily when an API key is available."""
    global _client
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY is not configured. Please set GROQ_API_KEY in your desktop settings or environment variables."
        )
    if _client is None:
        _client = Groq(api_key=api_key)
    return _client


class _LazyGroqClient:
    """Proxy object so code importing `client` continues to work seamlessly."""
    def __getattr__(self, name):
        c = get_groq_client()
        return getattr(c, name)


client = _LazyGroqClient()


def ask_groq(prompt: str):
    cl = get_groq_client()
    response = cl.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.1,
    )

    return response.choices[0].message.content
