"""The demo project's tests. These FAIL because of the bug in add()."""

from calculator import add, multiply


def main():
    assert add(2, 2) == 4, "add(2, 2) should be 4"
    assert multiply(3, 4) == 12, "multiply(3, 4) should be 12"
    print("all tests pass")


if __name__ == "__main__":
    main()
