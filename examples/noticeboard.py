import sys

import eetlijst


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        sys.stdout.write("Usage: %s <username> <password> <get|set>\n" % argv[0])
        return 0

    # Parse action.
    action = argv[3].lower()

    if action not in ["get", "set"]:
        sys.stdout.write("Invalid action: %s\n" % action)
        return 1

    # Create a client.
    try:
        client = eetlijst.Eetlijst(username=argv[1], password=argv[2], login=True)
    except eetlijst.LoginError:
        sys.stderr.write("Username and/or password incorrect.\n")
        return 1

    # Perform action.
    if action == "get":
        get_action(client)
    else:
        set_action(client)


def get_action(client: eetlijst.Eetlijst) -> None:
    sys.stdout.write("%s\n" % client.get_noticeboard())


def set_action(client: eetlijst.Eetlijst) -> None:
    sys.stdout.write("Type a new noticeboard message: ")
    sys.stdout.flush()

    message = sys.stdin.readline().strip()

    if len(message) == 0:
        sys.stdout.write("Empty message. Noticeboard not updated.\n")
        return 1

    client.set_noticeboard(message)
    sys.stdout.write("Notice board updated\n")


# For example: `python noticeboard.py get username password`.
if __name__ == "__main__":
    sys.exit(main(sys.argv))
