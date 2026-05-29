# Contributing to Veridict

Thanks for your interest! Veridict is small, focused, and easy to hack on.

## Development setup

```bash
git clone https://github.com/venumittapalli576/veridict.git
cd veridict
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Checks

```bash
ruff check .     # lint
pytest -q        # tests
veridict run     # dogfood: Veridict verifying itself
```

All three run in CI on every PR.

## The one rule: never guess

Veridict's value is that it does not flatter the agent. When you add a verifier or a
claim pattern, it must only return `true`/`false` when it can **prove** the answer. If
something is ambiguous, return `unverifiable` — that honesty is the whole product.

## Where things live

| File | Responsibility |
| --- | --- |
| [`claims.py`](src/veridict/claims.py) | Extract claims from a transcript (add patterns here) |
| [`verifiers.py`](src/veridict/verifiers.py) | Establish ground truth (add verifiers here) |
| [`engine.py`](src/veridict/engine.py) | Wire claims + verifiers into a report |
| [`report.py`](src/veridict/report.py) | Terminal / JSON / Markdown rendering |
| [`models.py`](src/veridict/models.py) | Shared dataclasses + the trust-score logic |

## Adding a claim type

1. Add the enum value in `models.py` (`ClaimType`).
2. Add detection pattern(s) in `claims.py`.
3. Add a verifier branch in `verifiers.py` (`verify_claim`).
4. Add tests in `tests/`.

Please include tests with every change — Veridict, of all projects, should not ship
unverified work.
