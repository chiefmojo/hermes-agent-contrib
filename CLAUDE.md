# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Git

When Claude Code makes commits on behalf of Erick, always pass `--author="Erick <chiefmojo@chiefmojo.com>"`. Do not change the local git config — the repo's default author should be preserved for her own commits.

## Development Setup

```bash
uv venv venv --python 3.11
source venv/bin/activate           # or: source .venv/bin/activate
uv pip install -e ".[all,dev]"
```

For browser tools and WhatsApp bridge: `npm install` (Node.js 20+ required).

## Running Tests

**Always use the wrapper — never call `pytest` directly:**

```bash
scripts/run_tests.sh                                    # full suite (CI parity)
scripts/run_tests.sh tests/gateway/                     # one directory
scripts/run_tests.sh tests/agent/test_foo.py::test_x    # single test
scripts/run_tests.sh -v --tb=long                       # pass-through pytest flags
```

The wrapper enforces: credentials unset, TZ=UTC, LANG=C.UTF-8, PYTHONHASHSEED=0, 4 xdist workers. Direct `pytest` diverges from CI in ways that cause local-passes/CI-fails.

## TUI Development

```bash
cd ui-tui
npm install        # first time
npm run dev        # watch mode
npm run type-check # tsc --noEmit
npm run lint       # eslint
npm test           # vitest
```

## Architecture

### Core File Dependency Chain

```
tools/registry.py  (no deps — imported by all tool files)
       ↑
tools/*.py  (each calls registry.register() at import time)
       ↑
model_tools.py  (imports tools/registry + triggers tool discovery)
       ↑
run_agent.py, cli.py, batch_runner.py
```

### Key Entry Points

| File | Role |
|------|------|
| `run_agent.py` | `AIAgent` class — thin coordinator; core logic in `agent/` submodules (~4k LOC) |
| `model_tools.py` | Tool orchestration, `discover_builtin_tools()`, `handle_function_call()` |
| `toolsets.py` | Toolset definitions; `_HERMES_CORE_TOOLS` is the default platform bundle |
| `cli.py` | `HermesCLI` — interactive CLI with prompt_toolkit (~15k LOC) |
| `hermes_state.py` | `SessionDB` — SQLite session store with FTS5 full-text search |
| `hermes_constants.py` | `get_hermes_home()` / `display_hermes_home()` — profile-aware paths |
| `agent/prompt_builder.py` | System prompt assembly (identity, skills, context files, memory) |
| `agent/context_compressor.py` | Auto-summarization when approaching context limits |
| `agent/background_review.py` | Background memory/skill review prompts (`_MEMORY_REVIEW_PROMPT`, etc.) |
| `hermes_cli/commands.py` | Central `COMMAND_REGISTRY` — all slash commands, autocomplete, menus |
| `gateway/run.py` | `GatewayRunner` — platform lifecycle, message routing, cron delivery (~18.7k LOC) |
| `gateway/stream_consumer.py` | Streaming output handler — `finalize` flag controls per-adapter post-processing |
| `plugins/platforms/discord/adapter.py` | Discord platform adapter (messaging, voice, TTS, table formatting) |
| `cron/scheduler.py` | Cron job runner — creates `AIAgent` instances for scheduled jobs |

### Agent Loop

`AIAgent.run_conversation()` is synchronous. The loop calls the LLM, dispatches tool calls via `handle_function_call()`, appends tool results, and repeats until the model returns a text-only response or `max_iterations` is hit. Messages follow OpenAI format (`role: system/user/assistant/tool`).

### TUI Process Model

```
hermes --tui
  └─ Node (Ink)  ──stdio newline-delimited JSON-RPC──  Python (tui_gateway)
       │                                                    └─ AIAgent + tools + sessions
       └─ renders transcript, composer, approvals, activity
```

TypeScript owns the screen. Python owns sessions, model calls, and slash command logic.

**Do not re-implement the primary chat experience in React.** Extend Ink (`ui-tui/`) — anything added there appears in the web dashboard automatically.

## Adding Tools

Built-in tools require changes in exactly **2 files**:

1. **Create `tools/your_tool.py`** — call `registry.register()` at module level.
2. **Add to `toolsets.py`** — either `_HERMES_CORE_TOOLS` or a named toolset. Auto-discovery imports the file, but the tool is only exposed to an agent if its name is in a toolset.

All tool handlers must return a JSON string. Use `get_hermes_home()` for any persistent state paths — never `Path.home() / ".hermes"`.

For local/non-core tools, use the plugin route instead: `~/.hermes/plugins/<name>/plugin.yaml` + `__init__.py` with `ctx.register_tool(...)`.

