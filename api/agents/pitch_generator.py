"""
Step 5 — Pitch Deck Generator
Takes the thesis document and generates:
  1. A JSON slide manifest
  2. A self-contained HTML pitch deck (with Chart.js charts + Gemini-generated images)
  3. A PDF export via WeasyPrint
  4. An MP3 audio narration via Google Cloud TTS
"""

import json
import base64
from google import genai
from google.genai import types
from django.conf import settings

SLIDE_PLANNER_PROMPT = """You are a pitch deck design expert.
Given a business thesis document, create a compelling 8-10 slide pitch deck.

Return a JSON array of slide objects. Each slide must have:
{
  "slide_number": 1,
  "title": "Slide title",
  "type": "title|text|chart|image|split",
  "content": "Main body text or bullet points (use \\n for newlines)",
  "speaker_notes": "What to say aloud for this slide (2-4 sentences)",
  "chart_data": null or {
    "type": "bar|pie|line|doughnut",
    "labels": ["label1", "label2"],
    "datasets": [{"label": "Series name", "data": [1, 2, 3]}],
    "title": "Chart title"
  },
  "needs_image": true or false,
  "image_prompt": "Detailed prompt for generating a visual infographic for this slide (only if needs_image is true)"
}

Slide types:
- "title": Opening slide with headline and tagline
- "text": Text-heavy slide with bullet points
- "chart": Data visualization slide (always set chart_data)
- "image": Visual/infographic-heavy slide (set needs_image: true)
- "split": Half text, half chart or image

Required slides (in order):
1. Title slide — business name, tagline, one-liner
2. The Problem / Opportunity
3. Market Size & Demographics (chart)
4. Competitive Landscape (chart — bar chart of competitor counts/ratings)
5. Location Analysis (image — area map or demographic visual)
6. Financial Opportunity (chart — income/spending data)
7. Why Now / Tailwinds
8. Opportunity Score & Recommendation
9. Risk Assessment
10. Next Steps / Call to Action

Return ONLY the JSON array. No markdown, no extra text.
"""


