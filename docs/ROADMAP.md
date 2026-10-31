# Jarvis — Phased Engineering Roadmap

## Phase 0: Research, Architecture & Specification
- **Deliverables**: PRD, Architecture, Tech Stack, Dependency Decisions, Security Model, Roadmap, Testing Guide, Phase 0 Milestone Report.
- **Acceptance Criteria**: All documents generated, reviewed, self-consistent, and verified against project boundaries.
- **Test Gate**: Architecture self-review and boundary validation pass.

---

## Phase 1: Foundation & Project Scaffolding
- **Deliverables**:
  - Python virtual environment `.venv` with pinned packages in `pyproject.toml`.
  - Directory structure (`src/jarvis/`, `tests/`, `docs/`, `data/`).
  - Configuration manager (Pydantic settings) with `.env.example`.
  - Structured logging with automatic secret redaction.
  - Minimal FastAPI backend server and health check endpoints.
  - Session and task state manager.
  - Test runner script and automated test suite.
- **Acceptance Criteria**: Server starts cleanly, handles session creation, logs without secret leakage, all unit tests pass.
- **Test Gate**: `pytest tests/unit/test_foundation.py` passes 100%.

---

## Phase 2: Provider-Neutral LLM Connectivity
- **Deliverables**:
  - Abstract base provider contract (`BaseLLMProvider`).
  - Provider adapters: Local (Ollama/llama.cpp/OpenAI-compatible), Hosted (OpenAI, Anthropic, Gemini format), and Mock provider for testing.
  - Model capability registry (tracking tool-call support, streaming, vision, token limits).
  - Robust streaming event generator, timeouts, retries with exponential backoff, and cancellation tokens.
- **Acceptance Criteria**: Provider switching requires zero changes to core; streaming and cancellation work reliably; mock provider passes all protocol tests.
- **Test Gate**: `pytest tests/unit/test_providers.py` passes 100%.

---

## Phase 3: Assistant Core & Bounded Orchestration
- **Deliverables**:
  - Dual-path router: fast direct chat vs. tool-assisted task orchestrator.
  - Bounded orchestration engine with step limits, loop detection, timeout enforcement.
  - Intelligent, explainable model router (Local, Hybrid, Cloud modes).
  - Task progress and state streaming.
- **Acceptance Criteria**: Simple conversations execute directly without planning overhead; multi-step tool calls terminate within budget; infinite loops are aborted.
- **Test Gate**: `pytest tests/unit/test_orchestrator.py` passes 100%.

---

## Phase 4: Deterministic Security & Permission Enforcement
- **Deliverables**:
  - Permission Engine enforcing autonomy modes (`Plan`, `Agent Decides`, `Auto`, `Sandbox Only`).
  - Strict path boundary validator (symlink escape and path traversal protection).
  - Interactive approval workflow with cryptographic approval tokens.
  - Tamper-evident append-only audit logger.
- **Acceptance Criteria**: 100% of mutating actions gated; paths outside workspace strictly rejected; prompt injection attacks fail to bypass permissions.
- **Test Gate**: `pytest tests/unit/test_security.py` passes 100%.

---

## Phase 5: Tools, Skills & Integrations Runtime
- **Deliverables**:
  - Tool registry with typed Pydantic schemas and metadata.
  - Built-in tools: safe file operations, workspace inspection, web search simulation/adapter, system diagnostics.
  - Skill loader and manifest parser (YAML/JSON) with lifecycle management.
  - Model Context Protocol (MCP) tool client interface.
- **Acceptance Criteria**: All tools execute only through permission gate; invalid parameters rejected; third-party skill manifests validated.
- **Test Gate**: `pytest tests/unit/test_tools.py` passes 100%.

---

## Phase 6: Memory & Context Management
- **Deliverables**:
  - SQLite persistence layer with WAL mode and schema migrations.
  - Tiered memory: Working, Preferences/Facts, Episodic Tasks, Procedural Recipes.
  - Hybrid retrieval engine (SQLite FTS5 full-text search + ranking).
  - Context window budgeting and summarization.
  - User memory management API (inspect, edit, delete, export).
- **Acceptance Criteria**: Memories reliably persisted and retrieved; user can view and delete memories; context window limits strictly respected.
- **Test Gate**: `pytest tests/unit/test_memory.py` passes 100%.

---

## Phase 7: Personality & Voice Pipeline
- **Deliverables**:
  - Central personality configuration system (name, tone, formality, humor, proactivity).
  - Speech pipeline interface: STT (Whisper format) and TTS (Kokoro/Piper format).
  - Streaming audio chunk synthesis, phrase segmentation, and playback queue.
  - Barge-in voice activity detection and instant cancellation of speech and LLM generation.
- **Acceptance Criteria**: Model switching preserves personality; voice pipeline produces chunked audio; speech interruption immediately aborts generation.
- **Test Gate**: `pytest tests/unit/test_voice.py` passes 100%.

---

## Phase 8: Optional Decoupled Cloud Sync
- **Deliverables**:
  - Opt-in, decoupled cloud sync client.
  - Client-side AES-256-GCM encryption for syncable data.
  - Device pairing, registration, and revocation protocol.
  - Conflict resolution using deterministic field-level timestamping.
  - Zero-sync verification (local assistant works 100% offline).
- **Acceptance Criteria**: Data encrypted before leaving client; offline changes sync cleanly on reconnect; local mode remains fully functional without sync.
- **Test Gate**: `pytest tests/unit/test_sync.py` passes 100%.

---

## Phase 9: Polish, Distribution & Final Verification
- **Deliverables**:
  - Full-featured, responsive desktop web UI with dark/light theme, audio visualizer, permission prompts, and settings drawer.
  - CLI runner (`run.sh`, `python -m jarvis.cli`) and background service lifecycle manager.
  - Hardware & resource profiler (CPU, RAM, VRAM detection, low-resource profile).
  - Complete automated regression test suite run.
  - Comprehensive user and developer guides (`docs/USER_GUIDE.md`, `README.md`).
  - Final Milestone & Verification Report.
- **Acceptance Criteria**: Application starts cleanly; all automated test suites pass; comprehensive documentation ready for user handoff.
- **Test Gate**: Full test suite (`pytest tests/`) passes with 0 failures.
