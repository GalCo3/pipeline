import json
from pathlib import Path
from typing import Any

from hermes.connections import BaseElasticHandler
from hermes.observability import get_logger, init_observability

from settings import get_settings

init_observability(service_name="index-definitions")
logger = get_logger(__name__)

DEFINITIONS_DIR = Path(__file__).parent / "definitions"
SEMANTIC_SUFFIX = "-semantic"
# Fixed at index creation and rejected by Elasticsearch on every later
# `put_settings` call, closed or not, so an update must never resend it.
CREATION_ONLY_SETTINGS = {"number_of_shards"}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    content = path.read_text().strip()

    return json.loads(content) if content else {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)

    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value

    return merged


def _build_definition(index_dir: Path, environment: str) -> dict[str, Any]:
    layers = [_load_json(DEFINITIONS_DIR / "_global.json")]

    if index_dir.name.endswith(SEMANTIC_SUFFIX):
        layers.append(_load_json(DEFINITIONS_DIR / "_semantic.json"))

    layers.append(_load_json(index_dir / "base.json"))
    layers.append(_load_json(index_dir / f"{environment}.json"))

    definition: dict[str, Any] = {}
    for layer in layers:
        definition = _deep_merge(definition, layer)

    return definition


def _apply_definition(
    elastic_handler: BaseElasticHandler, index: str, definition: dict[str, Any]
) -> None:
    mappings = definition.get("mappings", {})
    settings = definition.get("settings", {})
    aliases = definition.get("aliases", {})

    if elastic_handler.index_exists(index):
        logger.info("Updating existing index", index=index)

        updatable_settings = {
            key: value for key, value in settings.items() if key not in CREATION_ONLY_SETTINGS
        }

        if mappings:
            elastic_handler.put_mapping(index, mapping=mappings, is_multisite=True)
        if updatable_settings:
            elastic_handler.put_settings(index, settings=updatable_settings, is_multisite=True)
        if aliases:
            elastic_handler.put_aliases(index, aliases=aliases, is_multisite=True)
    else:
        logger.info("Creating index", index=index)

        elastic_handler.create_index(
            index,
            mappings=mappings,
            settings=settings,
            aliases=aliases,
            is_multisite=True,
        )


def main() -> None:
    settings = get_settings()
    elastic_handler = BaseElasticHandler(settings.elastic_config)

    for index_dir in sorted(p for p in DEFINITIONS_DIR.iterdir() if p.is_dir()):
        definition = _build_definition(index_dir, settings.environment)
        _apply_definition(elastic_handler, index_dir.name, definition)
        logger.info("Applied index definition", index=index_dir.name)


if __name__ == "__main__":
    main()
