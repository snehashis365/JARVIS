# Jarvis — Product Requirements Document (PRD)

## 1. Executive Summary & Purpose

Jarvis is a capable, modular, desktop-first personal AI assistant. It provides persistent, transparent, and private AI capabilities on modest hardware without requiring specialized GPUs, large amounts of RAM, or paid cloud APIs.

Jarvis functions as a reliable conversational partner, task orchestrator, researcher, and local operator. It enforces strict, deterministic security boundaries and provides user-controlled privacy, modular LLM connectivity, and natural voice interaction.

---

## 2. Product Principles

1. **Local-First, Not Local-Only**: Operates 100% locally with local models (e.g., Ollama, LM Studio, llama.cpp), while seamlessly integrating hosted cloud providers (OpenAI, Anthropic, Gemini) if and when explicitly configured by the user.
2. **Provider-Neutral Architecture**: Decoupled from any single model provider or runtime. Switching providers or models never alters the assistant's personality, memory, tools, or permission rules.
3. **Deterministic Permission Enforcement**: Autonomy is governed by deterministic software permissions in code, not model self-policing or system prompts.
4. **Transparent & Observable**: The assistant makes its internal state visible (idle, listening, thinking, speaking, tool execution, awaiting approval, error recovery). Private chain-of-thought is kept secure while actions and rationales are clearly reported.
5. **Resource-Aware Performance**: Designed to run comfortably on modern laptops (4–8 CPU cores, 8–16 GB RAM) with adaptive resource throttling and low-latency response streaming.
6. **Graceful Degradation & Recoverability**: Long tasks, network disruptions, tool failures, and application restarts are safely checkpointed and recoverable.

---

## 3. Target User Personas & Use Cases

### 3.1 Primary Personas
- **Developer & Power User**: Needs local code assistance, documentation lookup, file transformations, script execution, and task automation with zero telemetry or unexpected cloud data leakage.
- **Privacy-Conscious Professional**: Manages notes, research summaries, task tracking, and daily schedule assistance entirely offline or with strict per-data-category cloud permissions.
- **Hands-Free Desktop Operator**: Uses natural voice commands (push-to-talk / wake phrase) for quick queries, dictation, and system task execution with immediate speech interruption capabilities.

### 3.2 Core Use Cases
1. **Conversational Assistance**: Instant answers, explanations, brainstorming, and writing assistance with consistent assistant identity and tone.
2. **Safe Workspace Operations**: Inspecting, searching, reading, creating, and modifying workspace files governed by strict path allowlists and approval policies.
3. **Bounded Web & Research Tasks**: Querying external or local sources, summarizing articles, and synthesizing knowledge without infinite agent loops.
4. **Natural Voice Interaction**: Real-time push-to-talk voice input, streaming text-to-speech output, low time-to-first-audio, and instant speech cancellation on user interruption (barge-in).
5. **Structured Memory & Recall**: Remembering user preferences, project conventions, and key facts across sessions while offering explicit inspect/edit/delete controls.

---

## 4. Key Functional Requirements

### 4.1 Operating Modes
Jarvis supports three operational modes that dictate model inference:
- **Local Mode (Default)**: All inference and context processing remain on the local machine via local backends (Ollama, LM Studio, llama.cpp). Network access is restricted to user-permitted tools.
- **Cloud Mode**: Tasks are dispatched to configured hosted providers (OpenAI, Anthropic, Gemini, OpenRouter) via API keys provided by the user.
- **Hybrid Mode**: Intelligent, policy-driven routing. Simple conversational prompts and privacy-sensitive queries stay local; compute-heavy tasks or specialized reasoning can optionally route to cloud models according to user policy.

