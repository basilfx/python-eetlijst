#!/usr/bin/env python

import eetlijst
import sys


def main():
    if len(sys.argv) != 2:
        sys.stdout.write("Usage: %s <session_id>\n" % sys.argv[0])
        return 0

    # Parse session id
    session_id = sys.argv[1].lower()

    # Create a client
    try:
        client = eetlijst.Eetlijst(session_id=session_id, login=True)
    except eetlijst.LoginError:
        sys.stderr.write("Session id is probably expired or invalid.\n")
        return 1

    # Perform action
    sys.stdout.write(
        "Session id belongs to list with name '%s'.\n" % client.get_name())

# E.g. `session.py session_id'
if __name__ == "__main__":
    sys.exit(main())
