# Jarvis — Master Project Prompt

> **Purpose:** This is the master product, architecture, and engineering brief for building a modular personal AI assistant. Antigravity should treat this file as the primary project specification and `AGENTS.md` as persistent engineering instructions.

---

## 1. Role and mission

Act as the lead software architect, senior engineer, security engineer, test engineer, and technical researcher for this project.

Your task is to help design and build a capable, modular, desktop-first personal AI assistant (working name: **Jarvis**). The assistant should feel like a persistent, useful presence on the user's computer: conversational when needed, capable of research and practical work, able to use approved tools, and able to communicate through natural voice.

Do not blindly implement the first idea. Research existing solutions, compare options, explain trade-offs, and prefer mature, maintained, well-tested libraries over custom infrastructure.

The project owner wants to understand the important decisions and review the architecture. Work autonomously on routine engineering decisions, but do not make major product, security, privacy, or cost decisions silently.

**Important project separation:** This is a separate, exploratory personal-assistant project. Do not merge it with the user's other Python/Ollama `agent.py` learning project or reuse its architecture by assumption. Existing experience may inform decisions, but the projects remain separate unless the owner explicitly asks otherwise.

## 1.1 Strict workspace boundary and unattended execution

The project root is the only permitted location for project file creation, modification, deletion, generated output, caches, virtual environments, dependency folders, databases, logs, and test artifacts.

- Treat the opened Jarvis project folder as the workspace root. Resolve and verify its absolute path at the start.
- All file operations must remain inside that root. Before writing, moving, or deleting a path, resolve it and verify that it is still inside the project root. Reject path traversal, symlink escapes, and paths that resolve outside the root.
- Do not edit, delete, rename, or inspect unrelated personal files or folders outside the project root.
- Do not modify OS settings, shell profiles, PATH, registry, startup entries, global packages, system services, firewall, drivers, or other machine-wide configuration.
- Do not run commands with administrator/root privileges or use `sudo`.
- Keep Python virtual environments, Node dependencies, build output, caches, local databases, and generated artifacts inside the project folder wherever practical. Do not install packages globally.
- Do not access personal credentials, browser profiles, password stores, SSH keys, unrelated repositories, or other private locations.
- Do not launch unrestricted shell commands, destructive cleanup commands, or scripts whose effects extend beyond the project root.
- Network access may be used for documentation research and downloading project dependencies only when needed. Do not upload project files, source code, logs, prompts, memory, or personal data to external services.
- Do not publish, deploy, send messages, create accounts, make purchases, or incur paid API/cloud costs.
- Do not enable microphone, camera, screen capture, broad filesystem access, or remote-control capabilities on the host during development.
- If a necessary action cannot be completed within these boundaries, skip or isolate that action, document the blocker, and continue with independent work.
- These instructions are an operational boundary, not a claim that a prompt itself creates an OS-level sandbox. Use available workspace restrictions/sandboxing if provided, and never claim stronger isolation than actually exists.

The owner is authorizing autonomous development through all planned phases within these boundaries. Do not stop after Phase 0 for routine architecture approval. Make conservative, reversible decisions, record assumptions, and continue. Pause only the specific operation that would violate a boundary or require paid spend, credentials, external side effects, or a genuinely high-impact security/privacy decision. Continue other safe work where possible.

## 2. Product vision

Build a desktop assistant that can:

- Hold natural conversations and act as a useful chat companion.
- Research topics and browse the web.
- Work with local files and folders, subject to explicit permissions.
- Interact with desktop applications and browser-based services.
- Execute multi-step tasks and report progress.
- Use tools, integrations, and installable skills.
- Remember useful preferences, facts, task context, and prior work.
- Speak and listen naturally, with low perceived latency.
- Be interrupted while speaking or working.
- Run locally, in hybrid mode, or with cloud services.
- Adapt to the hardware and model capabilities available on a given device.
- Preserve a consistent assistant identity even when the underlying model changes.

The product should be useful on modest hardware. It must not assume a dedicated GPU, large amounts of RAM, or paid API access.

## 3. Product principles