### 4.2 Autonomy & Permission Modes
All tool executions and state mutations are gated by one of four deterministic autonomy levels:
1. **Plan Mode**: Read-only inspection within allowlisted paths. Jarvis produces structured execution plans and explains actions, but cannot mutate any state.
2. **Agent Decides Mode (Default)**: Jarvis autonomously performs low-risk read/search operations. Any state-changing action (file write/delete, shell execution, external network call) triggers a deterministic approval prompt.
3. **Auto Mode**: Jarvis autonomously executes multi-step workflows within strictly pre-approved scope boundaries (e.g., maximum budget of 10 tool calls, allowlisted directory tree, 60s timeout). High-consequence actions (deletion, privilege escalation, external sharing) still require approval.
4. **Sandbox-Only Mode**: Actions execute exclusively in constrained sandbox boundaries. Jarvis verifies path isolation, restricted environment variables, and absence of external access before proceeding.

### 4.3 Conversation & Orchestration Lifecycle
- **Dual-Path Routing**:
  - *Direct Fast Path*: Standard conversational queries bypass agent loops and planners, streaming directly from the model to minimize latency.
  - *Bounded Tool Path*: Queries requiring tools instantiate an orchestrator with step limits, loop detection, timeout enforcement, and progress updates.
- **Streaming & Cancellation**: Streaming tokens and tool-call events to UI/speech output. The user can cancel generation or tool execution at any millisecond.

### 4.4 Tool, Skill & Integration System
- **Registry**: Typed schemas, explicit argument validation, permission tags, and deterministic preconditions for every tool.
- **Skills**: Declarative collections of workflows and instructions defining how tools are composed for specific jobs (e.g., repository analyzer, doc synthesizer).
- **Model Context Protocol (MCP)**: Pluggable adapter support to connect standardized MCP server tools safely.

### 4.5 Memory & Context Management
- **Tiered Memory Categories**:
  - *Working Context*: Current conversation window and active task buffers.
  - *User Profile & Preferences*: Stable facts, preferred names, tone, formatting conventions.
  - *Episodic Task Memory*: Summaries of completed tasks, outcomes, and checkpoints.
  - *Procedural Workflows*: Learned patterns and user-approved shortcuts.
- **Governance**: User-accessible memory explorer to view, edit, search, export, and delete individual memory items or entire domains.

### 4.6 Voice & Audio Subsystem
- **Speech-to-Text (STT)**: Integration with local Whisper / faster-whisper engines (or mock audio processors in test environments).
- **Text-to-Speech (TTS)**: Integration with lightweight local neural TTS (Kokoro-82M / Piper) supporting sentence chunking and streaming audio playback.
- **Barge-In (Interruption)**: Automatic silence/speech detection that cancels ongoing speech playback and model generation when the user speaks.

### 4.7 Optional Decoupled Cloud Sync
- **Independent from Inference**: Sync operates independently of LLM hosting. A user can run local inference with encrypted cloud sync, or cloud inference with zero sync.
- **End-to-End Encryption**: Client-side encryption for synchronized preferences, memory entries, and skill configs.
- **Conflict Handling**: Deterministic last-write-wins with field-level conflict tracking and device revocation.

---

## 5. Non-Functional & Quality Requirements

- **Local Resource Consumption**: Idle RAM < 150 MB for backend service; startup time < 2.0 seconds.
- **Security & Privacy**: Zero plaintext credential logging. Sensitive fields redacted in all debug output. Absolute workspace path boundary enforcement.
- **Reliability & Testability**: 100% of core orchestration, permission, tool execution, and adapter routines must run against local mocks without requiring external network or paid API accounts.
- **Cross-Platform Compatibility**: Full operational support on macOS and Linux, with clean path and process abstraction for Windows.

---

## 6. Success Metrics & Acceptance Criteria

1. **Safety**: 0 unauthorized file writes, network requests, or path escapes across all test suites and operational runs.
2. **Responsiveness**: Fast-path conversational response start (time to first token) under 500ms on local models (or mock endpoints).
3. **Autonomy Reliability**: Zero unbounded agent loops; all tasks bounded by configurable limits.
4. **Verifiable Quality**: Comprehensive automated test coverage spanning unit, integration, security, voice, and regression suites.
