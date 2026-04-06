"""
Step 1 — Prompt Validation Agent
Checks if the user's business idea prompt has sufficient context to proceed with deep research.
Returns either a go-ahead or a structured list of missing information / follow-up questions.
"""

import json
from google import genai
from google.genai import types
from django.conf import settings

VALIDATION_SYSTEM_PROMPT = """You are a business research quality-control agent.
Your job is to evaluate whether a business idea prompt has enough information for deep market research.

A good prompt should include (ideally):
- A specific business idea or prediction (what product/service)
- A geographic location or target market
- Some context about why the person thinks there is an opportunity
- Any data or evidence they already have

You must respond with valid JSON only, no markdown fences, no extra text.

If the prompt is SUFFICIENT:
{"status": "ok", "summary": "one sentence summary of the idea", "key_aspects": ["aspect1", "aspect2"]}

If the prompt is INSUFFICIENT:
{
  "status": "insufficient",
  "missing": ["list of missing pieces of context"],
  "questions": ["specific question to ask the user", "another question"],
  "suggestion": "a one paragraph suggestion on how to improve the prompt"
}
"""


def validate_prompt(prompt: str, extra_data: dict = None) -> dict:
    """
    Validates whether the business idea prompt has enough context for research.
    Returns a dict with status and guidance.
    """
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    user_message = f"Business Idea Prompt:\n{prompt}"
    if extra_data:
        user_message += f"\n\nAdditional Data Provided:\n{json.dumps(extra_data, indent=2)}"

    try:
        response = client.models.generate_content(
            model=settings.GEMINI_TEXT_MODEL,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=VALIDATION_SYSTEM_PROMPT,
                temperature=0.2,
                response_mime_type="application/json",
            ),
        )
        result = json.loads(response.text)
        # Gemini sometimes wraps the object in a list — unwrap it
        if isinstance(result, list):
            result = result[0] if result else {}
        return result
    except (json.JSONDecodeError, Exception) as e:
        return {
            "status": "ok",
            "summary": prompt[:200],
            "key_aspects": [],
            "_parse_error": str(e),
        }
