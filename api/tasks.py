"""
Celery background tasks for the full research pipeline.
Each task updates the ResearchSession model and can be polled via SSE.
"""

import json
import logging
from celery import shared_task
from django.core.files.base import ContentFile

from api.models import ResearchSession, SessionStatus
from api.agents.researcher import plan_research, execute_tool_plan
from api.agents.thesis_generator import generate_thesis
from api.agents.pitch_generator import (
    generate_slide_manifest,
    build_pitch_html,
    html_to_pdf,
    generate_audio_narration,
)

logger = logging.getLogger(__name__)


def _update_status(session_id: str, status: str, **kwargs):
    ResearchSession.objects.filter(id=session_id).update(status=status, **kwargs)


@shared_task(bind=True, max_retries=1)
def run_full_research(self, session_id: str):
    """
    Orchestrates the full agentic research pipeline for a session.
    Steps: plan → tool execution → thesis → pitch → audio
    """
    try:
        session = ResearchSession.objects.get(id=session_id)
    except ResearchSession.DoesNotExist:
        logger.error(f"Session {session_id} not found")
        return

    try:
        # Step 2: Plan research tools
        _update_status(session_id, SessionStatus.RESEARCHING)
        validation_summary = session.validation_feedback.get("summary", "")
        tool_plan = plan_research(session.prompt, validation_summary)
        _update_status(session_id, SessionStatus.RESEARCHING, tool_plan=tool_plan)

        # Step 3: Execute tools in parallel
        tool_results = execute_tool_plan(tool_plan)
        _update_status(session_id, SessionStatus.RESEARCHING, tool_results=tool_results)

        # Step 4: Generate thesis
        _update_status(session_id, SessionStatus.GENERATING_THESIS)
        thesis_md = generate_thesis(session.prompt, tool_results, validation_summary)
        _update_status(session_id, SessionStatus.GENERATING_THESIS, thesis_md=thesis_md)

        # Step 5a: Generate slide manifest (non-fatal)
        _update_status(session_id, SessionStatus.GENERATING_PITCH)
        slides = []
        try:
            slides = generate_slide_manifest(thesis_md)
        except Exception as exc:
            logger.warning(f"Slide manifest generation failed for {session_id}: {exc}")

        # Infer deck title from first title slide
        deck_title = "Business Validation Report"
        for slide in slides:
            if slide.get("type") == "title":
                deck_title = slide.get("title", deck_title)
                break

        # Step 5b: Build HTML pitch deck (non-fatal)
        html_content = None
        if slides:
            try:
                html_content = build_pitch_html(slides, deck_title)
            except Exception as exc:
                logger.warning(f"Pitch HTML build failed for {session_id}: {exc}")

        # Step 5c: Convert to PDF (non-fatal)
        pdf_bytes = None
        if html_content:
            try:
                pdf_bytes = html_to_pdf(html_content)
            except Exception as exc:
                logger.warning(f"PDF conversion failed for {session_id}: {exc}")

        # Step 5d: Generate audio (non-fatal)
        audio_bytes = None
        try:
            audio_bytes = generate_audio_narration(slides)
        except Exception as exc:
            logger.warning(f"Audio narration generation failed for {session_id}: {exc}")

        # Refresh session and save whatever was successfully generated
        session = ResearchSession.objects.get(id=session_id)
        session.slides_json = slides
        session.thesis_md = thesis_md
        session.tool_plan = tool_plan
        session.tool_results = tool_results

        if pdf_bytes:
            session.pdf_file.save(
                f"pitch_{session_id}.pdf",
                ContentFile(pdf_bytes),
                save=False,
            )

        if audio_bytes:
            session.audio_file.save(
                f"narration_{session_id}.wav",
                ContentFile(audio_bytes),
                save=False,
            )

        session.status = SessionStatus.COMPLETED
        session.save()

    except Exception as exc:
        logger.exception(f"Research pipeline failed for session {session_id}: {exc}")
        ResearchSession.objects.filter(id=session_id).update(
            status=SessionStatus.FAILED,
            error_message=str(exc),
        )
        raise self.retry(exc=exc, countdown=0)
