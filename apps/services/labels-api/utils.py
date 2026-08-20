import json
import re

from constants import SYSTEM_PROMPT

from hermes.observability import get_logger

logger = get_logger(__name__)


def build_system_prompt() -> str:
    """Return the system prompt for document label recommendation."""
    return SYSTEM_PROMPT


def build_user_message(name: str, labels: list[str], content: str) -> str:
    """Format the user input message with clear sections for metadata and content."""
    labels_formatted = json.dumps(labels, ensure_ascii=False, indent=2)
    return (
        f"Candidate Labels:\n{labels_formatted}\n\n"
        f'Document Metadata:\n- Name: "{name}"\n\n'
        f'Document Body Content:\n"{content}"'
    )


def parse_llm_json_response(raw_response_text: str, available_labels: list[str]) -> str | None:
    """Extract and parse recommended_label from LLM JSON output with fallback matching."""
    text = raw_response_text.strip()

    # Strip markdown code fences if present (e.g. ```json ... ```)
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()

    # Primary attempt: Parse JSON
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            label = data.get("recommended_label")
            if isinstance(label, str):
                cleaned_label = label.strip().strip('"').strip("'")
                if cleaned_label:
                    return cleaned_label
    except json.JSONDecodeError:
        logger.warning(
            "Failed to parse JSON response from LLM, attempting plain string fallback",
            raw_response=raw_response_text,
        )

    # Fallback attempt: Direct string match against available labels
    for label in available_labels:
        if label.lower() in text.lower():
            logger.info("Found fallback label match in raw response", fallback_label=label)
            return label

    return None
