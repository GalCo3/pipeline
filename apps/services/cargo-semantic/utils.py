# CargoEnrichedMessage.text_content is the raw extracted file text — nothing from
# CargoMessage is prefixed into it, so no field is baked into the embedded text.
TEXT_FIELD = "text_content"
EMBEDDED_FIELDS: set[str] = set()

# Never belong on a chunk document: text bodies, pipeline bookkeeping.
EXCLUDED_FIELDS = {TEXT_FIELD, "indexed_at"}
