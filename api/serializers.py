from rest_framework import serializers
from .models import ResearchSession


class ResearchSessionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResearchSession
        fields = ["prompt", "extra_data"]


class ResearchSessionSerializer(serializers.ModelSerializer):
    pdf_url = serializers.SerializerMethodField()
    audio_url = serializers.SerializerMethodField()

    class Meta:
        model = ResearchSession
        fields = [
            "id",
            "prompt",
            "extra_data",
            "status",
            "validation_feedback",
            "tool_plan",
            "tool_results",
            "thesis_md",
            "slides_json",
            "pdf_url",
            "audio_url",
            "error_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_pdf_url(self, obj) -> str | None:
        if obj.pdf_bytes:
            request = self.context.get("request")
            url = f"/api/sessions/{obj.id}/pdf/"
            return request.build_absolute_uri(url) if request else url
        return None

    def get_audio_url(self, obj) -> str | None:
        if obj.audio_bytes:
            request = self.context.get("request")
            url = f"/api/sessions/{obj.id}/audio/"
            return request.build_absolute_uri(url) if request else url
        return None
