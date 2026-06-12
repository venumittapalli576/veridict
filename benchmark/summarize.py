"""Aggregate benchmark/results/runs.jsonl into a Markdown summary.

Usage: python benchmark/summarize.py [path/to/runs.jsonl]
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

DEFAULT = Path(__file__).resolve().parent / "results" / "runs.jsonl"


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    runs = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]

    by_model: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    false_examples: list[str] = []

    for run in runs:
        m = by_model[run["model"]]
        m["runs"] += 1
        report = run.get("report")
        if not report:
            m["no_summary"] += 1
            continue
        s = report["summary"]
        m["claims"] += s["verified"] + s["false"] + s["unverifiable"]
        m["true"] += s["verified"]
        m["false"] += s["false"]
        m["unverifiable"] += s["unverifiable"]
        if s["false"]:
            m["runs_with_false"] += 1
            for claim in report["claims"]:
                if claim["verdict"] == "false":
                    false_examples.append(
                        f"- **{run['model']} / {run['task']}** claimed `{claim['type']}"
                        + (f" → {claim['target']}`" if claim["target"] else "`")
                        + f' ("{claim["text"][:90]}…") — {claim["evidence"]["detail"]}'
                    )

    total_runs = sum(m["runs"] for m in by_model.values())
    total_false_runs = sum(m["runs_with_false"] for m in by_model.values())
    print(f"**{total_runs} runs** · {total_false_runs} summaries contained at least one false claim\n")
    print("| Model | Runs | Claims made | True | False | Unverifiable | Runs w/ false claim |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for model, m in sorted(by_model.items()):
        print(
            f"| {model} | {m['runs']} | {m['claims']} | {m['true']} | {m['false']} "
            f"| {m['unverifiable']} | {m['runs_with_false']}/{m['runs']} |"
        )
    if false_examples:
        print("\n### False claims caught\n")
        print("\n".join(false_examples))


if __name__ == "__main__":
    main()
