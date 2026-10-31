# Jarvis — Comprehensive User and Developer Guide

## 1. Introduction

Jarvis is a modular, desktop-first personal AI assistant built for high privacy, transparent observability, and deterministic software security. It runs 100% locally on standard consumer hardware, with seamless, opt-in support for hosted cloud models and multi-device encrypted synchronization.

---

## 2. Quickstart & Installation

### 2.1 Prerequisites
- Python 3.12+
- Operating System: macOS, Linux, or Windows (WSL / native)

### 2.2 Environment Setup
The project uses an isolated Python virtual environment `.venv` located at the project root:

```bash
# 1. Initialize local virtual environment (if not already created)
python3 -m venv .venv

# 2. Install dependencies in editable mode
.venv/bin/pip install -e ".[dev]"

# 3. Copy configuration example
cp .env.example .env
```

### 2.3 Starting Jarvis
Launch the desktop assistant server:

```bash
# Option A: Using the launch script
bash run.sh

# Option B: Direct CLI invocation
.venv/bin/python -m jarvis.cli start --host 127.0.0.1 --port 8000
```

Once started, open your browser and navigate to:
**`http://127.0.0.1:8000`**

### 2.4 First-Run GUI Setup Wizard
When launching Jarvis for the first time without an active configuration (`data/config.json`), Jarvis automatically presents the **Initial Setup Wizard**:
1. **Local LLM Auto-Detection**: Jarvis actively probes running instances of **Ollama** (port 11434), **LM Studio** (port 1234), and **llama.cpp** (port 8080), fetching their installed models and response latencies in real-time.
2. **Custom OpenAI-Compatible Endpoints**: You can specify custom server URLs (e.g. vLLM, Together AI, Groq, Ollama remote, self-hosted proxies) following standard OpenAI `/v1/models` conventions.
3. **Cloud Providers Dropdown**: Seamlessly configure OpenAI, Anthropic, or Google Gemini with your API keys and target model tags.
4. **Local Gitignored Persistence**: Configurations are stored in `data/config.json` (strictly gitignored) while `config.template.json` provides a clean empty reference template.
5. **Re-running Setup Anytime**: Click the **⚙️ Setup Wizard** button in the header at any time to re-scan local backends or adjust provider configurations on the fly.

To run an interactive terminal chat session directly:
```bash
.venv/bin/python -m jarvis.cli chat
```

To view system and hardware profiling:
```bash
.venv/bin/python -m jarvis.cli status
```

---

## 3. Operating Modes & Model Configuration

Configure your preferred inference mode in `.env` or via the web settings interface:

### 3.1 Local Mode (Default)
Inference and sensitive processing stay entirely on your device.
- Point `JARVIS_LOCAL_ENDPOINT` to your local engine (e.g., Ollama at `http://127.0.0.1:11434/v1`, LM Studio at `http://127.0.0.1:1234/v1`, or llama.cpp server).
- Set `JARVIS_LOCAL_MODEL` to your preferred model (e.g. `llama3.2`, `qwen2.5-coder`).

### 3.2 Cloud Mode
Requests are dispatched to hosted cloud providers using your configured API keys:
- `OPENAI_API_KEY` (model: `gpt-4o`)
- `ANTHROPIC_API_KEY` (model: `claude-3-5-sonnet-20241022`)
- `GEMINI_API_KEY` (model: `gemini-2.0-flash`)

### 3.3 Hybrid Mode
Smart, policy-driven routing:
- Short conversational queries stay local for zero latency and privacy.
- Complex reasoning or multi-step tool tasks route to configured cloud models according to user policy.

---

## 4. Autonomy Modes & Deterministic Security

Security in Jarvis is strictly enforced in code via `PermissionManager` and canonical `PathValidator`, never by system prompts alone.

| Autonomy Mode | Read Actions | Mutating Actions (Write, Delete, Execute) |
| :--- | :--- | :--- |
| **Plan** | Allowed within workspace | Strictly Denied (read-only plan preparation) |
| **Agent Decides (Default)** | Allowed within workspace | Interactive User Approval Prompt Required |
| **Auto** | Allowed within workspace | Pre-approved within budget; Deletion requires approval |
| **Sandbox Only** | Restricted to `data/sandbox/` | Restricted to `data/sandbox/`; Network/Exec prohibited |