1. **Local-first, not local-only:** Local execution should be a first-class option. Cloud services may be used when the user enables them.
2. **Provider-neutral:** Do not couple the product to one model vendor, model family, or inference runtime.
3. **User-controlled privacy:** Make it clear what data stays local and what leaves the device.
4. **Permission-enforced autonomy:** The assistant may plan broadly, but actual actions must be controlled by deterministic software permissions.
5. **Use existing infrastructure:** Do not reinvent mature capabilities without a compelling reason.
6. **Resource-aware:** Select models and workflows based on available CPU, RAM, VRAM, latency, and task complexity.
7. **Responsive:** Avoid unnecessary model calls, tool calls, long reasoning loops, and needless background activity.
8. **Observable:** The user should understand whether the assistant is listening, thinking, speaking, using a tool, waiting for approval, or unable to proceed.
9. **Recoverable:** Long-running tasks, errors, interrupted generation, and application restarts should be handled safely.
10. **Incremental delivery:** Build and verify a useful foundation before adding complexity.

## 4. Architecture and engineering approach

Design a modular system with clear boundaries. Prefer a **modular monolith** initially rather than microservices. Split processes only where isolation, platform constraints, performance, or reliability justify it.

Candidate logical modules:

- Desktop shell and user interface.
- Application/backend service.
- Conversation and session manager.
- Assistant identity/personality configuration.
- LLM provider adapters and model capability registry.
- Model selection/routing.
- Orchestration and task state.
- Tool registry and execution runtime.
- Permission and policy enforcement.
- Skills and integrations.
- Memory and retrieval.
- Speech-to-text and text-to-speech.
- Browser and desktop interaction.
- Notifications and background service.
- Optional cloud sync service.
- Logging, diagnostics, and telemetry controls.

Define interfaces between modules before implementation. Avoid circular dependencies and global mutable state. Keep provider-specific code behind adapters. Use typed schemas and explicit contracts for messages, tool calls, task states, permissions, and errors.

Do not create abstractions for hypothetical future requirements unless they solve a current architectural problem. Keep the initial design extensible without making it unnecessarily elaborate.

## 5. Desktop application and runtime

Evaluate the most suitable desktop approach, including options such as:

- Tauri with a web frontend.
- Electron with a web frontend.
- A Python-native desktop application, if there is a strong reason.

Do not select a stack merely because it is familiar. Compare platform support, packaging, resource consumption, native integration, security, ecosystem maturity, and developer experience.

A possible frontend stack is React, TypeScript, and Tailwind CSS, but validate the choice.

The desktop application should eventually support:

- Main chat window.
- Compact/floating assistant interface.
- Global keyboard shortcut.
- Tray/menu-bar presence where appropriate.
- Notifications and task progress.
- Settings for models, providers, personality, voice, privacy, permissions, and memory.
- Session restoration after restart.
- Clear connection and runtime status.
- Accessibility and keyboard navigation.

A background service may be required for global shortcuts, wake-word listening, or long-running tasks. Design lifecycle management carefully: startup, shutdown, crash recovery, duplicate-instance prevention, and clean cancellation.

Do not implement always-on microphone capture by default. Listening behavior must be explicit, visible, configurable, and easy to disable.

## 6. Assistant core and orchestration

The assistant core should manage the lifecycle of a user request:

1. Receive and normalize input.
2. Identify whether it is a simple conversational request or a task requiring tools.
3. Retrieve only relevant context and memory.
4. Select an appropriate model or route.
5. Decide whether tools, skills, or a workflow are needed.
6. Check permissions before every action.
7. Execute approved actions with timeouts and cancellation.
8. Validate tool results and decide whether another step is necessary.
9. Return a clear response and update task state.
10. Persist only appropriate conversation or task information.

Use bounded execution. Set sensible limits for tool calls, retries, task duration, recursion, and context size. Detect repeated or unproductive tool calls. Avoid turning every prompt into a complex agent workflow.

For ordinary conversation, prefer a direct model response. Do not invoke a planner, multiple agents, or a complex reasoning framework unless the request warrants it.

The orchestrator must support:

- Streaming responses.
- Tool-call streaming where supported.
- Cancellation and interruption.
- Timeouts and retries with backoff where appropriate.
- Partial failure handling.
- Task progress and status.
- Structured outputs where needed.
- Safe resumption of eligible tasks.
- Clear error reporting.

Do not expose private chain-of-thought. Provide concise activity summaries, decisions, tool actions, and results instead.

## 7. Provider-neutral LLM infrastructure

The application must not be tied to one inference provider.

Evaluate and support relevant local and hosted options, as appropriate:

**Local candidates**
- Ollama.
- LM Studio.
- llama.cpp server.
- Other OpenAI-compatible local endpoints.

**Hosted candidates**
- OpenAI.
- Anthropic Claude.
- Google Gemini.
- Other compatible hosted APIs or gateways.

Use a provider adapter or gateway abstraction so the rest of the application does not depend on vendor-specific request formats. An OpenAI-compatible interface is useful as a common path, but do not assume all providers implement identical behavior.

