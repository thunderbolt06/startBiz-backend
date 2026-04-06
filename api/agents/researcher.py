"""
Step 2 & 3 — Research Orchestrator
Uses Gemini to plan which data tools to call, then executes them in parallel.
"""

import json
import asyncio
from google import genai
from google.genai import types
from django.conf import settings

from api.tools.google_places import search_places
from api.tools.demographics import fetch_demographics
from api.tools.earnings import fetch_earnings

RESEARCH_PLANNER_PROMPT = """You are a business research planning agent.
Given a business idea prompt, your job is to plan which data sources to query.

Available tools:
1. google_places — searches for nearby businesses of a specific type in an area
   args: {"query": "string (business type)", "location": "string (city/area)", "radius": number (meters, default 5000)}

2. demographics — fetches population density and demographic data for a location
   args: {"location": "string (city/area, country)", "country_code": "string (ISO 2-letter, e.g. IN, US)"}

3. earnings — fetches average household income / earnings data for a location
   args: {"location": "string (city/area)", "country_code": "string (ISO 2-letter)"}

You must respond with valid JSON only — a list of tool calls to make:
[
  {"tool": "google_places", "args": {"query": "gift shops", "location": "Bandra, Mumbai", "radius": 3000}},
  {"tool": "google_places", "args": {"query": "retail stores", "location": "Bandra, Mumbai", "radius": 3000}},
  {"tool": "demographics", "args": {"location": "Mumbai, India", "country_code": "IN"}},
  {"tool": "earnings", "args": {"location": "Mumbai", "country_code": "IN"}}
]

Plan 3-6 tool calls that will give the most relevant context for the business idea.
Think about: direct competitors, adjacent competitors, target demographic data, economic data.
"""


def plan_research(prompt: str, validation_summary: str = "") -> list:
    """Uses Gemini to decide which tools to call and with what arguments."""
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    message = f"Business Idea: {prompt}"
    if validation_summary:
        message += f"\nSummary: {validation_summary}"

    try:
        response = client.models.generate_content(
            model=settings.GEMINI_TEXT_MODEL,
            contents=message,
            config=types.GenerateContentConfig(
                system_instruction=RESEARCH_PLANNER_PROMPT,
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )
        plan = json.loads(response.text)
        if isinstance(plan, list):
            return plan
        return []
    except Exception:
        return []


TOOL_DISPATCH = {
    "google_places": search_places,
    "demographics": fetch_demographics,
    "earnings": fetch_earnings,
}


async def _execute_tool_async(tool_name: str, args: dict) -> dict:
    """Executes a single tool call, wrapping sync functions in an executor."""
    tool_fn = TOOL_DISPATCH.get(tool_name)
    if not tool_fn:
        return {"tool": tool_name, "error": f"Unknown tool: {tool_name}"}

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, lambda: tool_fn(**args))
        return {"tool": tool_name, "args": args, "data": result}
    except Exception as e:
        return {"tool": tool_name, "args": args, "error": str(e)}


async def _execute_all_tools_async(tool_plan: list) -> list:
    tasks = [
        _execute_tool_async(item.get("tool", ""), item.get("args", {}))
        for item in tool_plan
    ]
    return await asyncio.gather(*tasks)


def execute_tool_plan(tool_plan: list) -> list:
    """Synchronous entry point — runs all tools concurrently and returns results."""
    try:
        loop = asyncio.new_event_loop()
        results = loop.run_until_complete(_execute_all_tools_async(tool_plan))
        loop.close()
        return list(results)
    except Exception as e:
        return [{"error": str(e)}]