def _generate_slide_image(image_prompt: str) -> str | None:
    """
    Generates an infographic image using Gemini Flash Image model.
    Returns base64-encoded PNG string or None on failure.
    """
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(
            model=settings.GEMINI_IMAGE_MODEL,
            contents=(
                f"Create a clean, professional business infographic: {image_prompt}. "
                "Style: modern, minimal, white background, use blues and greens. No text overlays."
            ),
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                return base64.b64encode(part.inline_data.data).decode("utf-8")
    except Exception:
        pass
    return None


def generate_slide_manifest(thesis_md: str) -> list:
    """Uses Gemini to create the JSON slide manifest from the thesis."""
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    try:
        response = client.models.generate_content(
            model=settings.GEMINI_TEXT_MODEL,
            contents=f"Create a pitch deck from this business thesis:\n\n{thesis_md}",
            config=types.GenerateContentConfig(
                system_instruction=SLIDE_PLANNER_PROMPT,
                temperature=0.3,
                response_mime_type="application/json",
            ),
        )
        slides = json.loads(response.text)
        if isinstance(slides, list):
            return slides
        return []
    except Exception:
        return []


def _escape_html(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _content_to_html(content: str) -> str:
    """Converts slide content text to HTML bullet points or paragraphs."""
    lines = [l.strip() for l in content.split("\n") if l.strip()]
    if len(lines) <= 1:
        return f"<p>{_escape_html(content)}</p>"
    items = "".join(
        f"<li>{_escape_html(line.lstrip('•-* '))}</li>" for line in lines
    )
    return f"<ul>{items}</ul>"


def _build_slide_html(slide: dict, image_b64: str | None = None) -> str:
    """Renders a single slide as an HTML div."""
    slide_type = slide.get("type", "text")
    title = _escape_html(slide.get("title", ""))
    content = slide.get("content", "")
    chart_data = slide.get("chart_data")
    slide_num = slide.get("slide_number", 1)
    chart_id = f"chart_{slide_num}"

    content_html = _content_to_html(content)

    chart_section = ""
    if chart_data:
        chart_json = json.dumps(chart_data)
        chart_section = f"""
        <div class="chart-container">
          <canvas id="{chart_id}"></canvas>
        </div>
        <script>
          (function() {{
            var ctx = document.getElementById('{chart_id}').getContext('2d');
            var chartData = {chart_json};
            new Chart(ctx, {{
              type: chartData.type || 'bar',
              data: {{
                labels: chartData.labels,
                datasets: chartData.datasets.map(function(ds) {{
                  return Object.assign({{
                    backgroundColor: ['#3B82F6','#10B981','#F59E0B','#EF4444','#8B5CF6','#06B6D4','#F97316'],
                    borderColor: '#1E3A5F',
                    borderWidth: 1
                  }}, ds);
                }})
              }},
              options: {{
                responsive: true,
                plugins: {{
                  legend: {{ position: 'bottom' }},
                  title: {{ display: true, text: chartData.title || '' }}
                }}
              }}
            }});
          }})();
        </script>
        """

    image_section = ""
    if image_b64:
        image_section = f'<div class="slide-image"><img src="data:image/png;base64,{image_b64}" alt="Infographic" /></div>'

    if slide_type == "title":
        return f"""
        <div class="slide slide-title" id="slide-{slide_num}">
          <div class="slide-inner">
            <h1>{title}</h1>
            <div class="tagline">{content_html}</div>
          </div>
        </div>"""

    if slide_type == "chart":
        return f"""
        <div class="slide slide-chart" id="slide-{slide_num}">
          <div class="slide-inner">
            <h2>{title}</h2>
            {chart_section}
          </div>
        </div>"""

    if slide_type == "image":
        return f"""
        <div class="slide slide-image-type" id="slide-{slide_num}">
          <div class="slide-inner">
            <h2>{title}</h2>
            {image_section or content_html}
          </div>
        </div>"""

    if slide_type == "split":
        return f"""
        <div class="slide slide-split" id="slide-{slide_num}">
          <div class="slide-inner">
            <h2>{title}</h2>
            <div class="split-layout">
              <div class="split-left">{content_html}</div>
              <div class="split-right">{chart_section or image_section}</div>
            </div>
          </div>
        </div>"""

    return f"""
    <div class="slide slide-text" id="slide-{slide_num}">
      <div class="slide-inner">
        <h2>{title}</h2>
        <div class="slide-body">{content_html}</div>
      </div>
    </div>"""


PITCH_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{deck_title}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0F172A; color: #E2E8F0; }}

  .deck-nav {{
    position: fixed; top: 0; left: 0; right: 0; z-index: 100;
    background: rgba(15,23,42,0.95); backdrop-filter: blur(8px);
    padding: 12px 24px; display: flex; align-items: center; justify-content: space-between;
    border-bottom: 1px solid #1E3A5F;
  }}
  .deck-nav .nav-title {{ font-size: 14px; font-weight: 600; color: #60A5FA; }}
  .deck-nav .controls {{ display: flex; gap: 8px; align-items: center; }}
  .deck-nav button {{
    background: #1E3A5F; border: none; color: #E2E8F0; padding: 6px 16px;
    border-radius: 6px; cursor: pointer; font-size: 13px; transition: background 0.2s;
  }}
  .deck-nav button:hover {{ background: #2563EB; }}
  .slide-counter {{ font-size: 13px; color: #94A3B8; min-width: 60px; text-align: center; }}

  .slides-container {{ padding-top: 60px; }}

  .slide {{
    min-height: 100vh; display: flex; align-items: center; justify-content: center;
    padding: 40px; scroll-margin-top: 60px;
  }}
  .slide-inner {{ max-width: 960px; width: 100%; }}

  .slide-title {{ background: linear-gradient(135deg, #0F172A 0%, #1E3A5F 50%, #0F172A 100%); }}
  .slide-title h1 {{
    font-size: clamp(36px, 5vw, 64px); font-weight: 800; color: #60A5FA;
    margin-bottom: 24px; line-height: 1.1;
  }}
  .slide-title .tagline {{ font-size: clamp(16px, 2vw, 22px); color: #94A3B8; }}
  .slide-title .tagline p {{ color: #94A3B8; font-size: 22px; }}

  .slide-text {{ background: #0F172A; }}
  .slide-text:nth-child(even) {{ background: #111827; }}
  .slide-text h2, .slide-chart h2, .slide-image-type h2, .slide-split h2 {{
    font-size: 32px; font-weight: 700; color: #60A5FA; margin-bottom: 28px;
  }}
  .slide-body ul, .split-left ul {{ list-style: none; padding: 0; }}
  .slide-body li, .split-left li {{
    padding: 10px 0 10px 20px; border-left: 3px solid #3B82F6;
    margin-bottom: 10px; font-size: 18px; color: #CBD5E1; line-height: 1.5;
  }}
  .slide-body p {{ font-size: 18px; color: #CBD5E1; line-height: 1.7; }}

  .slide-chart {{ background: #111827; }}
  .chart-container {{
    max-width: 700px; margin: 0 auto; background: #1E293B;
    border-radius: 12px; padding: 24px;
  }}

  .slide-image-type {{ background: #0F172A; }}
  .slide-image img {{
    max-width: 100%; border-radius: 12px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
  }}

  .slide-split {{ background: #111827; }}
  .split-layout {{
    display: grid; grid-template-columns: 1fr 1fr;
    gap: 32px; align-items: center;
  }}

  hr.slide-divider {{ border: none; border-top: 1px solid #1E3A5F; margin: 0; }}

  @media (max-width: 640px) {{
    .split-layout {{ grid-template-columns: 1fr; }}
    .slide {{ padding: 20px; }}
  }}
</style>
</head>
<body>

<nav class="deck-nav">
  <span class="nav-title">{deck_title}</span>
  <div class="controls">
    <button onclick="prevSlide()">&#8592; Prev</button>
    <span class="slide-counter" id="counter">1 / {total_slides}</span>
    <button onclick="nextSlide()">Next &#8594;</button>
  </div>
</nav>

<div class="slides-container" id="slides-container">
{slides_html}
</div>

<script>
  var slides = document.querySelectorAll('.slide');
  var current = 0;

  function updateCounter() {{
    document.getElementById('counter').textContent = (current + 1) + ' / ' + slides.length;
  }}

  function goToSlide(idx) {{
    current = Math.max(0, Math.min(idx, slides.length - 1));
    slides[current].scrollIntoView({{ behavior: 'smooth', block: 'start' }});
    updateCounter();
  }}

  function nextSlide() {{ goToSlide(current + 1); }}
  function prevSlide() {{ goToSlide(current - 1); }}

  document.addEventListener('keydown', function(e) {{
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') nextSlide();
    if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') prevSlide();
  }});

  var observer = new IntersectionObserver(function(entries) {{
    entries.forEach(function(entry) {{
      if (entry.isIntersecting) {{
        var num = parseInt(entry.target.id.replace('slide-', '')) - 1;
        if (!isNaN(num)) {{ current = num; updateCounter(); }}
      }}
    }});
  }}, {{ threshold: 0.5 }});

  slides.forEach(function(s) {{ observer.observe(s); }});
  updateCounter();
</script>
</body>
</html>
"""


def build_pitch_html(slides: list, deck_title: str = "Business Pitch Deck") -> str:
    """
    Builds the full self-contained HTML pitch deck.
    Generates images for slides that need them via Gemini Flash Image.
    """
    slides_html_parts = []
    for i, slide in enumerate(slides):
        image_b64 = None
        if slide.get("needs_image") and slide.get("image_prompt"):
            image_b64 = _generate_slide_image(slide["image_prompt"])

        slide_html = _build_slide_html(slide, image_b64)
        slides_html_parts.append(slide_html)
        if i < len(slides) - 1:
            slides_html_parts.append('<hr class="slide-divider" />')

    return PITCH_HTML_TEMPLATE.format(
        deck_title=_escape_html(deck_title),
        total_slides=len(slides),
        slides_html="\n".join(slides_html_parts),
    )


def html_to_pdf(html_content: str) -> bytes:
    """Converts the HTML pitch deck to PDF using WeasyPrint."""
    import os
    # On macOS with Homebrew, Pango/GObject live in /opt/homebrew/lib.
    # dlopen reads DYLD_FALLBACK_LIBRARY_PATH at call time, so setting it
    # here before the lazy import is sufficient.
    if os.path.isdir("/opt/homebrew/lib"):
        os.environ.setdefault("DYLD_FALLBACK_LIBRARY_PATH", "/opt/homebrew/lib")
    from weasyprint import HTML, CSS
    pdf_bytes = HTML(string=html_content, base_url=None).write_pdf(
        stylesheets=[
            CSS(string="""
                @page { size: 1280px 720px; margin: 0; }
                .deck-nav { display: none !important; }
                .slide { min-height: 720px; page-break-after: always; }
            """)
        ]
    )
    return pdf_bytes


def _build_narration_script(slides: list) -> str:
    """Concatenates slide speaker notes into a single narration script."""
    parts = []
    for slide in slides:
        notes = slide.get("speaker_notes", "")
        title = slide.get("title", "")
        if notes:
            parts.append(f"{title}. {notes}")
    return "  ".join(parts).strip()


def _google_tts(script: str, api_key: str) -> bytes:
    """
    Calls the Google Cloud Text-to-Speech REST API.
    Splits long scripts into ≤4900-char chunks and concatenates MP3 bytes.
    Raises on any failure so the caller can fall back to ElevenLabs.
    """
    import base64
    import requests

    GOOGLE_TTS_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
    CHUNK_SIZE = 4900

    def _synthesize_chunk(text: str) -> bytes:
        payload = {
            "input": {"text": text},
            "voice": {
                "languageCode": "en-US",
                "name": "en-US-Neural2-D",
                "ssmlGender": "MALE",
            },
            "audioConfig": {"audioEncoding": "MP3", "speakingRate": 0.95},
        }
        resp = requests.post(
            GOOGLE_TTS_URL,
            params={"key": api_key},
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return base64.b64decode(resp.json()["audioContent"])

    # Split into word-boundary chunks if needed
    if len(script) <= CHUNK_SIZE:
        return _synthesize_chunk(script)

    chunks, cursor = [], 0
    while cursor < len(script):
        end = cursor + CHUNK_SIZE
        if end >= len(script):
            chunk = script[cursor:]
        else:
            # Break at last space within the limit
            end = script.rfind(" ", cursor, end) or end
            chunk = script[cursor:end]
        chunks.append(chunk.strip())
        cursor = end

    return b"".join(_synthesize_chunk(c) for c in chunks if c)


def generate_audio_narration(slides: list) -> bytes | None:
    """
    Generates MP3 audio narration from slide speaker notes.
    Primary: Google Cloud TTS.
    Fallback: ElevenLabs (if Google fails or key is missing).
    Returns raw MP3 bytes or None if both providers are unavailable.
    """
    import logging
    import os
    from dotenv import load_dotenv
    from pathlib import Path

    logger = logging.getLogger(__name__)

    # Re-read .env so keys are always fresh in Celery worker processes
    _env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    load_dotenv(dotenv_path=_env_path, override=True)

    script = _build_narration_script(slides)
    if not script:
        logger.warning("No speaker notes in slides — skipping audio narration")
        return None

    logger.info(f"Narration script: {len(script)} chars")

    # ── Primary: Google TTS ──────────────────────────────────────────────────
    google_key = os.environ.get("GOOGLE_TTS_API_KEY", "").strip().strip('"').strip("'")
    if google_key:
        try:
            logger.info("Generating audio via Google Cloud TTS")
            audio_bytes = _google_tts(script, google_key)
            logger.info(f"Google TTS succeeded ({len(audio_bytes):,} bytes)")
            return audio_bytes
        except Exception as exc:
            logger.warning(f"Google TTS failed ({exc}) — falling back to ElevenLabs")
    else:
        logger.warning("GOOGLE_TTS_API_KEY not set — falling back to ElevenLabs")

    # ── Fallback: ElevenLabs ─────────────────────────────────────────────────
    el_key = os.environ.get("ELEVENLABS_API_KEY", "").strip().strip('"').strip("'")
    if not el_key:
        logger.warning("ELEVENLABS_API_KEY not set — skipping audio narration")
        return None

    try:
        from elevenlabs.client import ElevenLabs

        el_script = script
        if len(el_script) > 4900:
            el_script = el_script[:4900].rsplit(" ", 1)[0]
            logger.info(f"Truncated to {len(el_script)} chars for ElevenLabs limit")

        logger.info(f"Generating audio via ElevenLabs ({len(el_script)} chars)")
        client = ElevenLabs(api_key=el_key)
        audio_chunks = client.text_to_speech.convert(
            text=el_script,
            voice_id="JBFqnCBsd6RMkjVDRZzb",
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )
        audio_bytes = b"".join(audio_chunks)
        logger.info(f"ElevenLabs audio succeeded ({len(audio_bytes):,} bytes)")
        return audio_bytes
    except Exception as exc:
        logger.error(f"ElevenLabs audio generation failed: {exc}", exc_info=True)
        return None