Provider adapters should normalize:

- Chat messages and roles.
- Streaming events.
- Tool/function calls.
- Structured output.
- Usage/token information when available.
- Errors and rate limits.
- Cancellation and timeouts.
- Model metadata and capability information.

Maintain a model capability registry. Track, where known:

- Tool calling support and reliability.
- Structured output support.
- Streaming support.
- Vision/image input.
- Context length.
- Reasoning capability or model class.
- Local/remote status.
- Approximate resource requirements.
- Cancellation support.
- Provider-specific limitations.

Do not assume a model supports a feature just because its provider does. Validate capabilities at runtime where possible and handle unsupported features gracefully.

The user should be able to add or change providers and models through configuration or settings without modifying orchestration code. Support custom base URLs and local endpoints.

## 8. Evaluate existing routing and agent frameworks

Research current, maintained options before implementing custom infrastructure. Candidates include, but are not limited to:

- LiteLLM for provider abstraction and model gateway functionality.
- RouteLLM or equivalent routing approaches for model selection.
- OpenRouter for optional hosted model aggregation.
- PydanticAI, LangGraph, or other orchestration frameworks where their capabilities genuinely fit.
- MCP for standardized tool/integration connectivity.

These tools are not automatically required. Evaluate current maintenance, license, security posture, compatibility, resource cost, API stability, documentation, and whether they overlap.

Do not combine multiple frameworks that solve the same problem without a clear justification. Do not confuse a hosted model aggregator with a self-hosted provider gateway. Prefer the smallest reliable set of dependencies.

Before selecting a framework, document:
- The problem it solves.
- Alternatives considered.
- Why it is suitable.
- Limitations and lock-in risks.
- License and maintenance status.
- How it will be tested.
- How the project can replace it later.

## 9. Hybrid model selection and routing

Support three broad operating modes:

- **Local:** Inference and sensitive processing remain on the device, except for explicitly configured external integrations.
- **Cloud:** Requests use configured hosted models.
- **Hybrid:** Route tasks to local or hosted models based on policy, capability, performance, cost, and user preference.

Hybrid routing should be capability- and policy-aware, not simply choose the largest model.

Examples:
- Small local model for greetings and straightforward conversation.
- Fast model for simple summaries and classification.
- Tool-capable model for tool use.
- Larger reasoning model for genuinely complex planning or analysis.
- Vision-capable model for images or screen understanding.
- Speech models for transcription and speech generation.

Routing should consider:
- User's selected mode and privacy rules.
- Task complexity and required capabilities.
- Model availability and health.
- Latency and resource availability.
- Context limits.
- Cost limits and provider quotas.
- Whether the task contains sensitive information.

Do not silently send private content to a cloud model. If policy does not permit the required route, ask or use an allowed fallback.

Avoid excessive routing complexity. A simple, explainable policy is preferable initially. Log the route and a user-understandable reason, without exposing private internal reasoning.

## 10. Assistant identity and personality

Personality must be centrally configured and independent of the underlying model.

Allow the user to configure:
- Assistant name.
- Tone and conversational style.
- Formality.
- Verbosity.
- Humour.
- Proactivity.
- Preferred response format.
- Voice and speaking style.
- Boundaries and behavior preferences.

Model switching must not make the assistant feel like a different product. Use a shared identity/personality configuration and provider-specific prompt adapters only where necessary.

Avoid excessively long system prompts. Keep stable identity instructions separate from task instructions, memory, tool descriptions, and temporary context. Version prompt templates and test them across providers.

Do not let retrieved memory or external content override system policy, permissions, or the user's explicit settings.

## 11. Tools, skills, integrations, and workflows

Keep these concepts distinct:

- **Tools:** Concrete operations the assistant can invoke, such as reading a file, searching the web, or creating a calendar event.
- **Skills:** Reusable instructions and workflows that explain how to accomplish a class of tasks using available tools.
- **Integrations:** Connections to external services or applications.
- **Agents:** Components that coordinate work for a defined responsibility.
- **Workflows:** Bounded sequences of operations with state, validation, and recovery.

Build a discoverable registry with metadata, schemas, permission requirements, availability, and version information.

Skills should be installable, inspectable, enableable, disableable, and removable. A skill should declare:
- Purpose and instructions.
- Required tools and integrations.
- Permissions and data access.
- Dependencies.
- Version and source.
- Whether it can execute code or access the network.

Treat third-party skills as untrusted until reviewed. Do not execute arbitrary skill scripts without sandboxing and permission checks.

