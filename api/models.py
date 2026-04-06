import uuid
from django.db import models


class SessionStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    VALIDATING = "validating", "Validating"
    INSUFFICIENT = "insufficient", "Insufficient"
    RESEARCHING = "researching", "Researching"
    GENERATING_THESIS = "generating_thesis", "Generating Thesis"
    GENERATING_PITCH = "generating_pitch", "Generating Pitch"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class ResearchSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prompt = models.TextField()
    extra_data = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=30,
        choices=SessionStatus.choices,
        default=SessionStatus.PENDING,
    )
    validation_feedback = models.JSONField(default=dict, blank=True)
    tool_plan = models.JSONField(default=list, blank=True)
    tool_results = models.JSONField(default=dict, blank=True)
    thesis_md = models.TextField(blank=True, default="")
    slides_json = models.JSONField(default=list, blank=True)
    pdf_file = models.FileField(upload_to="pdfs/", blank=True, null=True)
    audio_file = models.FileField(upload_to="audio/", blank=True, null=True)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Session {self.id} — {self.status}"
