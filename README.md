<div align="center">

# Veridict

### Your AI coding agent says it's done. **Veridict decides whether that's true.**

Veridict independently re-checks what an AI agent *claims* it did — and renders a verdict.
It doesn't trust the transcript. It re-runs the tests, looks at the disk, and asks git.

[![CI](https://github.com/venumittapalli576/veridict/actions/workflows/ci.yml/badge.svg)](https://github.com/venumittapalli576/veridict/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/lint-ruff-261230.svg)](https://github.com/astral-sh/ruff)

</div>

---

## The problem

AI coding agents have a habit of saying the work is done when it isn't. They write
**"✅ all tests pass"** while the suite has a syntax error. They report **"created `auth.py`"**
when the file only ever existed in their imagination. This isn't malice — they generate
"done!" language as part of their output pattern, whether or not reality agrees.

The numbers back it up:

- **96% of developers** don't fully trust AI-generated code — yet only **~48%** always verify it before committing. ([The New Stack](https://thenewstack.io/agentic-ai-verification-impact/))
- Agents routinely **claim tests pass when they don't**, and reference files that were never written. ([DEV Community](https://dev.to/moonrunnerkc/ai-coding-agents-lie-about-their-work-outcome-based-verification-catches-it-12b4))

As teams ship more autonomous agents, *checking their work* is quietly becoming its own
category. Veridict takes the minimal end of it: point it at any agent's summary and it tells
you, claim by claim, what actually holds up — no framework to adopt, no graders to write.

## What it does

Pipe an agent's summary into Veridict. It extracts every checkable claim, **independently
establishes ground truth**, and tells you — per claim — whether reality backs it up:

```text
$ veridict check examples/agent_transcript.md --path examples/demo_project

╭─────────────────────────────────────────────────────╮
│ VERIDICT  ·  Caught 2 false claims  ·  trust 50/100 │
╰─────────────────────────────────────────────────────╯
Claims vs. reality
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Verdict        ┃ Claim                            ┃ Evidence                                     ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ ✔ true         │ file_exists → calculator.py      │ file exists                                  │
│ ✔ true         │ file_exists → test_calculator.py │ file exists                                  │
│ ✘ FALSE        │ file_exists → utils.py           │ file does not exist                          │
│ ✘ FALSE        │ tests_pass                       │ exited 1                                     │
│ ? unverifiable │ build_passes                     │ set commands.build in .veridict.yaml         │
│ ? unverifiable │ no_errors                        │ claim is too vague to verify                 │
└────────────────┴──────────────────────────────────┴──────────────────────────────────────────────┘
2 verified · 2 false · 2 unverifiable
```

The agent said "all tests pass" and "created `utils.py`". Both were false — and Veridict's
exit code is non-zero, so it doubles as a **CI gate** or **pre-commit hook**.

The same report as a PR comment (`--md`) renders like this:

> ### ❌ Veridict — Caught 2 false claims  ·  trust **50/100**
>
> | Verdict | Claim | Evidence |
> | --- | --- | --- |
> | ✅ true | `file_exists → calculator.py` | file exists |
> | ✅ true | `file_exists → test_calculator.py` | file exists |
> | ❌ FALSE | `file_exists → utils.py` | file does not exist |
> | ❌ FALSE | `tests_pass` | exited 1 |
> | ⚠️ unverifiable | `build_passes` | set commands.build in .veridict.yaml |
> | ⚠️ unverifiable | `no_errors` | claim is too vague to verify without guessing |

## Install

```bash
# Straight from GitHub (works today)
pipx install git+https://github.com/venumittapalli576/veridict.git

# Or from source
git clone https://github.com/venumittapalli576/veridict.git
cd veridict && pip install -e ".[dev]"
```

Once published to PyPI: `pipx install veridict` (or zero-install with `uvx veridict ...`).

## Quickstart

```bash
# 1. Verify an agent's summary against your project
veridict check agent_summary.md

# ...or pipe it straight from your agent / clipboard
pbpaste | veridict check

# 2. Run the configured ground-truth checks (a CI / commit gate)
veridict run --strict

# 3. Scaffold a config (pre-filled with auto-detected commands)
veridict init
```

## How it works

Veridict keeps three ideas deliberately separate:

| Stage | Question | How |
| --- | --- | --- |
| **Claim** | What did the agent *say* it did? | Transparent pattern matching over the transcript (see [`claims.py`](src/veridict/claims.py)). Untrusted by definition. |
| **Ground truth** | What is *actually* true? | Re-run the test/build/lint command, hit the filesystem, ask `git status` (see [`verifiers.py`](src/veridict/verifiers.py)). |
| **Verdict** | Do they agree? | `true` ✔ · `false` ✘ · `unverifiable` ?, plus a 0–100 **trust score**. |

The guiding principle: **never guess.** If Veridict can't *prove* a claim, it reports
`unverifiable` rather than rubber-stamping it. The trust score is computed only from claims
that were actually decided — so it never flatters the agent.

## What Veridict can verify

| Claim the agent makes | Veridict's independent check |
| --- | --- |
| "all tests pass" / "suite is green" | Runs your configured `tests` command; checks the real exit code |
| "the build succeeds" / "compiles cleanly" | Runs `build` |
| "lint is clean" / "no warnings" | Runs `lint` |
| "mypy passes" / "no type errors" | Runs `typecheck` |
| "created `path/to/file.py`" | Checks the file exists on disk |
| "updated `config.py`" | Asks `git status` whether the file actually changed |
| "no errors" / vague success | Reported `unverifiable` — by design, not guessed |

## Configuration

Veridict works with zero config (it auto-detects pytest, `npm test`, `cargo`, `go`).
For full control, drop a `.veridict.yaml` in your repo (`veridict init` writes one for you):

```yaml
# How Veridict establishes GROUND TRUTH. Exit code 0 == passed.
commands:
  tests: "pytest -q"
  build: null
  lint: "ruff check ."
  typecheck: "mypy ."

# Checks that MUST pass for `veridict run` to exit 0.
required:
  - tests

timeout: 300
```

## Use it as a gate

**Pre-commit hook** — never commit on top of an agent's unverified "done":

```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: veridict
      name: veridict
      entry: veridict run --strict
      language: system
      pass_filenames: false
```

**GitHub Actions** — post the verdict on the PR:

```yaml
- run: pipx install veridict
- run: veridict run --md >> "$GITHUB_STEP_SUMMARY"
```

## Output formats

| Flag | Output | Good for |
| --- | --- | --- |
| *(none)* | Rich terminal report | humans |
| `--json` | Machine-readable JSON | scripts, dashboards |
| `--md` | Markdown tables | PR comments, job summaries |
| `--strict` | Treat `unverifiable` as failure too | paranoid CI |
| `--verbose` | Show captured output for failures | debugging |

## Why "Veridict"?

**veri**fy + ver**dict**. That's the whole job: independently verify, then deliver a verdict.

## Where it fits

"Check the outcome, not the transcript" is an idea that's (rightly) catching on fast — Veridict
is not the first to argue it. It deliberately occupies the *small* end of the space:

- **Agent-eval platforms** (DeepEval / Confident AI and friends) and **agent-testing frameworks**
  (e.g. Microsoft's [RAMPART](https://www.microsoft.com/en-us/security/blog/2026/05/20/introducing-rampart-and-clarity-open-source-tools-to-bring-safety-into-agent-development-workflow/))
  are powerful but heavier — you write graders/tests and wire them into your stack.
- **Agent orchestrators** increasingly cross-check claims, but only inside their own runtime.
- **Veridict** is the opposite: one dependency-light CLI you point at *any* agent's summary, after
  the fact, with zero setup. `pipx install`, pipe the text in, get a verdict. No framework, no lock-in.

The bet is simple: the *simplest possible* version — usable in ten seconds against any agent — is
the one people actually keep around.

## Roadmap

- [ ] Publish to PyPI
- [ ] First-class GitHub Action with automatic PR comments
- [ ] A structured claims format agents can emit directly (no extraction needed)
- [ ] More verifiers: "coverage didn't drop", "no secrets committed", "no new TODOs"
- [ ] Plugin API for custom verifiers

## Contributing

Issues and PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Veridict verifies itself
with `veridict run`, so it has to practice what it preaches.

## License

[MIT](LICENSE) © Venu Mittapalli