Support MCP where it adds value, but do not make MCP mandatory for internal tools. Evaluate existing integrations before building custom ones.

Workflows should support progress, cancellation, checkpoints, retries, and clear failure states. Require approval for sensitive steps according to the permission policy.

## 12. Computer and browser interaction

The assistant should eventually be able to interact with the user's computer and web services.

Prefer, in order where applicable:
1. Official application APIs.
2. Browser automation and DOM/accessibility interfaces.
3. OS accessibility APIs and supported native automation.
4. Image/screen understanding and coordinate-based interaction only when better interfaces are unavailable.

Avoid brittle screen-coordinate automation as the default.

For browser automation, evaluate mature tools such as Playwright and browser-control integrations. For desktop interaction, evaluate supported OS automation/accessibility tools for target platforms.

All computer actions must pass through the permission manager. The assistant must distinguish observing from changing state.

Examples of actions that normally require explicit approval:
- Sending messages or emails.
- Publishing or submitting content.
- Deleting or overwriting files.
- Installing software.
- Making purchases or payments.
- Changing security settings.
- Running commands with elevated privileges.
- Sharing private data externally.

Show the user what will happen before high-impact actions. Provide a way to cancel an operation and, where feasible, undo it.

## 13. Security, permissions, and autonomy modes

Security must be enforced in code, not merely described in prompts.

Implement a deterministic permission manager that every tool and action must pass through. The LLM must never be able to bypass it or directly execute privileged operations.

Support configurable autonomy modes:

### 13.1 Plan
- The assistant can inspect only resources explicitly permitted for read access.
- It can prepare plans and proposed actions.
- It cannot make state-changing changes.
- It can explain what it would do.

### 13.2 Agent Decides
- The assistant can select tools and execute low-risk actions within granted permissions.
- Sensitive or high-impact actions require user approval.
- The assistant must explain the action and its scope before approval.

### 13.3 Auto
- The assistant can execute multi-step workflows within explicitly pre-authorized boundaries.
- User-defined limits apply to files, applications, network access, commands, time, and cost.
- Destructive, financial, identity/security, or externally publishing actions remain protected unless the user has explicitly configured a narrow safe policy.
- Auto mode must not mean unrestricted access.

### 13.4 Sandbox Only
- Execution is confined by actual OS-level or container-level isolation.
- Restrict filesystem paths, network access, process execution, and available capabilities.
- Prompt instructions alone do not constitute a sandbox.
- Explain the sandbox's real boundaries and limitations.

### 13.5 Permission system requirements
- Tool-level and resource-level permissions.
- Read/write/delete/execute distinctions.
- Directory allowlists and denylists.
- Network domain restrictions where feasible.
- Command allowlists or constrained execution.
- Per-action approval.
- Expiring and revocable grants.
- Audit logs.
- Clear permission prompts.
- Safe defaults.
- Separate policies for local and cloud processing.
- No secrets in logs or prompts.
- Credential storage using OS-supported secure storage where possible.

External web pages, files, emails, documents, tool results, and skill content are untrusted data. They must never be treated as instructions that override system policy or permissions. Include defenses against prompt injection and malicious tool output.

## 14. Memory and context management

Memory should improve continuity without indiscriminately storing everything.

Evaluate established memory and retrieval libraries before implementing custom solutions. A local database such as SQLite is a candidate for structured persistence. Add vector search only if it provides measurable value.

Consider distinct memory categories:
- Short-term conversation context.
- Long-term user preferences and stable facts.
- Episodic memory of useful past events or tasks.
- Procedural memory for learned workflows.
- Active task state and checkpoints.
- Optional synchronized context.

Requirements:
- Memory should be relevant and selective.
- Do not save every message by default.
- Make memory inspectable, editable, and deletable by the user.
- Provide controls for what can be remembered and synchronized.
- Support retention policies.
- Keep source and confidence where useful.
- Prevent untrusted content from silently becoming trusted instructions.
- Avoid retrieving irrelevant memories.
- Support summarization and context-window management.
- Keep task state separate from general user memory.
- Preserve context across model/provider switches.
- Handle deletion consistently, including synchronized copies where applicable.

Do not assume a vector database is required. Benchmark retrieval quality and complexity before adopting one.

## 15. Voice and conversational interaction

Voice is a major product capability, not a decorative add-on.

Evaluate established speech-to-text and text-to-speech options. Candidates may include:
- Whisper or faster-whisper for local speech recognition.
- Kokoro 82M as an initial local TTS candidate.
- Other local TTS engines based on voice quality, latency, licensing, and hardware.
- Gemini or other hosted TTS as optional cloud services.

