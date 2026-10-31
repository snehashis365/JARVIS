# First Antigravity Handoff Message — Autonomous Run

Read `Prompt.md` and `AGENTS.md` in full before doing any work.

I am authorizing you to run the project through **all phases**, from Phase 0 through Phase 9, autonomously. Do not stop after Phase 0 to wait for my review. I will review the completed work and reports when I return.

## Non-negotiable boundary: the Jarvis project folder only

1. First identify and verify the absolute path of this Jarvis project folder.
2. All project file reads, writes, edits, moves, deletions, generated files, virtual environments, dependencies, caches, databases, logs, builds, and test artifacts must stay inside this folder.
3. Before every write, move, or delete, resolve the target path and verify it remains inside the project root. Reject path traversal and symlink escapes.
4. Do not modify, delete, rename, or inspect unrelated files outside this folder.
5. Do not install global packages. Keep dependencies and environments local to the project wherever practical.
6. Do not use administrator/root privileges or `sudo`. Do not modify OS settings, PATH, shell profiles, registry, startup entries, system services, firewall, drivers, or machine-wide configuration.
7. Do not access personal credentials, browser profiles, password stores, SSH keys, unrelated repositories, or private folders.
8. Do not upload project files, source code, logs, prompts, memory, or personal data to external services.
9. Do not publish, deploy, send messages, create accounts, make purchases, or incur paid API/cloud costs.
10. Do not enable host microphone, camera, screen capture, broad filesystem access, or remote-control capabilities during development.
11. You may use the network for documentation research and downloading project dependencies when needed. Keep all downloaded project artifacts inside this folder.
12. A prompt is not an OS sandbox. Use actual workspace restrictions if available and do not claim isolation that is not enforced.

## Execution instructions

- Complete Phase 0 research, architecture, and documentation first.
- Self-review the architecture and record assumptions, decisions, trade-offs, security boundaries, and limitations.
- Continue through every subsequent implementation phase without waiting for routine approval.
- Use mature, maintained libraries where appropriate; do not reinvent established infrastructure without a documented reason.
- Make conservative, reversible decisions. Do not ask me questions for routine choices that can be handled safely.
- Implement in coherent increments, not one giant code dump.
- Add tests with features. After every meaningful change, run relevant unit, integration, regression, security, static-check, and build tests.
- Follow the required cycle: **Implement → Test → Diagnose → Fix → Retest → Document → Proceed.**
- Do not hide failures, weaken tests to make them pass, or claim tests passed unless they were actually run.
- Use mocks and local test servers for provider tests. Do not require paid APIs for routine tests.
- Build provider integrations so I can configure real credentials later, but do not request, search for, or use my credentials.
- Keep `docs/` current and create a milestone report for each phase.
- If an action requires paid spend, credentials, external side effects, host-wide changes, access outside the project folder, or a major security/privacy decision, do not perform that action. Document the blocker and continue with independent safe work.
- Do not leave the application in a knowingly broken state just to reach the next phase. If blocked, stabilize the current state, document the unfinished work, and continue only where dependencies allow.

## Final deliverables

When all safe work is complete, leave the Jarvis project folder with:
- The implemented application and source code.
- Setup and launch instructions.
- Configuration examples without real secrets.
- All architecture, dependency, security, roadmap, and testing documentation.
- Automated tests and clear commands to run them.
- Phase-by-phase milestone reports.
- A final report stating what works, what was tested, what failed, what remains incomplete, and any manual steps I need to take.

The goal is to leave a working, tested, documented application—not just a plan or a demo. Be accurate about limitations. Proceed autonomously within the boundaries above.