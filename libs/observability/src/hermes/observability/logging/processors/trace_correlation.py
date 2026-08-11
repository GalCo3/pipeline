from opentelemetry import trace
from structlog.types import EventDict, WrappedLogger


def add_otel_trace_ids(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """
    Processor that inspects the current active OpenTelemetry span.
    If a span is active and valid, extracts the trace_id, span_id, and optional parent_span_id
    in hexadecimal format and injects them into the root of the event dictionary.
    """
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if not ctx.is_valid:
        return event_dict

    # Format trace_id to 32 hex chars and span_id to 16 hex chars
    event_dict["trace_id"] = format(ctx.trace_id, "032x")
    event_dict["span_id"] = format(ctx.span_id, "016x")

    # If parent span exists, extract and format its span_id
    parent = getattr(span, "parent", None)
    if parent is not None and hasattr(parent, "span_id"):
        event_dict["parent_span_id"] = format(parent.span_id, "016x")

    return event_dict
