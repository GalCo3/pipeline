# CargoEnrichedMessage.text_content is the raw extracted file text — nothing from
# CargoMessage is prefixed into it, so no field is baked into the embedded text.
TEXT_FIELD = "text_content"
EMBEDDED_FIELDS: set[str] = set()

# Fields written by cargo-lexical that never belong on a chunk document (large
# text bodies, pipeline-internal bookkeeping).
EXCLUDED_FIELDS = {TEXT_FIELD, "indexed_at"}
