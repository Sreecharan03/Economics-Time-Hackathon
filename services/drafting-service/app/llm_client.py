"""Thin Groq wrapper, same pattern as extraction-service/app/llm_client.py --
kept separate from drafter.py so tests can inject a fake llm_fn."""
import os


class LLMNotConfigured(RuntimeError):
    pass


MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


def is_configured() -> bool:
    return bool(os.environ.get("GROQ_API_KEY"))


def call_groq(system_prompt: str, user_content: str) -> str:
    if not is_configured():
        raise LLMNotConfigured(
            "GROQ_API_KEY is not set. drafting-service needs it to do anything -- "
            "there is no non-LLM path for this service, by design (see README.md)."
        )
    from groq import Groq

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    return resp.choices[0].message.content
