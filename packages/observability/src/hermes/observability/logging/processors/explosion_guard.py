from structlog.types import EventDict, WrappedLogger

from hermes.observability.constants import WHITELISTED_KEYS


def mapping_explosion_guard(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """
    Ensures only whitelisted root keys remain at the root of the JSON log dictionary.
    All other keys (developer-passed kwargs) are bundled into a nested 'metadata' dictionary.
    """
    # Identify non-whitelisted keys, ignoring internal keys starting with underscore
    extra_keys = [k for k in event_dict if k not in WHITELISTED_KEYS and not k.startswith("_")]

    if extra_keys:
        metadata = event_dict.get("metadata", {})
        if not isinstance(metadata, dict):
            # If metadata was passed as a non-dict type, nest it under original_metadata
            metadata = {"original_metadata": metadata}

        event_dict["metadata"] = {**metadata, **{k: event_dict.pop(k) for k in extra_keys}}

    return event_dict
