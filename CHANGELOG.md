# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] — 2026-06-12

### Fixed
- **A leaked credential can no longer exit 0.** An enabled `no_secrets` check
  now always gates `veridict run` (and therefore the GitHub Action), even when
  not listed under `required:`. Opting out means disabling the check.
- **Claim extractor: method calls are not filenames.** An agent describing a
  code edit (`x.split('=')`) was extracted as a `file_modified` claim about a
  file named `x.split` — the only false verdict in the benchmark's first
  sweep was Veridict's own bug, not an agent's lie.

### Added
- `benchmark/` — an agent-agnostic harness that fact-checks coding-agent
  summaries with Veridict, plus the first published sweep: 15 runs × 3 Claude
  models, 25 claims, 0 false. See `benchmark/README.md` for the two findings
  that mattered more than the headline.
- GitHub Action: `pin-config` input (default on) takes `.veridict.yaml` from
  the diff base, so a PR can't weaken its own verification.

## [0.2.0] — 2026-06-11

The "make them prove it" release: verify AI-agent PRs in CI, and catch the two
scariest things an agent can quietly add — credentials and unfinished work.

### Added
- **First-class GitHub Action** (`action.yml`): three lines of YAML re-run your
  checks on every PR, scan everything the PR added, post a sticky comment with
  the verdict, and fail the job on false claims. Outputs `trust-score`,
  `exit-code`, and report paths.
- **`no_secrets` diff scanner** (on by default in `veridict run`): flags
  secret-shaped values in *added* lines — AWS/GitHub/OpenAI/Anthropic/Slack/
  Stripe/Google key shapes, private key blocks, and hardcoded credentials —
  with every finding masked so the report never re-leaks a value. Claims like
  "no secrets were committed" are now verifiable.
- **`no_new_todos` diff scanner**: flags newly introduced `TODO`/`FIXME`/
  `HACK`/`XXX` markers; verifies claims like "removed all the TODOs".
- **`--diff-base REF`** on `check` and `run`: scan everything added since a
  ref (e.g. `origin/main`), not just pending changes — this is how the Action
  scans a whole PR. Falls back to a two-dot diff when shallow CI clones have
  no merge-base.
- **`--json-file PATH`**: write the JSON report to a file alongside any stdout
  format, so CI gets Markdown and the trust score from a single run.
- **`checks:` config section** to enable/disable the built-in scanners; they
  can also be listed in `required:`.
- README hero image generated from real output (`scripts/make_demo_svg.py`).

### Changed
- `veridict run` now includes the enabled diff scanners alongside command checks.
- This repo's own PRs are verified by its own action (dogfooding workflow).

## [0.1.0] — 2026-05-29

Initial release.

### Added
- `veridict check` — extract claims from an AI agent's summary and verify each
  against reality (tests, build, lint, typecheck, file existence, git changes).
- `veridict run` — run configured ground-truth checks as a CI / pre-commit gate.
- `veridict init` — scaffold a `.veridict.yaml`, pre-filled with auto-detected commands.
- Zero-config auto-detection for pytest, `npm test`, Cargo, and Go projects.
- A 0–100 **trust score** plus terminal, `--json`, and `--md` output formats.
- Non-zero exit code when a claim is false or a required check fails.

[0.2.1]: https://github.com/venumittapalli576/veridict/releases/tag/v0.2.1
[0.2.0]: https://github.com/venumittapalli576/veridict/releases/tag/v0.2.0
[0.1.0]: https://github.com/venumittapalli576/veridict/releases/tag/v0.1.0