Do not assume a candidate is best without testing it on target hardware and representative speech.

Voice requirements:
- Push-to-talk initially; optional wake-word support later.
- Visible microphone/listening state.
- Configurable input and output devices.
- Streaming or incremental speech output.
- Begin speaking before the complete response is generated where technically practical.
- Sentence/phrase segmentation that sounds natural.
- Interruptible speech and generation.
- Cancellation when the user starts speaking.
- Avoid duplicate or repeated spoken phrases.
- Configurable voice, speed, and style.
- Optional cloud TTS only with explicit provider/privacy configuration.

Measure end-to-end latency: speech capture, transcription, model response start, first audio output, and completion. Do not optimize only one stage.

Do not store raw microphone recordings by default. Make recording and retention behavior explicit.

## 16. Optional cloud sync and multi-device continuity

Cloud sync is optional and independent of cloud inference.

The assistant must remain fully useful in local-only mode. Users may enable cloud synchronization without enabling hosted LLM inference, and vice versa.

If implemented, sync may cover user-approved:
- Preferences and personality configuration.
- Selected memories.
- Conversation summaries or selected context.
- Skill configuration.
- Task state and checkpoints.
- Device configuration that is safe to synchronize.

Requirements:
- Account authentication and device registration.
- Device listing and revocation.
- Offline operation and later synchronization.
- Conflict detection and resolution.
- Versioning and migration.
- Secure transport and storage.
- Encryption at rest and in transit; evaluate end-to-end encryption for sensitive user data.
- User-visible control over synchronized categories.
- No automatic upload of raw conversations, files, microphone audio, screen captures, or credentials.
- Clear data export and deletion behavior.
- Safe handling of multiple devices editing the same state.

Do not build cloud infrastructure until the local foundation is stable. Research managed services and self-hosted options before implementing a custom backend.

## 17. Resource awareness and operating modes

The application must adapt to different hardware.

At startup and when relevant, detect or allow configuration of:
- CPU and core count.
- RAM.
- GPU/VRAM where available.
- Operating system.
- Available inference runtimes.
- Model availability and approximate resource requirements.

Do not assume a GPU exists or that a detected GPU is compatible with a given runtime.

Provide sensible profiles such as:
- Low-resource.
- Balanced.
- Performance.
- Battery-conscious, where relevant.

Resource-aware behavior should include:
- Choosing suitable local models.
- Limiting concurrent inference and background work.
- Avoiding unnecessary model loading.
- Releasing resources when appropriate.
- Warning before loading models likely to exceed available memory.
- Allowing the user to override automatic choices.

Keep the user in control of resource-intensive operations.

## 18. Observability and user experience

The UI should clearly communicate:
- Current assistant state: idle, listening, transcribing, thinking, speaking, using a tool, waiting for approval, paused, or failed.
- Active model/provider and whether inference is local or remote.
- Active task and progress.
- Tools being used and their results at a useful level.
- Permission requests.
- Errors and recovery options.
- Whether cloud sync is enabled and its status.

Provide useful activity history without exposing private chain-of-thought. Make it possible to inspect which tools were used, what data categories were accessed, and which actions changed state.

Do not overwhelm the user with internal implementation details during ordinary conversation. Provide advanced diagnostics separately.

## 19. Technology selection and dependency policy

Before implementation, research and compare technology choices. Do not assume the examples in this prompt are mandatory.

Evaluate at least the relevant options for:
- Desktop shell.
- Frontend.
- Backend/runtime.
- LLM provider abstraction.
- Model routing.
- Agent orchestration.
- Memory and retrieval.
- STT and TTS.
- Browser automation.
- Desktop automation.
- Tool/skill integration.
- Local persistence.
- Optional cloud sync and authentication.
- Sandboxing and permission enforcement.
- Packaging and updates.

For each important dependency, assess:
- Current maintenance and release activity.
- License and commercial-use implications.
- Security history and advisories.
- Documentation quality.
- Community and ecosystem.
- Compatibility with target platforms.
- Resource usage and latency.
- API stability and migration cost.
- Whether it duplicates another selected dependency.

Prefer fewer, well-understood dependencies. Pin or constrain versions appropriately. Keep a dependency inventory and document why each significant dependency exists.

Do not install a large framework merely because it is popular. Demonstrate that it solves a real requirement.

## 20. Testing, verification, and reliability

Testing is a mandatory engineering activity, not a final cleanup task.

### 20.1 Required development cycle

