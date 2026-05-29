# Example: an AI agent's (overconfident) summary

This is the kind of message a coding agent leaves at the end of a task. Run it
through Veridict against the demo project to see which claims actually hold up:

```bash
veridict check examples/agent_transcript.md --path examples/demo_project
```

---

Done! Here's what I changed:

- I created `calculator.py` with `add`, `subtract`, and `multiply`.
- I added unit tests in `test_calculator.py` covering the core operations.
- I also created `utils.py` with a couple of shared helpers.

I ran the suite and **all tests pass** ✅. The build is green and everything
works with no errors. Ready to merge!
