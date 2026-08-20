# text_content is the raw extracted file text; no message field is prefixed in.
TEXT_FIELD = "text_content"
EMBEDDED_FIELDS: set[str] = set()

# Never belong on a chunk document: text bodies, pipeline bookkeeping.
EXCLUDED_FIELDS = {TEXT_FIELD, "indexed_at"}
