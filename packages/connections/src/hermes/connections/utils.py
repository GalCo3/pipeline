import functools
import json
import logging
from collections.abc import Callable, Iterable
from http import HTTPStatus
from typing import Any

import jsonpickle
import tenacity
from confluent_kafka import TopicPartition
from confluent_kafka.schema_registry import SchemaRegistryError
from elasticsearch import ConflictError

from .models import SiteResponse

logger = logging.Logger(__name__)

RETRYABLE_STATUS_CODES = [
    HTTPStatus.TOO_MANY_REQUESTS,
    HTTPStatus.REQUEST_TIMEOUT,
    HTTPStatus.SERVICE_UNAVAILABLE,
    HTTPStatus.GATEWAY_TIMEOUT,
    HTTPStatus.BAD_GATEWAY,
]


def is_produce_error_retryable(err) -> bool:
    return (
        isinstance(err, SchemaRegistryError)
        and getattr(err, "http_status_code", None) in RETRYABLE_STATUS_CODES
    )


def execute_on_client(method: Callable, *args, **kwargs) -> SiteResponse:
    """Execute an operation and handle exceptions"""
    result = SiteResponse(is_success=False)

    try:
        response = method(*args, **kwargs)
        result.is_success = True
        result.response = response
    except Exception as e:
        result.error = e

    return result


async def execute_on_client_async(method: Callable, *args, **kwargs) -> SiteResponse:
    """Await an async operation and handle exceptions"""
    result = SiteResponse(is_success=False)

    try:
        response = await method(*args, **kwargs)
        result.is_success = True
        result.response = response
    except Exception as e:
        result.error = e

    return result


def kafka_header_to_dict(headers: Any) -> dict:
    """
    Transform kafka headers to dict
    :param headers: Kafka headers
    :return: A dictionary representing the headers
    """
    if not headers:
        return {}

    json_input = {}

    for header_field_name, header_bytes in headers:
        header_json = header_bytes.decode("utf-8")
        json_input[header_field_name] = json.loads(
            jsonpickle.encode(header_json, unpicklable=False)
        )

    return json_input


def dict_to_kafka_header(headers: dict) -> list[tuple[str, str | bytes | None]]:
    """
    Transforms a dictionary to kafka headers
    :param headers: The dictionary
    :return: The kafka headers
    """
    sequence_output = []

    for header_field_name, header_value in headers.items():
        extracted_values = json.loads(jsonpickle.encode(header_value, unpicklable=False))

        encoded_result = (
            extracted_values.encode("utf-8")
            if isinstance(extracted_values, str)
            else json.dumps(extracted_values).encode("utf-8")
        )

        sequence_output.append((header_field_name, encoded_result))

    return sequence_output


def retry(
    max_retries: int,
    backoff_factor: int = 2,
    min: int = 1,
    max: int = 10,
    *args,
    **kwargs,
):
    def decorator(func):
        @tenacity.retry(
            *args,
            wait=tenacity.wait_exponential(multiplier=backoff_factor, min=min, max=max),
            stop=tenacity.stop_after_attempt(max_retries + 1),
            reraise=False,
            before_sleep=tenacity.before_sleep_log(logging.getLogger(), logging.WARNING),
            retry_error_callback=lambda retry_state: retry_state.outcome.result(),
            **kwargs,
        )
        @functools.wraps(func)
        def wrapper(*func_args, **func_kwargs):
            return func(*func_args, **func_kwargs)

        return wrapper

    return decorator


def retry_on_conflict(max_retries: int, backoff_factor: int = 2, min: int = 1, max: int = 10):
    """
    Decorator to retry a function on ConflictError.
    Args:
    max_retries (int): The maximum number of retries.
    backoff_factor (int, optional): The factor by which to increase the backoff
        time. Defaults to 2.
    Returns:
    Anything the function returns or the error string if raised
    """

    def _should_retry(result):
        local_site_response, remote_site_response = result
        return (
            not local_site_response.is_success
            and isinstance(local_site_response.error, ConflictError)
        ) or (
            remote_site_response
            and not remote_site_response.is_success
            and isinstance(remote_site_response.error, ConflictError)
        )

    return retry(
        max_retries,
        backoff_factor,
        min,
        max,
        retry=tenacity.retry_if_result(_should_retry),
    )


def map_assignment_by_topics(tps: Iterable[TopicPartition]) -> dict[str, dict]:
    """Maps an assignment to a pair of partitions and offsets for every topic name"""
    mapped: dict[str, dict] = {}

    for tp in tps:
        if tp.topic not in mapped:
            mapped[tp.topic] = {}

        mapped[tp.topic].update({tp.partition: tp.offset})

    return {"topics": mapped}