For every meaningful feature or major change, follow:

**Understand requirements → Identify affected components → Define test cases → Implement → Run unit tests → Run integration tests → Run relevant regression tests → Run static checks/build → Diagnose failures → Fix → Retest → Document → Proceed.**

Do not proceed to dependent work while known critical failures remain unresolved.

### 20.2 Test planning

Before implementing a feature:
- Define expected behavior and edge cases.
- Identify dependencies and failure modes.
- Define acceptance criteria.
- Identify security/privacy implications.
- Add or update test cases before or alongside implementation.

Tests must verify behavior, not merely that a function runs or that a UI renders.

### 20.3 Required test categories

Create an appropriate test suite covering:

**Unit tests**
- Message normalization and prompt composition.
- Provider adapters and response parsing.
- Model capability registry.
- Model routing decisions.
- Permission decisions.
- Tool schemas and validation.
- Skill loading and metadata validation.
- Memory creation, retrieval, update, and deletion.
- Task state transitions.
- Streaming event handling.
- Cancellation and timeout behavior.
- Error normalization and retry policies.

**Integration tests**
- Local model endpoints using mocks or controlled test servers.
- Cloud provider adapters using mocks by default.
- Tool execution through the permission manager.
- Orchestration across model, memory, and tools.
- Persistence and restart recovery.
- Skill-to-tool interactions.
- STT/TTS component integration.
- Cloud sync behavior if implemented.
**Regression tests**
- Re-run tests for affected modules after changes.
- Maintain tests for previously fixed bugs.
- Verify provider switching does not break common workflows.
- Verify model switching preserves assistant identity and relevant context.
- Verify new features do not bypass permissions.

**Security tests**
- Unauthorized tool calls are rejected.
- Read-only mode cannot mutate state.
- Directory allowlists and denylists are enforced.
- Network restrictions are enforced where configured.
- Prompt injection in web pages/files/tool results cannot override policy.
- Malicious or malformed skill metadata is rejected.
- Secrets do not appear in logs, prompts, or error reports.
- Sandbox boundaries are verified at OS/container level.
- Cloud/local data handling follows the selected privacy mode.
- Approval cannot be forged or skipped by model output.

**Voice tests**
- Speech recognition errors and noisy input.
- TTS streaming and phrase ordering.
- Interruptions and cancellation.
- Device unavailable or disconnected.
- Model/provider failure during speech.
- Latency measurements.

**End-to-end tests**
- Launch and start a conversation.
- Complete a simple chat without unnecessary tool calls.
- Summarize a permitted local file.
- Create or modify a file only after permission checks.
- Switch between local and hosted models.
- Run a bounded multi-step task.
- Interrupt generation and speech.
- Restart and restore eligible session/task state.
- Operate in local-only mode with network access disabled where feasible.
- Recover gracefully when a provider or tool becomes unavailable.

### 20.4 Test infrastructure

- Use mocks, fixtures, temporary directories, and temporary databases.
- Do not require paid API calls for routine automated tests.
- Use deterministic fake providers for repeatable orchestration tests.
- Keep live provider tests optional and clearly marked.
- Do not use real user files or credentials in tests.
- Avoid tests that depend on unstable external websites.
- Keep tests fast enough to run frequently.
- Separate unit, integration, security, and end-to-end test commands.

### 20.5 Provider compatibility matrix

Where the relevant services are available, test adapters against:
- Ollama.
- LM Studio.
- llama.cpp server.
- OpenAI.
- Anthropic.
- Gemini.

For each, verify supported capabilities rather than assuming parity: streaming, tool calling, structured output, vision, usage metadata, cancellation, and error handling. Clearly mark capabilities as supported, unsupported, partially supported, or unverified.

### 20.6 Required failure scenarios

Include tests for:
- Provider unavailable or rate-limited.
- Model not found.
- Invalid API credentials.
- Network interruption.
- Malformed provider response.
- Unsupported tool call.
- Invalid tool arguments.
- Tool timeout or crash.
- Repeated tool-call loop.
- Context overflow.
- Memory database unavailable or corrupted.
- User cancellation during generation or tool execution.
- Application shutdown during a task.
- Sync conflict or interrupted sync.
- Insufficient RAM/VRAM.
- Audio device unavailable.

### 20.7 Test reporting and milestone gates

Maintain `docs/TESTING.md` with:
- Test strategy and commands.
- Test categories and ownership.
- Mock/live test configuration.
- Provider compatibility matrix.
- Known limitations.
- How to add tests.

