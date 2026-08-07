import logging

from structlog.processors import CallsiteParameter, CallsiteParameterAdder
from structlog.types import EventDict, WrappedLogger

from hermes.observability.constants import IGNORED_PACKAGES

# Callsite parameter tracker initialized to skip internal packages
_callsite_adder = CallsiteParameterAdder(
    [
        CallsiteParameter.FILENAME,
        CallsiteParameter.LINENO,
        CallsiteParameter.FUNC_NAME,
    ],
    additional_ignores=list(IGNORED_PACKAGES),
)


def add_source_info(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Extracts log callsite source information (file, line, func) and nests it.
    This is a functional processor for structlog.
    """
    record = event_dict.get("_record")

    if isinstance(record, logging.LogRecord):
        event_dict["source"] = {
            "file": record.filename,
            "line": record.lineno,
            "func": record.funcName,
        }
    else:
        # Uses both logger and method_name implicitly via the CallsiteParameterAdder contract
        _callsite_adder(logger, method_name, event_dict)
        filename = event_dict.pop("filename", None)
        if filename is not None:
            event_dict["source"] = {
                "file": filename,
                "line": event_dict.pop("lineno", None),
                "func": event_dict.pop("func_name", None),
            }

    return event_dict
