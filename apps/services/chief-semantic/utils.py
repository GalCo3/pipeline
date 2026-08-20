# cleaned_text is `name` followed by the command content, so `name` is the only
# message field baked into the embedded text.
TEXT_FIELD = "cleaned_text"
EMBEDDED_FIELDS = {"name"}

# Never belong on a chunk document: text bodies, pipeline bookkeeping.
EXCLUDED_FIELDS = {TEXT_FIELD, "command_content", "indexed_at"}