### 4.1 Interactive Approval Workflow
When Jarvis requests a mutating action in `Agent Decides` mode:
1. A yellow **Approval Required** banner appears in the desktop web UI.
2. The user inspects the tool name, action type, and target resource.
3. Clicking **Approve** or **Reject** transmits the cryptographic decision to the backend.
4. All actions and decisions are permanently recorded in `logs/security_audit.jsonl`.

---

## 5. Tools, Skills, and Integrations

### 5.1 Extensive Built-in Toolset (11 Tools)
Jarvis comes with 11 built-in, security-governed tools accessible by the assistant during tasks or testable directly in the web UI:
- **Filesystem**:
  - `workspace_read_file`: Safely read UTF-8 files within workspace boundaries.
  - `workspace_write_file`: Controlled writing with overwrite and permission checks (ActionType.WRITE).
  - `workspace_delete_file`: Safely remove files within workspace (ActionType.DELETE, requires approval in Agent Decides mode).
  - `workspace_list_directory`: Inspect directories within the workspace.
  - `workspace_search_files`: Fast glob search (e.g. `*.py`, `**/*.md`) and content substring filtering.
- **Web & Research**:
  - `web_search`: Query web topics with offline synthesis fallback.
  - `web_fetch`: Retrieve text or JSON content from public URLs.
- **System & Terminal**:
  - `system_diagnostics`: Inspect OS, CPU count, architecture, and Python runtime metrics.
  - `datetime_now`: Current system timestamp, date, time, and timezone.
  - `calculate_expression`: Safe mathematical expression evaluation using AST (no unsafe `eval`).
  - `execute_shell_command`: Bounded workspace shell execution (ActionType.EXECUTE, gated by approval in Agent Decides mode).

### 5.2 Interactive Tool Runner & Chat Cards
- **Sidebar "🛠️ Tools" Tab**: Browse all 11 tools, inspect their parameters, and click **"⚡ Test Run"** to execute any tool with custom parameters and view the immediate output.
- **Live Tool Cards in Chat**: When Jarvis decides to invoke a tool, an expandable card appears in the chat stream showing the tool name, arguments, and live output.

### 5.3 Skills
Skills are modular, inspectable YAML/JSON workflows.
- View and toggle skills in the **Skills** tab of the web interface or via `GET /api/skills`.
- Built-ins include `workspace_analyzer` and `web_researcher`.

### 5.4 Model Context Protocol (MCP)
External tools exposed by MCP servers are automatically wrapped in native `BaseTool` instances and guarded by the same permission checks.

---

## 6. Structured Memory & Continuity

Jarvis stores memories locally in SQLite with Write-Ahead Logging (WAL) and FTS5 indexing.
- **Categories**: Working, Preferences, Facts, Episodic History, Procedural Workflows.
- **Search**: Fast BM25 full-text search across titles and contents.
- **Context Budgeting**: Automatic summarization of older conversational turns ensures prompts never exceed context window budgets.
- **Inspection & Creation**: View, search, add, or delete memories anytime in the **Memory** tab.

---

## 7. Voice Pipeline, Speech UI & Interruption

- **Immersive Voice Mode**: Click **"🎙️ Voice Mode"** in the top navigation to open the full-screen voice interaction modal with the pulsing Jarvis audio orb.
- **Push-to-Talk**: Hold Spacebar or tap the microphone button (`🎙️`) on the chat input bar to speak. Real-time speech recognition transcribes your input as you talk.
- **Spoken Assistant Responses (TTS)**: When **🔊 Auto-Speak** is enabled, Jarvis speaks answers out loud with natural voice synthesis.
- **Barge-in Interruption**: Click **⏹️ Stop** or press Escape while Jarvis is speaking or generating to immediately interrupt the voice output and model generation.

---

## 8. Optional Decoupled Cloud Sync

Sync is 100% opt-in and independent from inference:
- Client-side **AES-256-GCM** encryption using PBKDF2 key derivation.
- Synchronizes user preferences, personality profiles, and curated facts.
- Never synchronizes raw chat history, credentials, or private files.
- Local mode remains 100% functional without cloud sync.

---

## 9. Running Automated Tests

All tests execute against local mock providers and in-memory databases with zero paid API costs:

```bash
# Run complete test suite with coverage
bash scripts/run_tests.sh

# Run specific test suites
.venv/bin/pytest tests/unit/
.venv/bin/pytest tests/security/
.venv/bin/pytest tests/integration/
```
