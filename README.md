# Jarvis — Modular, Desktop-First Personal AI Assistant

Jarvis is a capable, modular, desktop-first personal AI assistant built for high privacy, transparent observability, and deterministic software security. It operates 100% locally on standard hardware without requiring dedicated GPUs, large RAM, or paid cloud APIs, while seamlessly supporting optional hosted cloud models and end-to-end encrypted multi-device synchronization.

---

## Key Capabilities

- **Desktop Interface, Setup Wizard & CLI**: Single-page desktop interface (`http://127.0.0.1:8000`) with first-run GUI Setup Wizard, local LLM auto-detection, and interactive terminal chat (`python -m jarvis.cli chat`).
- **Extensive Security-Governed Toolset**: 11 built-in tools across filesystem (`read`, `write`, `delete`, `list`, `search`), web research (`search`, `fetch`), system diagnostics, time/date, safe math calculation, and shell command execution. Includes interactive "Test Run" console and live in-chat tool execution cards.
- **Voice Chat UI & Barge-in Interruption**: Dedicated Voice Mode with pulsing Jarvis ARC audio orb, push-to-talk speech recognition (`🎙️`), natural spoken responses (`speechSynthesis`), and instantaneous barge-in interruption (`⏹️ Stop`).
- **Provider-Neutral LLM Connectivity**: Automatic probing and discovery for local runtimes (Ollama, LM Studio, llama.cpp, custom endpoints) and hosted APIs (OpenAI, Anthropic, Gemini, custom OpenAI-compatible endpoints).
- **Explainable Model Router**: Intelligent routing across Local, Cloud, and Hybrid operating modes.
- **Deterministic Permission Enforcement**: Code-level gates with four autonomy modes (`Plan`, `Agent Decides`, `Auto`, `Sandbox Only`), canonical path traversal protection, interactive approval workflows, and append-only audit logging.
- **Structured Memory & FTS5 Search**: Local SQLite persistence in WAL mode, tiered memory categories (Preferences, Facts, Episodic, Procedural), context window budgeting with automatic executive summarization, and complete user search/add/edit/delete controls.
- **Decoupled E2EE Cloud Sync**: Optional AES-256-GCM client-side encrypted sync for preferences and curated memories, operating independently of inference.

---

## Quickstart

### 1. Installation
All project dependencies are isolated in the local `.venv` virtual environment:

```bash
# Initialize local virtual environment
python3 -m venv .venv

# Install project and dependencies
.venv/bin/pip install -e ".[dev]"

# Configure settings
cp .env.example .env
```

### 2. Launching Jarvis
```bash
# Launch via startup script
bash run.sh

# Or start via CLI
.venv/bin/python -m jarvis.cli start
```

Access the desktop web interface in your browser at: **`http://127.0.0.1:8000`**

On initial launch, the **Initial Setup Wizard** automatically opens:
- Auto-detects local Ollama, LM Studio, and llama.cpp servers and their installed models.
- Allows configuration of cloud providers (OpenAI, Anthropic, Gemini) or custom OpenAI-compatible endpoints.
- Saves settings to gitignored `data/config.json`.
- Can be re-launched at any time via the **⚙️ Setup Wizard** button in the top navigation.

### 3. Interactive Terminal Chat
```bash
.venv/bin/python -m jarvis.cli chat
```

### 4. Hardware & Runtime Diagnostics
```bash
.venv/bin/python -m jarvis.cli status
```

---

## Running Automated Tests

Jarvis enforces a strict **zero-cost testing policy**. All automated tests run locally using deterministic mock providers and in-memory test databases without requiring paid API keys or external network connections:

```bash
# Run the complete test suite (61 tests) with coverage reporting
bash scripts/run_tests.sh
```

---

## Project Structure

```text
Jarvis/
├── src/jarvis/
│   ├── cli.py                 # Command-line interface
│   ├── config.py              # Pydantic settings & path validation
│   ├── logging.py             # Secret-redacting structured logger
│   ├── core/                  # Orchestrator, session state, hardware profiler
│   ├── providers/             # LLM adapters (Local, OpenAI, Anthropic, Gemini, Mock)
│   ├── routing/               # Explainable model router & heuristics
│   ├── security/              # Permission manager, path validator, audit logger
│   ├── tools/                 # Built-in tools, skill manager, MCP client
│   ├── memory/                # SQLite WAL storage, FTS5 search, summarizer
│   ├── voice/                 # Personality profile, STT/TTS pipeline, barge-in
│   ├── sync/                  # E2EE AES-256-GCM cloud sync client
│   └── server/                # FastAPI application & static web UI
├── tests/
│   ├── conftest.py            # Shared async test fixtures
│   ├── unit/                  # Unit tests across all subsystems
│   ├── security/              # Sandboxing and path traversal tests
│   └── integration/           # End-to-end integration workflows
├── docs/                      # Architectural, security, and user documentation
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── TECH_STACK.md
│   ├── DEPENDENCY_DECISIONS.md
│   ├── SECURITY.md
│   ├── ROADMAP.md
│   ├── TESTING.md
│   ├── USER_GUIDE.md
│   └── milestones/            # Phase 0 through Phase 9 reports
├── data/                      # Local SQLite database and sandbox
├── logs/                      # Application logs and security audit trails
├── run.sh                     # Launch script
└── pyproject.toml             # Pinned project packaging metadata
```

---

## Documentation Index

- [Product Requirements (PRD)](docs/PRD.md)
- [System Architecture](docs/ARCHITECTURE.md)
- [Technology Stack Decisions](docs/TECH_STACK.md)
- [Dependency Audit & Decisions](docs/DEPENDENCY_DECISIONS.md)
- [Security Architecture & Threat Model](docs/SECURITY.md)
- [Phased Engineering Roadmap](docs/ROADMAP.md)
- [Testing Strategy & Verification](docs/TESTING.md)
- [User & Developer Guide](docs/USER_GUIDE.md)
- [Milestone Reports](docs/milestones/)
