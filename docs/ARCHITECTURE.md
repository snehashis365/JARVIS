# Jarvis — System Architecture Document

## 1. Architectural Style: Modular Monolith

Jarvis is architected as an extensible **modular monolith**. This avoids the operational complexity, serialization overhead, network latency, and deployment failure modes of microservices, while enforcing strict encapsulation between logical subsystems via typed contracts and explicit interfaces.

```mermaid
graph TD
    UI[Desktop Web Shell / UI Frontend] <-->|HTTP / WebSockets / SSE| API[Backend Service & Gateway]
    
    subgraph Core[Jarvis Modular Monolith Core]
        API --> Orchestrator[Conversation & Task Orchestrator]
        API --> SessionMgr[Session & Task State Manager]
        
        Orchestrator --> Router[Model Router & Selector]
        Router --> ProviderAdapters[Provider Adapters: Local / Cloud / Mock]
        
        Orchestrator --> PermMgr[Deterministic Permission Manager]
        PermMgr --> ToolRuntime[Tool & Skill Runtime]
        ToolRuntime --> ToolRegistry[Tool Registry & MCP Client]
        
        Orchestrator --> MemorySubsystem[Memory & Context Engine]
        MemorySubsystem --> SQLite[(Local SQLite DB + FTS5)]
        
        API --> VoicePipeline[Voice Subsystem: STT / Audio Chunking / TTS]
        VoicePipeline --> AudioOutput[Audio I/O & Interruption Controller]
        
        API --> SyncClient[Optional E2EE Cloud Sync Client]
    end
```

---

## 2. Subsystem Decompositions & Responsibilities

### 2.1 Interface & Desktop Layer (`src/jarvis/server`)
- Exposes REST, Server-Sent Events (SSE), and WebSocket endpoints.
- Lightweight, self-contained desktop UI served directly from FastAPI / Starlette, accessible via browser or embedded WebView / Tauri.
- Provides real-time event streaming for tokens, tool execution progress, speech waveforms, permission prompts, and system telemetry.

### 2.2 Core Orchestration & Session (`src/jarvis/core`)
- **Conversation Manager**: Handles conversational turns, history management, and direct fast-path routing.
- **Task Orchestrator**: Executes bounded workflows for tool-assisted requests. Maintains execution budgets (max steps, timeouts, recursion depth).
- **Session Manager**: Manages active sessions, serializes conversation state, and enables seamless task resumption after application restart.

### 2.3 Provider Adapters & Capability Registry (`src/jarvis/providers`)
- **Normalized Contract**: Standardized abstraction (`BaseLLMProvider`) supporting `generate()`, `stream()`, `embed()`, and capability introspection.
- **Adapters**:
  - `LocalProvider`: Connects to Ollama, LM Studio, llama.cpp, or custom local OpenAI-compatible endpoints.
  - `HostedProvider`: Configurable adapters for OpenAI, Anthropic, Gemini, OpenRouter.
  - `MockProvider`: High-fidelity, deterministic in-memory provider for automated tests and offline simulation.
- **Capability Registry**: Dynamically discovers and tracks model capabilities (tool use, JSON schema, vision, max context, streaming latency).

### 2.4 Model Selection & Intelligent Router (`src/jarvis/routing`)
- Evaluates incoming prompts against policies (Local, Hybrid, Cloud).
- Analyzes complexity, required tools, and context window requirements.
- Generates transparent, human-readable explanations for routing decisions without leaking internal chain-of-thought.

### 2.5 Deterministic Permission Enforcement (`src/jarvis/security`)
- **Permission Engine**: The sole authoritative gate for executing any external action or tool.
- Evaluates autonomy modes (`Plan`, `Agent Decides`, `Auto`, `Sandbox Only`).
- Enforces strict path boundaries (resolving real paths, preventing symlink escapes and traversal).
- Maintains tamper-evident audit logging for all attempted and completed actions.

### 2.6 Tool, Skill & MCP Runtime (`src/jarvis/tools`)
- **Tool Registry**: Strongly typed Pydantic parameter schemas, execution preconditions, permission tags, and timeouts.
- **Built-in Tools**: Safe file reading/writing (path-restricted), web search abstraction, computer inspection, system diagnostics.
- **Skill Engine**: Declarative YAML/JSON skill manifests defining multi-step workflow prompts and required tools.
- **MCP Client**: Standardized connector supporting Model Context Protocol tool definitions.

### 2.7 Tiered Memory & Context Engine (`src/jarvis/memory`)
- Local SQLite database with Write-Ahead Logging (WAL) and automated migrations.
- Categories: Working memory, User profile/preferences, Episodic task history, Procedural recipes.
- Hybrid retrieval: Fast BM25 full-text search (SQLite FTS5) coupled with optional embedding vector distance ranking.
- Context budgeting: Automatically summarizes old turns to stay safely within model token limits.

### 2.8 Voice & Audio Subsystem (`src/jarvis/voice`)
- **Speech-to-Text (STT)**: Streaming audio capture and chunk transcription via local Whisper/faster-whisper or test mock.
- **Text-to-Speech (TTS)**: Chunk-level neural TTS generation (Kokoro-82M / Piper).
- **Interruption Manager**: Asynchronous event listener capable of aborting active audio playback and backend generation upon detecting user voice activity (barge-in).

