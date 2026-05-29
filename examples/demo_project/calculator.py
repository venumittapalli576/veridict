"""A tiny calculator with a deliberately planted bug (for the Veridict demo)."""


def add(a, b):
    # BUG: this should be `a + b`. The agent claimed the tests pass anyway.
    return a - b


def subtract(a, b):
    return a - b


def multiply(a, b):
    return a * b
