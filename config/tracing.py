"""
OpenTelemetry tracing setup.

Always instruments Django, logging, and outgoing requests so that
%(otelTraceID)s / %(otelSpanID)s are always available in log records.

OTLP export to Jaeger (or any collector) is opt-in: set
OTEL_EXPORTER_OTLP_ENDPOINT in the environment to enable it.
Run the collector locally with: docker compose up -d
"""
import logging
import os

logger = logging.getLogger(__name__)

_initialised = False


def setup_tracing() -> None:
    global _initialised
    if _initialised:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.instrumentation.django import DjangoInstrumentor
        from opentelemetry.instrumentation.logging import LoggingInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        service_name = os.getenv("OTEL_SERVICE_NAME", "startbiz-backend")
        resource = Resource(attributes={SERVICE_NAME: service_name})
        provider = TracerProvider(resource=resource)

        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
        if endpoint:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces")
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info(
                "OpenTelemetry tracing initialised → %s (service=%s)",
                endpoint, service_name,
            )
        else:
            logger.debug(
                "OpenTelemetry: no OTEL_EXPORTER_OTLP_ENDPOINT set — "
                "instrumenting only (no export)"
            )

        trace.set_tracer_provider(provider)

        DjangoInstrumentor().instrument()
        LoggingInstrumentor().instrument(set_logging_format=True)
        RequestsInstrumentor().instrument()

        _initialised = True

    except Exception:
        logger.exception("Failed to initialise OpenTelemetry tracing — continuing without it")
