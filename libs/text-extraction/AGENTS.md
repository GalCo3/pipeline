# Agent Guide — Text Extraction

This guide helps AI coding assistants and human developers maintain the architecture,
design principles, and codebase quality of the `text-extraction` library. See the
workspace-level [AGENTS.md](../../AGENTS.md) for shared tooling commands (ruff/ty
run from repo root).

---

## 1. Architectural Philosophy: Functional Core / Imperative Shell

We strictly separate pure logic from I/O and side effects:

- **Imperative Shell (`shell/`)**: Handles stream reading, network calls, and logging. Side effects and framework calls are confined here.
- **Functional Core (`core/`)**: Pure, side-effect-free logic (detector, router, extractors). Domain logic accepts plain data (`io.BytesIO` or `Iterable[bytes]`) and returns plain text.
- **Orchestrator (`orchestrator.py`)**: The coordination glue. It manages the Smart Ingress Routing boundary between streams and in-memory buffers.

---

## 2. Interface Contracts

When writing or extending text extractors:

### 2.1 Buffered Extractors (`PayloadMode.BUFFER`)
- **Applies to**: PDF, DOCX, XLSX, PPTX.
- **Payload Signature**: Must accept `payload: io.BytesIO` directly.
- **Implementation**: Call `payload.seek(0)` before passing the stream to the parser. Never copy/rewrite the payload buffer into another `BytesIO` instance.
- **Interface**:
  ```python
  def extract(payload: io.BytesIO, max_length: int) -> str:
      payload.seek(0)
      # Parse directly using the library...
  ```

### 2.2 Streaming Extractors (`PayloadMode.STREAM`)
- **Applies to**: Plain text (`text/plain`), remote network Tika extractors.
- **Payload Signature**: Must accept `payload: Iterable[bytes]`.
- **Interface**:
  ```python
  def extract(payload: Iterable[bytes], max_length: int) -> str:
      for chunk in payload:
          # Process chunk incrementally...
  ```

---

## 3. Coding Standards & Conventions

- **Pure Functions**: A function's output must only depend on its inputs. Ensure no reads from module-level mutable variables.
- **No Input Mutation**: Never mutate input arguments (e.g. do not call `.append()` on an input list). Return new values instead.
- **Google-Style Docstrings**: Document all new and updated functions with structured sections (`Args`, `Returns`, `Raises`, `Yields`).
- **No `is_fake` checks**: Production logic must not contain test-aware attributes or hardcoded class name matching for mocked objects (e.g. do not check `hasattr(doc, "is_fake")`). Use clean duck-typing instead.
- **No print side-effects at import time**: Any executable block at the module scope (e.g. in `main.py`) must be guarded with `if __name__ == "__main__":`.

---

## 4. Testing & Verification

- **Pure core tests**: Tests for functions in the functional core must not require mocks or complex setup. Supply inputs and verify expected output.
- **Coverage standard**: We aim for 100% statement coverage. Always run tests with coverage reporting.
- **Useful Commands**:
  ```bash
  # Run full test suite
  uv run pytest

  # Run test suite with term-missing coverage report
  uv run pytest --cov=src --cov-report=term-missing
  ```
