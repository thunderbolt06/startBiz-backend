"""
Step 4 — Thesis Generator
Synthesises the user prompt, validation summary and all tool results into
a structured business-research thesis document (markdown).
"""

import json
from google import genai
from google.genai import types
from django.conf import settings

THESIS_SYSTEM_PROMPT = """You are an expert business research analyst and strategy consultant.
Your job is to write a comprehensive, data-driven business thesis document.

Given a business idea and research data from multiple sources, produce a well-structured
markdown document with the following sections:

# [Business Idea Title]

## Executive Summary
2-3 paragraphs covering what the idea is, what the research found, and the overall verdict.

## Market Analysis
- Target market size and demographics
- Market trends (cite numbers from the data)
- Consumer demand indicators

## Competitive Landscape
- Existing competitors found (list with details)
- Market saturation level
- Gaps identified

## Location & Demographics
- Area-specific data (population density, demographics)
- Economic profile (income levels, spending power)
- Foot traffic and access considerations

## Opportunity Assessment
- Why this could work (bull case)
- Why it might not work (bear case)
- Key success factors

## Opportunity Score
Provide a score from 1–10 with justification. Use this format:
**Opportunity Score: X/10** — [one sentence reason]

## Risks & Challenges
Bullet list of the top 5-7 risks.

## Strategic Recommendation
Clear, actionable recommendation: GO / GO WITH CAUTION / DO NOT GO
Followed by 3-5 specific next steps if they proceed.

---
Write in professional but accessible language. Use actual numbers from the data provided.
Be honest — if the data shows the market is saturated, say so clearly.
"""


def generate_thesis(prompt: str, tool_results: list, validation_summary: str = "") -> str:
    """
    Generates the full thesis markdown document from the prompt and all research data.
    """
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    data_section = json.dumps(tool_results, indent=2)
    message = f"""Business Idea Prompt:
{prompt}

{f"Validation Summary: {validation_summary}" if validation_summary else ""}

Research Data Collected:
{data_section}

Please write the full thesis document based on the above information.
"""

    try:
        response = client.models.generate_content(
            model=settings.GEMINI_TEXT_MODEL,
            contents=message,
            config=types.GenerateContentConfig(
                system_instruction=THESIS_SYSTEM_PROMPT,
                temperature=0.4,
                max_output_tokens=8192,
            ),
        )
        return response.text
    except Exception as e:
        return f"# Thesis Generation Error\n\nFailed to generate thesis: {str(e)}"
