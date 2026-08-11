from structlog.types import EventDict, WrappedLogger


def rename_event_and_uppercase_level(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """
    Renames 'event' key to 'message' and uppercases level keys.
    This is a pure function processor for structlog.
    """
    if "event" in event_dict:
        event_dict["message"] = event_dict.pop("event")
    if "level" in event_dict:
        event_dict["level"] = str(event_dict["level"]).upper()
    return event_dict