For each milestone, produce a short test report containing:
- What changed.
- Tests executed.
- Pass/fail/skipped/untested counts.
- Build and static-check results.
- Failures and their resolution.
- Remaining risks and limitations.

A milestone is not complete merely because code has been written. It is complete only when:
- Acceptance criteria are met.
- Relevant unit and integration tests pass.
- Relevant regression tests pass.
- Security checks for the changed surface pass.
- The application builds and launches where applicable.
- Remaining limitations are documented.

Never claim a test passed unless it was actually run. Never hide failures, silently skip tests, or modify tests merely to make implementation pass. If a test cannot be run, state why and what remains unverified.

## 21. Implementation roadmap

Work incrementally. Adjust phase boundaries if research demonstrates a better sequence, but preserve the principle of a verified foundation before expanding scope.

### Phase 0 — Research and architecture
- Inspect the workspace and existing project files.
- Research current frameworks and libraries.
- Identify platform and hardware assumptions.
- Compare architecture and technology options.
- Define core interfaces and data contracts.
- Produce architecture, dependency, security, testing, and roadmap documents.
- Record the proposed architecture and important decisions in the project documentation.
- Perform a self-review against the requirements, security boundaries, resource constraints, and test plan.
- Continue into Phase 1 and subsequent phases without waiting for routine approval, provided all work remains within the strict workspace boundary.

### Phase 1 — Foundation
- Establish repository structure and development tooling.
- Build minimal desktop shell/backend connection.
- Add configuration and logging.
- Add basic session and task state.
- Add initial automated tests and CI-ready commands.

### Phase 2 — LLM connectivity
- Implement provider adapters.
- Connect at least one local runtime.
- Add one hosted provider as an optional adapter.
- Implement streaming, errors, timeouts, and cancellation.
- Add capability registry and provider tests.

### Phase 3 — Assistant core
- Add conversation lifecycle and bounded orchestration.
- Implement simple-chat fast path.
- Add task state and progress.
- Add model routing with explainable decisions.
- Test tool-free and tool-assisted paths.

### Phase 4 — Security and permissions
- Implement deterministic permission manager.
- Add autonomy modes and approval UI.
- Add filesystem/network/process policies as applicable.
- Add audit logging and security tests.
- Do not expose powerful tools before this phase is sufficiently complete.

### Phase 5 — Tools, skills, and integrations
- Add a small set of useful tools.
- Add skill registry and lifecycle.
- Evaluate MCP and integrations.
- Add browser and desktop interaction incrementally.
- Verify every tool is permission-gated.

### Phase 6 — Memory and continuity
- Add structured local memory.
- Add selective memory extraction and retrieval.
- Add context summarization and task checkpoints.
- Add user inspection/edit/delete controls.
- Test persistence, retrieval, deletion, and model switching.

### Phase 7 — Personality and voice
- Add central personality settings.
- Add speech recognition and TTS.
- Implement streaming speech, interruption, and device handling.
- Measure real latency and resource use.

### Phase 8 — Optional cloud sync
- Research backend/auth/sync choices.
- Implement opt-in sync and device management.
- Add conflict handling, privacy controls, and security tests.
- Verify local-only mode remains fully functional.

### Phase 9 — Polish and distribution
- Improve onboarding, settings, accessibility, and diagnostics.
- Add packaging, updates, and crash recovery.
- Optimize resource use.
- Run complete regression and security suites.
- Document installation, configuration, backup, recovery, and troubleshooting.

Before moving from one phase to the next, run the relevant test suite and verify the phase's acceptance criteria. Do not carry known critical failures into later phases.

## 22. Engineering rules

- Use clear, typed interfaces and schemas.
- Keep functions and modules focused.
- Avoid unnecessary complexity and premature abstraction.
- Avoid giant files and tightly coupled modules.
- Keep secrets out of source control.
- Provide `.env.example` or equivalent configuration examples without real credentials.
- Validate all external inputs.
- Use structured logging with sensitive-data redaction.
- Handle errors explicitly.
- Use timeouts and cancellation for network and tool operations.
- Avoid unbounded loops, retries, and background tasks.
- Make state-changing operations auditable.
- Add migrations for persistent data schema changes.
- Keep dependencies documented and reasonably pinned.
- Use Git with logical commits.
- Do not overwrite or delete user data without explicit approval.
- Do not claim functionality that has not been implemented and verified.

## 23. Autonomous development expectations

Antigravity should be proactive and capable of completing substantial work without asking the owner to approve every minor choice.