### 2.9 Optional Cloud Sync (`src/jarvis/sync`)
- Completely decoupled from LLM inference.
- Client-side AES-GCM encryption of preferences, memories, and skills before transmission.
- Offline-first synchronizer with deterministic conflict resolution (field-level timestamping/vector clocks).

---

## 3. Data Flows & Sequence Diagrams

### 3.1 Fast-Path Conversational Request
```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Server as API Gateway
    participant Orchestrator as Assistant Core
    participant Router as Model Router
    participant Provider as LLM Provider
    
    User->>Server: Send Message ("Hello Jarvis")
    Server->>Orchestrator: handle_message()
    Orchestrator->>Router: route_request()
    Router-->>Orchestrator: Route: Local fast model (no tools needed)
    Orchestrator->>Provider: stream(prompt)
    loop Token Generation
        Provider-->>Orchestrator: token chunk
        Orchestrator-->>Server: SSE stream chunk
        Server-->>User: Render token in UI
    end
    Orchestrator->>Orchestrator: Persist conversation turn
```

### 3.2 Bounded Tool Execution with Permission Gate
```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Orchestrator as Task Orchestrator
    participant Provider as LLM Provider
    participant PermMgr as Permission Manager
    participant Tool as Tool Runtime
    
    User->>Orchestrator: "Analyze workspace and write summary to notes.txt"
    Orchestrator->>Provider: generate_with_tools()
    Provider-->>Orchestrator: Tool Call Request: write_file("notes.txt", content)
    Orchestrator->>PermMgr: request_permission(tool="write_file", path="notes.txt")
    
    alt Autonomy Mode: Agent Decides (Requires Approval)
        PermMgr-->>Orchestrator: PENDING_APPROVAL
        Orchestrator-->>User: Prompt: "Allow write_file on notes.txt? [Y/N]"
        User->>Orchestrator: Approve Action
        Orchestrator->>PermMgr: record_approval(token)
    end
    
    PermMgr->>PermMgr: Validate Path (inside project root, no symlink escape)
    PermMgr-->>Orchestrator: PERMISSION_GRANTED
    Orchestrator->>Tool: execute("write_file", args)
    Tool-->>Orchestrator: Execution Result (success)
    Orchestrator->>PermMgr: log_audit_trail(action, status=SUCCESS)
    Orchestrator->>Provider: Submit tool result
    Provider-->>Orchestrator: "Successfully wrote summary to notes.txt"
    Orchestrator-->>User: Final Response
```

### 3.3 Voice Pipeline with Barge-in Interruption
```mermaid
sequenceDiagram
    autonumber
    actor User
    participant AudioMgr as Audio / Voice Controller
    participant Orchestrator as Assistant Core
    participant TTS as TTS Engine
    
    Orchestrator->>TTS: Stream response text chunks
    TTS-->>AudioMgr: Stream audio PCM buffers
    AudioMgr->>User: Playback Audio Response
    
    User->>AudioMgr: User starts speaking ("Stop, Jarvis")
    AudioMgr->>AudioMgr: Detect Voice Activity / Barge-In
    AudioMgr->>AudioMgr: Immediately Halt Audio Buffer Playback
    AudioMgr->>Orchestrator: cancel_current_task()
    Orchestrator->>Orchestrator: Cancel LLM generation & tool work
    AudioMgr->>Orchestrator: Process new speech input
```

---

## 4. Key Data Contracts & Schemas

### 4.1 Message & Role Schema
```python
class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

class ChatMessage(BaseModel):
    role: MessageRole
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

### 4.2 Tool Execution & Schema
```python
class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters_schema: Dict[str, Any]
    requires_permission: bool = True
    read_only: bool = False
    timeout_seconds: float = 30.0

class ToolCall(BaseModel):
    id: str
    tool_name: str
    arguments: Dict[str, Any]

class ToolResult(BaseModel):
    tool_call_id: str
    status: Literal["success", "error", "rejected"]
    output: Any
    error_message: Optional[str] = None
```

### 4.3 Permission Policy Schema
```python
class AutonomyMode(str, Enum):
    PLAN = "plan"
    AGENT_DECIDES = "agent_decides"
    AUTO = "auto"
    SANDBOX_ONLY = "sandbox_only"

class PermissionRequest(BaseModel):
    request_id: str
    tool_name: str
    action_type: Literal["read", "write", "delete", "execute", "network"]
    resource_path: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    justification: str

class PermissionDecision(BaseModel):
    request_id: str
    allowed: bool
    requires_user_prompt: bool
    reason: str
```

---

## 5. Storage & Persistence Architecture

- **Engine**: SQLite 3 with Write-Ahead Logging (`PRAGMA journal_mode=WAL;`), Foreign Keys enabled (`PRAGMA foreign_keys=ON;`), and synchronous normal mode for high throughput.
- **Location**: Strictly confined to `<workspace_root>/data/jarvis.db`.
- **Migrations**: Lightweight schema version table (`schema_migrations`) executing transactional DDL updates on startup.
- **Tables**:
  - `sessions` / `messages`: Chat histories, token metrics, metadata.
  - `tasks`: Active and archived task states, step counts, checkpoint payloads.
  - `memories`: Structured user facts, episodic experiences, categories, confidence, timestamps.
  - `audit_logs`: Cryptographically chained or append-only audit trail of all security decisions and executed actions.
  - `settings`: Assistant identity, provider configurations, privacy preferences.
