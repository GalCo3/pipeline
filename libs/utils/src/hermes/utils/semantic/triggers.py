from typing import Literal

from pydantic import BaseModel, ConfigDict

from hermes.connections import BasePlainProducerHandler
from hermes.observability import get_logger

logger = get_logger(__name__)

SemanticAction = Literal["delete", "update_metadata", "index"]


class SemanticTriggerMessage(BaseModel):
    """The message a `*-lexical` service publishes for its `*-semantic` sibling."""

    model_config = ConfigDict(extra="forbid")

    id: str | int
    action: SemanticAction


def produce_semantic_trigger(
    producer_handler: BasePlainProducerHandler,
    topic: str,
    doc_id: str | int,
    action: SemanticAction,
) -> None:
    """Tell the semantic sibling service what happened to a lexical document."""
    producer_handler.produce_message(
        topic=topic, key=str(doc_id), value={"id": doc_id, "action": action}, headers={}
    )
    producer_handler.flush()
    logger.info("Produced semantic trigger", topic=topic, doc_id=doc_id, action=action)
