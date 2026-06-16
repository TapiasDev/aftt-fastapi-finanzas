import sys

from app.core.security import hash_password


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m app.scripts.hash_password <plain-password>")

    print(hash_password(sys.argv[1]))


if __name__ == "__main__":
    main()
