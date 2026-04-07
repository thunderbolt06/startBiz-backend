"""
OpenTelemetry tracing setup — sends traces to Jaeger via OTLP/HTTP.

Initialise by calling setup_tracing() once at process startup
(manage.py for dev, wsgi.py / asgi.py for production).
"""
import logging
import os

logger = logging.getLogger(__name__)

_initialised = False


def setup_tracing() -> None:
    global _initialised
    if _initialised:
        return

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if not endpoint:
        # Tracing is opt-in: silently skip when no endpoint is configured
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.django import DjangoInstrumentor
        from opentelemetry.instrumentation.logging import LoggingInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        service_name = os.getenv("OTEL_SERVICE_NAME", "startbiz-backend")

        resource = Resource(attributes={SERVICE_NAME: service_name})
        provider = TracerProvider(resource=resource)

        exporter = OTLPSpanExporter(
            endpoint=f"{endpoint.rstrip('/')}/v1/traces",
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        # Instrument the Django request/response cycle
        DjangoInstrumentor().instrument()

        # Inject trace-id and span-id into every log record
        LoggingInstrumentor().instrument(set_logging_format=True)

        # Trace outgoing requests made with the `requests` library
        RequestsInstrumentor().instrument()

        _initialised = True
        logger.info("OpenTelemetry tracing initialised → %s (service=%s)", endpoint, service_name)

    except Exception:
        logger.exception("Failed to initialise OpenTelemetry tracing — continuing without it")