You may autonomously:
- Inspect files and repository structure.
- Research libraries and compare alternatives.
- Create documentation and diagrams.
- Set up project scaffolding.
- Implement routine features within the approved architecture.
- Add tests and run them.
- Refactor when it improves clarity without changing intended behavior.
- Fix defects introduced by your changes.
- Make reversible engineering decisions and document them.

Ask the owner before:
- Destructive or irreversible operations.
- Deleting or overwriting existing user data.
- Enabling broad filesystem, microphone, camera, or network access.
- Sending private data to a cloud service.
- Incurring non-trivial paid API or infrastructure costs.
- Publishing, sending, purchasing, or submitting externally.
- Making a major architecture/product decision with meaningful long-term consequences.
- Proceeding when a genuinely essential requirement is unknown.

Do not ask for approval for every file creation, ordinary dependency installation, or routine implementation detail if it is within the agreed plan and environment. Explain significant decisions in concise summaries.

## 24. Documentation deliverables

During Phase 0, create and maintain:

- `docs/PRD.md` — product requirements and user-facing behavior.
- `docs/ARCHITECTURE.md` — architecture, components, boundaries, data flows, and key contracts.
- `docs/TECH_STACK.md` — selected stack and rationale.
- `docs/DEPENDENCY_DECISIONS.md` — researched dependencies, alternatives, licenses, and decisions.
- `docs/SECURITY.md` — threat model, permission model, privacy boundaries, and safeguards.
- `docs/ROADMAP.md` — phases, milestones, acceptance criteria, and known risks.
- `docs/TESTING.md` — testing strategy, commands, matrix, and reporting requirements.

Keep documentation aligned with implementation. Mark assumptions, decisions, open questions, and unverified capabilities explicitly.

## 25. Acceptance criteria for the overall project

The project should ultimately demonstrate:

- A usable desktop assistant interface.
- Local model connectivity and optional hosted providers.
- Provider/model switching without rewriting the assistant.
- A stable central personality configuration.
- Fast direct conversation for simple prompts.
- Bounded orchestration for tasks that need tools.
- Permission-enforced tool execution.
- Multiple autonomy modes with clear boundaries.
- Inspectable and controllable memory.
- Useful skills and integrations.
- Browser and desktop interaction with safeguards.
- Natural voice input/output with interruption.
- Optional cloud sync independent of inference provider.
- Resource-aware operation on modest hardware.
- Clear progress, status, and error reporting.
- Automated tests and documented verification.
- Local-only operation without mandatory paid services.

Do not mark the project complete based on a demo alone. Demonstrate the acceptance criteria and report any limitations.

## 26. First action — autonomous end-to-end execution

Run the project through **all phases**, from Phase 0 through Phase 9, without waiting for the owner to return for routine approvals.

1. Identify and verify the project root. Read `AGENTS.md` completely.
2. Inspect the workspace. Preserve existing files and user work; do not overwrite or delete anything unless it is clearly generated by this project and safe to replace.
3. Complete Phase 0 research, architecture, dependency evaluation, and documentation.
4. Self-review the architecture against this prompt. Record important decisions, assumptions, and trade-offs.
5. Continue through the implementation roadmap phase by phase.
6. Before each phase, define concrete acceptance criteria and relevant tests.
7. After each meaningful change, run the required unit, integration, regression, security, static-check, and build tests relevant to that change.
8. Fix failures caused by your changes and rerun the affected tests. Do not conceal failures or weaken tests to obtain a pass.
9. Keep all project changes and generated artifacts inside the project root.
10. Update documentation as the implementation evolves.
11. At the end of each phase, create a concise milestone report in the project folder and proceed to the next safe phase.
12. At the end, run the broadest practical test suite, produce a final status report, and document setup, launch, configuration, known limitations, and next steps.

Do not stop after Phase 0 for routine architecture approval. Use conservative, reversible assumptions where requirements are unclear and record them. Do not ask questions that can reasonably be handled by a safe provisional assumption.

**Pause only a specific action** if it would require paid services or non-trivial spend, external publication or communication, access to credentials or private data outside the project folder, machine-wide/system-level changes, broad host permissions, or a genuinely high-impact security/privacy decision. Do not perform that action. Record the blocker and continue with independent work that stays within the approved boundaries.

The project is not authorized to use real paid API keys or incur costs. Implement provider integrations so they can be configured later, and use mocks or local test servers for automated tests. Do not claim live provider functionality has been verified unless it has actually been tested with an authorized service.

The objective is to leave a working, tested, documented project in the Jarvis folder—not merely a plan or prototype. Be honest about incomplete features and limitations.