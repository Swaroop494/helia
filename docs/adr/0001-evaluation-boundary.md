# ADR 0001: feedback isolation and execution boundary

Status: implemented.

Hold out mutants before any arm runs, share the exact split between arms of a seed, and
evaluate held-out mutants only after generation ends. The analyser rejects held-out
records. Prompts use only original source and sanitized failure categories/test IDs; no
mutant source, diff, traceback or rewritten assertion reaches the LLM.

Target imports, mutations and test execution occur in disposable Docker workers. Static
AST indexing on the controller does not import target code. Each pool slot gets a fresh
container so one generated test cannot persist changes into another job. Failed or missing
Docker infrastructure is an explicit error, never permission to execute on the host.

Cosmic Ray owns mutation semantics. Helia supplies selection, budget, feedback and
evaluation; no custom fallback mutator is silently substituted.

