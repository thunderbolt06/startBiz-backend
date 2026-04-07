"""
API Views for StartBiz Validator
"""

import json
import time
import threading
import logging
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response

from .models import ResearchSession, SessionStatus
from .serializers import ResearchSessionCreateSerializer, ResearchSessionSerializer
from .agents.validator import validate_prompt
from .tasks import run_full_research

logger = logging.getLogger(__name__)


@api_view(["POST"])
@parser_classes([JSONParser, MultiPartParser])
def create_session(request):
    """
    POST /api/sessions/
    Creates a new research session with the user's prompt and optional extra data.
    """
    serializer = ResearchSessionCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    session = serializer.save()
    return Response(
        ResearchSessionSerializer(session, context={"request": request}).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
def get_session(request, session_id):
    """
    GET /api/sessions/{id}/
    Returns the current state of a research session.
    """
    try:
        session = ResearchSession.objects.get(id=session_id)
    except ResearchSession.DoesNotExist:
        return Response({"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)

    return Response(
        ResearchSessionSerializer(session, context={"request": request}).data
    )


@api_view(["POST"])
def validate_session(request, session_id):
    """
    POST /api/sessions/{id}/validate/
    Step 1: Runs prompt validation via Gemini.
    If sufficient → marks session as ready.
    If insufficient → returns questions and suggestions.
    """
    try:
        session = ResearchSession.objects.get(id=session_id)
    except ResearchSession.DoesNotExist:
        return Response({"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)

    if session.status not in [SessionStatus.PENDING, SessionStatus.INSUFFICIENT]:
        return Response(
            {"error": f"Session is in status '{session.status}' and cannot be re-validated"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    session.status = SessionStatus.VALIDATING
    session.save(update_fields=["status"])

    try:
        result = validate_prompt(session.prompt, session.extra_data or {})
    except Exception as e:
        session.status = SessionStatus.PENDING
        session.save(update_fields=["status"])
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    session.validation_feedback = result

    if result.get("status") == "ok":
        session.status = SessionStatus.PENDING
    else:
        session.status = SessionStatus.INSUFFICIENT

    session.save(update_fields=["status", "validation_feedback"])

    return Response({
        "validation": result,
        "session_status": session.status,
    })


@api_view(["POST"])
def start_research(request, session_id):
    """
    POST /api/sessions/{id}/research/
    Kicks off the full agentic research pipeline in a background thread.
    """
    try:
        session = ResearchSession.objects.get(id=session_id)
    except ResearchSession.DoesNotExist:
        return Response({"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)

    if session.status == SessionStatus.INSUFFICIENT:
        return Response(
            {"error": "Prompt is insufficient. Please refine it first."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if session.status in [SessionStatus.RESEARCHING, SessionStatus.GENERATING_THESIS, SessionStatus.GENERATING_PITCH]:
        return Response({"message": "Research already in progress", "session_id": str(session.id)})

    # Update prompt if provided in request body (user refined it)
    new_prompt = request.data.get("prompt")
    if new_prompt:
        session.prompt = new_prompt
        session.status = SessionStatus.PENDING
        session.save(update_fields=["prompt", "status"])

    t = threading.Thread(
        target=run_full_research,
        args=(str(session.id),),
        daemon=True,
        name=f"research-{session.id}",
    )
    t.start()

    return Response({
        "message": "Research started",
        "session_id": str(session.id),
        "stream_url": f"/api/sessions/{session.id}/stream/",
    })


@require_GET
@csrf_exempt
def stream_session(request, session_id):
    """
    GET /api/sessions/{id}/stream/
    Server-Sent Events stream — pushes status updates until completion.
    """
    def event_stream():
        last_status = None
        last_step_count = 0
        timeout = 600  # 10 minutes max
        elapsed = 0
        poll_interval = 2

        while elapsed < timeout:
            try:
                session = ResearchSession.objects.get(id=session_id)
            except ResearchSession.DoesNotExist:
                yield f"data: {json.dumps({'error': 'Session not found'})}\n\n"
                break

            current_status = session.status

            if current_status != last_status:
                last_status = current_status
                payload = {
                    "status": current_status,
                    "step": _status_to_step(current_status),
                    "step_label": _status_to_label(current_status),
                    "tool_plan": session.tool_plan if current_status not in [SessionStatus.PENDING, SessionStatus.VALIDATING] else [],
                }

                if current_status == SessionStatus.COMPLETED:
                    payload["thesis_preview"] = session.thesis_md[:500] if session.thesis_md else ""
                    payload["slide_count"] = len(session.slides_json)

                yield f"data: {json.dumps(payload)}\n\n"

                if current_status in [SessionStatus.COMPLETED, SessionStatus.FAILED]:
                    break

            time.sleep(poll_interval)
            elapsed += poll_interval

        if elapsed >= timeout:
            yield f"data: {json.dumps({'error': 'Research timed out'})}\n\n"

    response = StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    response["Access-Control-Allow-Origin"] = "*"
    return response


@api_view(["GET"])
def get_results(request, session_id):
    """
    GET /api/sessions/{id}/results/
    Returns the final thesis, slides, PDF and audio URLs.
    """
    try:
        session = ResearchSession.objects.get(id=session_id)
    except ResearchSession.DoesNotExist:
        return Response({"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)

    if session.status != SessionStatus.COMPLETED:
        return Response({
            "status": session.status,
            "message": "Research not yet complete",
        }, status=status.HTTP_202_ACCEPTED)

    return Response(
        ResearchSessionSerializer(session, context={"request": request}).data
    )


@require_GET
def serve_pdf(request, session_id):
    """
    GET /api/sessions/{id}/pdf/
    Streams the generated PDF pitch deck stored in the database.
    """
    session = get_object_or_404(ResearchSession, id=session_id)
    if not session.pdf_bytes:
        return HttpResponse(status=404)
    response = HttpResponse(bytes(session.pdf_bytes), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="pitch_{session_id}.pdf"'
    return response


@require_GET
def serve_audio(request, session_id):
    """
    GET /api/sessions/{id}/audio/
    Streams the generated audio narration stored in the database.
    """
    session = get_object_or_404(ResearchSession, id=session_id)
    if not session.audio_bytes:
        return HttpResponse(status=404)
    response = HttpResponse(bytes(session.audio_bytes), content_type="audio/wav")
    response["Content-Disposition"] = f'inline; filename="narration_{session_id}.wav"'
    return response


def _status_to_step(status: str) -> int:
    mapping = {
        SessionStatus.PENDING: 0,
        SessionStatus.VALIDATING: 1,
        SessionStatus.INSUFFICIENT: 1,
        SessionStatus.RESEARCHING: 2,
        SessionStatus.GENERATING_THESIS: 3,
        SessionStatus.GENERATING_PITCH: 4,
        SessionStatus.COMPLETED: 5,
        SessionStatus.FAILED: -1,
    }
    return mapping.get(status, 0)


def _status_to_label(status: str) -> str:
    mapping = {
        SessionStatus.PENDING: "Ready to research",
        SessionStatus.VALIDATING: "Validating your prompt...",
        SessionStatus.INSUFFICIENT: "Need more information",
        SessionStatus.RESEARCHING: "Gathering market data...",
        SessionStatus.GENERATING_THESIS: "Writing business thesis...",
        SessionStatus.GENERATING_PITCH: "Creating pitch deck & audio...",
        SessionStatus.COMPLETED: "Research complete!",
        SessionStatus.FAILED: "Research failed",
    }
    return mapping.get(status, status)
