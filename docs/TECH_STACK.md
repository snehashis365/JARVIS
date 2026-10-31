# Jarvis — Technology Stack & Architecture Decisions

## 1. Core Technology Selection

| Category | Technology | Rationale & Trade-offs |
| :--- | :--- | :--- |
| **Language & Runtime** | Python 3.12 | Modern syntax, robust typing (`typing`, `Self`, `TypeVar`), native `asyncio` task groups, superior ecosystem for AI, NLP, audio, and systems programming. |
| **Backend & Web API** | FastAPI / Starlette / Uvicorn | High-performance ASGI framework with native async support, built-in Pydantic v2 data validation, OpenAPI doc generation, and low-latency WebSocket and SSE streaming. |
| **Data Contracts** | Pydantic v2 | Extremely fast Rust-backed schema validation, JSON Schema generation for LLM tool calling, strict typing, and serialization. |
| **HTTP & Networking** | HTTPX | Mature async HTTP client with strict connection pooling, timeouts, HTTP/2 support, and seamless mock transport (`httpx.MockTransport`) for unit testing. |
| **Local Persistence** | SQLite 3 + FTS5 | Zero-configuration, zero-process overhead, standard library integration. WAL mode enables concurrent readers with low lock contention. Full-text search via FTS5. |
| **Cryptography** | `cryptography` (PyCA) | Audited, industry-standard AES-256-GCM authenticated encryption for optional cloud sync and local credential protection. |
| **Testing Framework** | Pytest + pytest-asyncio | Leading testing framework with async test support, flexible fixtures, mocking, and coverage reporting. |
| **Desktop / Web Interface** | Embedded SPA (HTML5/ES6/CSS3) | Self-contained, zero-build-tooling frontend served directly by the FastAPI backend. Zero global npm dependencies needed. Can be packaged inside Tauri or WebView for a native desktop window. |

---

## 2. Evaluation of Evaluated Alternatives

### 2.1 Backend / Runtime: Python vs. Rust vs. Node.js
- **Rust**: Exceptional performance and memory safety, but ecosystem friction for AI adapters, local model bindings, and rapid iteration.
- **Node.js**: Strong async I/O, but weaker local AI/ML/speech ecosystem compared to Python.
- **Decision**: Python 3.12 within local `.venv`. Provides maximum compatibility with AI runtimes (Ollama, llama.cpp, Whisper, Kokoro) while keeping memory footprint modest.

### 2.2 LLM Orchestration Frameworks: Custom vs. LangChain / CrewAI / AutoGen
- **LangChain / CrewAI**: Heavy dependencies, frequent breaking changes, unnecessary abstractions, and hidden prompt injections/token consumption.
- **Decision**: Purpose-built, lightweight, bounded orchestrator. Provides full visibility, precise step budgeting, deterministic loops detection, and deterministic permission checkpoints.

### 2.3 Provider Abstraction: Modular Adapter Pattern vs. Heavy Gateway
- **LiteLLM**: Useful reference, but adds significant dependency weight and transitive vulnerabilities if included in core.
- **Decision**: Modular adapter architecture adhering to OpenAI-compatible REST conventions. Allows connecting Ollama, LM Studio, llama.cpp, OpenAI, Anthropic, and Gemini through a clean, unified `BaseLLMProvider` contract without third-party lock-in.

### 2.4 Persistence: SQLite vs. DuckDB vs. Dedicated Vector DBs (Chroma/Milvus)
- **Chroma / Milvus**: Heavyweight C++ or Docker dependencies, excessive RAM usage for a personal desktop assistant.
- **Decision**: SQLite 3 with WAL mode and FTS5 full-text indexing. For semantic memory, lightweight in-process vector cosine similarity over numpy/sqlite arrays provides optimal balance of speed and zero maintenance.

### 2.5 Desktop UI: Embedded Web Shell vs. Electron vs. Tauri
- **Electron**: Bundles entire Chromium + Node runtime, consuming 300+ MB of RAM just for the UI shell.
- **Tauri**: Lightweight (< 30 MB RAM) using native OS WebViews (WebKit / WebView2).
- **Embedded Web UI**: Served directly by the backend at `http://127.0.0.1:8000`, instantly accessible in any browser and trivially embeddable in a Tauri or native desktop window wrapper.
- **Decision**: Embedded Web UI served by FastAPI backend as the universal baseline, with full API readiness for Tauri desktop shell wrapper.
