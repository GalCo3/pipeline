from http import HTTPStatus

import requests
from bs4 import BeautifulSoup
from exceptions import ChiefAPIError

from hermes.observability import get_logger

logger = get_logger(__name__)


def html_to_text(html_content: str) -> str:
    soup = BeautifulSoup(html_content, features="html.parser")
    return soup.get_text(strip=True, separator="\n")


def convert_chief_command(name: str, command_content: list[dict]) -> str:
    cleaned_text: str = f"{name}\n\n"

    for sub_command in command_content:
        current_text: str = sub_command.get("text") or ""
        cleaned_text += (
            f"{sub_command.get('full_name', '')}\n"
            f"{html_to_text(current_text) if current_text else ''}"
            f"\n\n"
        )

    return cleaned_text


def extract_chief_command_content(
    id: str, doc_path_template: str, api_key: str, timeout: int
) -> list[dict]:
    try:
        with requests.get(
            url=doc_path_template.format(id),
            headers={
                "x-chief-key": api_key,
            },
            verify=False,
            timeout=timeout,
        ) as response:
            if response.status_code == HTTPStatus.NOT_FOUND:
                logger.warning(f"Chief document {id} not found", status=HTTPStatus.NOT_FOUND)
                raise ChiefAPIError(f"Chief document {id} not found")

            response.raise_for_status()
            logger.info("Successfully got response from chief API")

            return response.json().get("documentContent", [])
    except ChiefAPIError:
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch chief document {id}: {e}")
        raise ChiefAPIError(f"Failed to fetch chief document {id}: {e}") from e
