# ChiefEnrichedMessage.cleaned_text is `name` followed by the fetched command
# content — `name` is the only ChiefMessage field baked into the embedded text,
# everything else on the message is pure metadata.
TEXT_FIELD = "cleaned_text"
EMBEDDED_FIELDS = {"name"}

# Fields written by chief-lexical that never belong on a chunk document (large
# text bodies, pipeline-internal bookkeeping).
EXCLUDED_FIELDS = {TEXT_FIELD, "command_content", "indexed_at"}