## Adding Slash Commands

All slash commands live in `COMMAND_REGISTRY` in `hermes_cli/commands.py`. Adding a `CommandDef` there automatically updates CLI dispatch, gateway dispatch, Telegram bot menu, Slack routing, autocomplete, and help text. Handler goes in `HermesCLI.process_command()` (CLI) and `gateway/run.py` (gateway).

## Configuration

**Three distinct config loaders — know which one you're in:**

| Loader | Used by |
|--------|---------|
| `load_cli_config()` in `cli.py` | Interactive CLI mode |
| `load_config()` in `hermes_cli/config.py` | `hermes tools`, `hermes setup`, subcommands |
| Direct YAML load | Gateway runtime (`gateway/run.py` + `gateway/config.py`) |

Adding a new config key: add it to `DEFAULT_CONFIG` in `hermes_cli/config.py`. Bump `_config_version` only when migrating/renaming existing keys — adding a new key to an existing section doesn't require a bump.

Secrets (API keys, tokens, passwords) go in `~/.hermes/.env`. Non-secret settings go in `config.yaml`.

## Plugins

**Plugins must not modify core files** (`run_agent.py`, `cli.py`, `gateway/run.py`, `hermes_cli/main.py`). If a plugin needs a capability the framework doesn't expose, expand the generic plugin surface (new hook or `ctx` method).

Plugin discovery runs as a side effect of importing `model_tools.py`. Code paths that read plugin state without going through `model_tools.py` must call `discover_plugins()` explicitly (it's idempotent).

Model-provider plugins (`plugins/model-providers/<name>/`) use a separate lazy discovery system — **not** the general `PluginManager`.

## Skills

- `skills/` — built-in skills, active by default, broadly useful
- `optional-skills/` — official but niche/heavy-dep skills; discoverable via `hermes skills browse`, not active by default

Skills should be preferred over new tools for any capability expressible as instructions + shell commands + existing tools.

## Test Invariants

Write invariant tests that assert relationships, not snapshot tests that encode current values. Snapshot tests break on every routine update (model names, config versions, list counts):

```python
# Bad
assert "gemini-2.5-pro" in _PROVIDER_MODELS["gemini"]
# Good
assert "gemini" in _PROVIDER_MODELS
assert len(_PROVIDER_MODELS["gemini"]) >= 1
```

## User Config Paths

| Path | Purpose |
|------|---------|
| `~/.hermes/config.yaml` | Runtime settings |
| `~/.hermes/.env` | API keys and secrets only |
| `~/.hermes/skills/` | All active skills |
| `~/.hermes/memories/` | Persistent memory (MEMORY.md, USER.md) |
| `~/.hermes/state.db` | SQLite session database |
| `~/.hermes/logs/` | `agent.log`, `errors.log`, `gateway.log` |

## companion-stable Branch Workflow

Companion patches (Faye-specific customizations) live on topic branches `port/<name>` off `companion-stable` on `chiefmojo/hermes-agent`. PRs target `companion-stable`.

- `companion-stable` moves independently — verify merge base before assuming your branch's delta matches expectations
- Source commits for porting come from `hermes-patches-faye`
- After cherry-picking with conflict resolution (`git add` + commit), the working tree may retain conflict markers — `git checkout HEAD -- <file>` cleans them without affecting the commit

### v0.14.0 Structural Changes (relevant for porting patches)

- Discord adapter: `plugins/platforms/discord/adapter.py` (was `gateway/platforms/discord.py`)
- Review prompts (`_MEMORY_REVIEW_PROMPT`, etc.): `agent/background_review.py` (was `run_agent.py`)
- Tests importing from old paths need updating when porting patches

### cron skip_memory Sentinel

In `cron/scheduler.py`, `skip_memory` is gated on `"memory_search"` (not `"memory"`) in the job's `enabled_toolsets`. This is intentional — `"memory_search"` never appears in default platform toolsets, so all default cron jobs get `skip_memory=True`. Only jobs that explicitly include `"memory_search"` opt in to memory access.

## Nix Build

`nix/web.nix` and `nix/tui.nix` contain `fetchNpmDeps` hashes that must match `web/package-lock.json` and `ui-tui/package-lock.json` respectively.

When CI "nix (ubuntu-latest)" fails with "stale npm lockfile hash":
1. Open the failed run → "Diagnose npm lockfile hashes" step
2. Find `NEW_HASH=sha256-...` for the stale entry
3. Update the `hash =` field in `nix/web.nix` or `nix/tui.nix`

Nix is not installed locally — always get the correct hash from CI logs.
