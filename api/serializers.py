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
        if obj.pdf_file:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.pdf_file.url)
            return obj.pdf_file.url
        return None

    def get_audio_url(self, obj) -> str | None:
        if obj.audio_file:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.audio_file.url)
            return obj.audio_file.url
        return None
