# Text Extraction

A streaming-first Python library for resilient document text extraction. Built on the **Functional Core / Imperative Shell** pattern for predictable behavior under high ingress load.

## Features

- **No-seek forward-only ingress** — peeks 2 KB from unrewindable streams, then routes by format
- **Memory-bounded processing** — structural formats buffer to RAM; text, images, and legacy doc formats stream incrementally
- **Declarative format registry** — add formats via a single wiring entry, no orchestrator edits
- **Domain-safe errors** — typed exceptions with caller-safe messages; full details logged internally
- **Dependency injection** — all limits flow from `AppSettings` at boot time

## Supported formats

| Category | MIME types | Strategy |
|----------|------------|----------|
| PDF | `application/pdf` | In-memory buffer → pypdfium2 |
| Office Open XML | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` (DOCX), `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` (XLSX), `application/vnd.openxmlformats-officedocument.presentationml.presentation` (PPTX) | In-memory buffer → native parser |
| Plain text | `text/plain` (heuristic) | Incremental UTF-8 stream |
| Images | `image/png`, `image/jpeg`, `image/webp`, `image/tiff`, `image/bmp`, `image/x-icon` | Stream → Apache Tika (Remote) |
| Legacy Word | `application/msword` | Stream → Apache Tika (Remote) |

Unknown or unregistered MIME types raise `UnsupportedFormatError`.


## Architecture

```
main (boot)
  └── orchestrator (workflow)
        ├── shell/stream.py    — BinaryIO reads, chunk generators
        ├── core/detector.py   — pure MIME sniffing
        ├── core/router.py     — pure registry lookup
        ├── core/extractors/   — pure extraction logic
        └── wiring.py          — composition-root registry
```

### Ingress routing

1. **Peek** — read exactly 2,048 bytes forward from the raw stream
2. **Detect** — pure magic-byte sniffing on an isolated `BytesIO` header
3. **Route** — declarative `ExtractorSpec` lookup by MIME type
4. **Buffer or stream**
   - **Structural** (PDF, DOCX, XLSX, PPTX): compile remainder into bounded `BytesIO`
   - **Streamable** (text, images, legacy DOC): lazy byte generator
5. **Extract** — invoke the mapped extractor with injected bounds

## Installation

Requires Python 3.10+ and [uv](https://github.com/astral-sh/uv).

```bash
uv sync
```

### System Prerequisites
* **Apache Tika Server**: Required for legacy Word (`.doc`) and image extraction. Ensure a Tika REST server is running (e.g. via Docker or jar) and accessible.

## Configuration

Settings load from environment variables (prefix `HERMES_TEXT_EXTRACTION__`) and an optional `.env` file.

| Variable | Default | Description |
|----------|---------|-------------|
| `HERMES_TEXT_EXTRACTION__MAX_FILE_SIZE_BYTES` | `1000` | Max ingress size in **megabytes** (converted to bytes internally) |
| `HERMES_TEXT_EXTRACTION__MAX_TEXT_LENGTH` | `1000000` | Max characters returned per extraction |
| `HERMES_TEXT_EXTRACTION__CHUNK_SIZE_BYTES` | `8192` | Stream read chunk size |
| `HERMES_TEXT_EXTRACTION__TIKA_SERVER_URL` | None | (Required) Endpoint URL of the Apache Tika REST server (e.g., `http://localhost:9998`) |
| `HERMES_TEXT_EXTRACTION__NETWORK_TIMEOUT_SECONDS` | `30.0` | Read and write network timeout in seconds for Tika requests |

Example `.env`:

```env
HERMES_TEXT_EXTRACTION__MAX_FILE_SIZE_BYTES=500
HERMES_TEXT_EXTRACTION__TIKA_SERVER_URL=http://localhost:9998
```


## Usage

### Library API

```python
from pathlib import Path
import logging

from hermes.text_extraction import extract_text, UnsupportedFormatError
from hermes.text_extraction.config import AppSettings

# Configure logging using standard logging library
logging.basicConfig(level=logging.INFO)

settings = AppSettings()

with Path("document.pdf").open("rb") as stream:
    text = extract_text(stream, settings=settings)
```

### CLI

```bash
uv run python -m hermes.text_extraction.main path/to/file.pdf
```

## Error handling

All package errors inherit from `HermesExtractionError`. Each carries an optional `mime_type` attribute for observability.

| Exception | Meaning |
|-----------|---------|
| `UnsupportedFormatError` | Detected MIME has no registered extractor |
| `FileTooLargeError` | Stream exceeds `max_file_size_bytes` |
| `CorruptDocumentError` | Structural document could not be parsed |
| `StreamReadError` | Ingress stream could not be read |
| `NetworkExtractionError` | Remote extraction via Apache Tika failed |
| `TextLimitExceededError` | Extracted text exceeds `max_text_length` |
| `ExtractionFailedError` | Unexpected internal failure / engine error |

Callers receive safe, stable messages. Full stack traces are written to the configured logger only.

```python
from hermes.text_extraction import (
    CorruptDocumentError,
    FileTooLargeError,
    HermesExtractionError,
)

try:
    text = extract_text(stream, settings=settings)
except FileTooLargeError as error:
    print(error.max_size_bytes)
except CorruptDocumentError as error:
    print(error.mime_type)
except HermesExtractionError:
    ...
```

## Adding a new format

1. Implement a pure extractor in `core/extractors/`. The signature depends on the extraction mode:
   - For `PayloadMode.BUFFER` (e.g. PDF or Office Open XML formats), conform to:
     ```python
     def extract(payload: io.BytesIO, max_length: int) -> str:
     ```
   - For `PayloadMode.STREAM` (e.g. plain text or custom streamed formats), conform to:
     ```python
     def extract(payload: Iterable[bytes], max_length: int) -> str:
     ```
2. Add the MIME constant to `constants.py` (if needed)
3. Register one row in `wiring.py`:

```python
MimeType.ODT: ExtractorSpec(odt.extract, PayloadMode.BUFFER),
```

## Project layout

```
src/hermes/text_extraction/
├── config/          # Pydantic settings (boot layer)
├── core/            # Pure logic: detector, router, extractors
├── shell/           # Side effects: streams
├── wiring.py        # Composition-root format registry
├── orchestrator.py  # Workflow coordinator
├── exceptions.py    # Domain error hierarchy
├── constants.py     # MIME types and defaults
└── main.py          # CLI entry point
```
