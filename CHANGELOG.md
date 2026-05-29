# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.1.0]: https://github.com/venumittapalli576/veridict/releases/tag/v0.1.0
