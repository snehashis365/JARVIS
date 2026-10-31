# Jarvis — Testing Strategy & Verification Guide

## 1. Testing Philosophy & Zero-Cost Mandate

Testing in Jarvis is a core engineering requirement. Every subsystem must be accompanied by comprehensive automated tests.
- **Zero Paid Cost**: All routine tests execute against local mock providers, in-memory databases, and temporary directories. No paid API keys or cloud services are ever required to pass tests.
- **Deterministic & Fast**: Tests must execute deterministically without flaky network or timing dependencies.
- **Coverage Requirement**: High branch coverage across core orchestration, security policies, tool permissions, and memory persistence.

---

## 2. Test Suite Organization

```text
tests/
├── conftest.py               # Shared fixtures (temp dirs, mock providers, db sessions)
├── unit/
│   ├── test_foundation.py    # Config, logging, session state, fast-path routing
│   ├── test_providers.py     # BaseLLMProvider, MockProvider, streaming, cancellation
│   ├── test_orchestrator.py  # Bounded execution, step limits, loop detection, router
│   ├── test_security.py      # Autonomy modes, path validation, prompt injection
│   ├── test_tools.py         # Tool registry, built-in tools, skill loader, MCP client
│   ├── test_memory.py        # SQLite persistence, FTS5 search, summarization, pruning
│   ├── test_voice.py         # STT/TTS pipeline, chunking, barge-in cancellation
│   └── test_sync.py          # E2EE client encryption, conflict resolution, device pairing
├── integration/
│   ├── test_e2e_api.py       # Full HTTP/WebSocket API workflows and SSE streaming
│   └── test_persistence.py  # DB migrations, crash recovery, session restoration
└── security/
    └── test_sandboxing.py    # Path traversal escapes, malicious skills, secret leaks
```

---

## 3. Test Execution Commands

All tests must be executed using the local virtual environment interpreter:

```bash
# Run all unit tests
.venv/bin/pytest tests/unit/ -v

# Run security & sandboxing tests
.venv/bin/pytest tests/security/ -v

# Run integration tests
.venv/bin/pytest tests/integration/ -v

# Run the complete test suite with coverage reporting
.venv/bin/pytest tests/ --cov=jarvis --cov-report=term-missing

# Run a specific test module
.venv/bin/pytest tests/unit/test_security.py -v
```

---

## 4. Provider Compatibility Matrix

| Provider / Runtime | Interface | Tool Calling | Streaming | Cancellation | Verified Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Mock Provider** | In-Memory / Deterministic | Yes | Yes | Yes | Fully Verified (Automated Suite) |
| **Ollama** | Local REST / OpenAI-compat | Yes | Yes | Yes | Supported / Mock-tested |
| **LM Studio** | Local REST / OpenAI-compat | Yes | Yes | Yes | Supported / Mock-tested |
| **llama.cpp** | Local REST / OpenAI-compat | Yes | Yes | Yes | Supported / Mock-tested |
| **OpenAI** | Hosted REST | Yes | Yes | Yes | Adapter implemented / Mock-verified |
| **Anthropic** | Hosted REST | Yes | Yes | Yes | Adapter implemented / Mock-verified |
| **Gemini** | Hosted REST | Yes | Yes | Yes | Adapter implemented / Mock-verified |

---

## 5. Failure Scenarios Verified

The test suite explicitly asserts correct behavior for:
1. **Network Interruptions & Timeouts**: Adapters fail gracefully with structured error events rather than crashing the orchestrator.
2. **Provider Rate Limiting**: Exponential backoff retry logic is exercised.
3. **Infinite Tool Loops**: Repetitive tool calls are detected and halted by the orchestrator budget.
4. **Path Traversal Attacks**: Attempts to read or write `../../etc/passwd` or symlink escapes raise `SecurityError`.
5. **Prompt Injection in Tool Output**: Malicious instructions embedded in simulated tool results cannot bypass permissions.
6. **Task Cancellation**: Tasks in progress cleanly terminate when cancellation token is triggered.
7. **Barge-in Voice Interruption**: Active audio playback and generation are aborted when voice input is received.

---

## 6. Automated Verification Results

Latest automated test run executed locally:
- **Total Tests**: 67 passed in 8.96s
- **Total Code Coverage**: 80%
- **Core Components Verified**:
  - Foundation, sessions, config, detector (93%)
  - Memory persistence & FTS5 search (81%)
  - Bounded multi-step orchestrator & universal context injection (87%)
  - Provider adapters (OpenAI-compatible, Anthropic, Gemini, Mock)
  - Security policies & deterministic permission gate (96%)
  - Built-in 11-tool registry & MCP client (94%)
  - Zero-API-key Web Search with Google & DuckDuckGo scraping (51%)
  - Interactive Security Approval & Tool Execution Resolution
  - Kokoro 82M TTS & audio streaming (62%)
  - End-to-end API & Web UI integration (89%)
