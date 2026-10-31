# Jarvis — Security Architecture & Threat Model

## 1. Threat Model & Security Posture

As a desktop personal assistant with tool-calling capabilities, Jarvis operates in an environment containing untrusted data (web pages, user documents, tool results, third-party skills) and privileged local resources (workspace files, processes, environment variables).

### 1.1 Threat Vectors & Mitigations

| Threat | Description | Mitigation Strategy |
| :--- | :--- | :--- |
| **Indirect Prompt Injection** | Untrusted content (e.g. summarized web page or file) embeds instructions attempting to hijack execution or steal secrets. | Strict input separation: external data is tagged as untrusted content; prompt adapters encapsulate external data in isolated quote blocks; system policy overrides tool results. Deterministic permissions prevent execution even if model is deceived. |
| **Path Traversal & Symlink Escapes** | Tool attempts to read or write files outside the workspace root using relative paths (`../../`) or following symlinks. | Canonical path resolution (`pathlib.Path.resolve()`). Absolute check verifying the resolved path starts with the configured project root. Symlink escape detection rejects targets resolving outside. |
| **Unauthorized Action Execution** | Model attempts to invoke destructive actions (file deletion, arbitrary shell commands, external API calls) autonomously. | Deterministic Permission Manager gates all tool invocations. Model responses are parsed as proposals only; execution requires matching permission grant or explicit user approval. |
| **Data Exfiltration** | Cloud model routing or external network tool leaks sensitive user data or credentials. | Local-first routing default; privacy mode flags; automated redaction of API keys, tokens, and private paths in prompts, logs, and telemetry. |
| **Malicious Skill Manifests** | Untrusted skill introduces unauthorized shell execution or excessive permission requests. | Static schema validation on skill load; explicit permission declarations; denial of undeclared capabilities; user confirmation before enabling new skills. |

---

## 2. Autonomy Modes & Policy Engine

The Permission Engine enforces four distinct autonomy modes:

```
[User Request]
       │
       ▼
[Model Proposal / Tool Call]
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│              DETERMINISTIC PERMISSION ENGINE            │
│  - Is action read-only or mutating?                     │
│  - Is resource path within allowed workspace bounds?     │
│  - Does current Autonomy Mode permit action?            │
└───────────────────────────┬─────────────────────────────┘
                            │
          ┌─────────────────┴─────────────────┐
          │                                   │
      [Allowed]                       [Requires Approval]
          │                                   │
          ▼                                   ▼
 [Execute Tool Action]               [Prompt User in UI]
          │                                   │
          ▼                            [User Decides]
 [Log to Audit Trail]                 ┌───────┴───────┐
                                      ▼               ▼
                                 [Approved]      [Rejected]
                                      │               │
                                      ▼               ▼
                                  [Execute]     [Halt / Return]
```

### 2.1 Mode Definitions
1. **Plan Mode**:
   - Only allowlisted read operations permitted.
   - All write, delete, execute, and outbound network actions are strictly prohibited.
   - Produces safe plan proposals without side effects.
2. **Agent Decides Mode (Default Safe Operating Mode)**:
   - Read and search operations inside allowlisted paths execute autonomously.
   - Any state-changing mutation (file writes, deletes, external requests, process execution) halts and prompts the user for approval.
3. **Auto Mode**:
   - Pre-authorized actions within tight boundaries execute without interactive prompts.
   - Bounded by strict limits: max 10 steps per task, 60s timeout, restricted folder scope.
   - Irreversible actions (file deletion, financial, privilege escalation) always require approval regardless of Auto mode.
4. **Sandbox-Only Mode**:
   - Execution is restricted to an isolated scratch/temporary directory.
   - No network access, no host environment variable inspection, no external process spawning.

---

## 3. Path Validation & Boundary Enforcement

Every filesystem operation must be validated by the following deterministic algorithm:

```python
def validate_workspace_path(target_path: Path, workspace_root: Path) -> Path:
    # 1. Resolve canonical path (resolves symlinks and relative components)
    resolved_path = (workspace_root / target_path).resolve()
    resolved_root = workspace_root.resolve()
    
    # 2. Strict prefix check
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError:
        raise SecurityError(f"Path traversal detected: {target_path} resolves outside workspace {resolved_root}")
        
    return resolved_path
```

---

## 4. Secret Redaction & Audit Trail

- **Zero-Secret Logging**: Regex-based redaction filters (`Bearer [A-Za-z0-9_\-\.]*`, `sk-[A-Za-z0-9]{20,}`, password patterns) applied to all loggers and SSE streams.
- **Audit Log Table**: Append-only SQLite table storing:
  - `timestamp`: UTC ISO-8601
  - `action`: Tool name and action type
  - `resource`: Canonical resource identifier
  - `parameters`: Redacted input arguments
  - `decision`: Granted / Denied / User-Approved / User-Rejected
  - `operator`: Mode and triggering session ID
