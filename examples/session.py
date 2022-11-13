import sys

import eetlijst


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stdout.write("Usage: %s <session_id>\n" % argv[0])
        return 0

    # Parse session id.
    session_id = argv[1].lower()

    # Create a client.
    try:
        client = eetlijst.Eetlijst(session_id=session_id, login=True)
    except eetlijst.LoginError:
        sys.stderr.write("Session id is probably expired or invalid.\n")
        return 1

    # Perform action.
    sys.stdout.write(
        "Session identifier belongs to list with name '%s'.\n" % client.get_name()
    )


# For example: `python session.py session_id`.
if __name__ == "__main__":
    sys.exit(main(sys.argv))
