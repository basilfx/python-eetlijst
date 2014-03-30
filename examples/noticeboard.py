#!/usr/bin/env python

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../"))

import eetlijst
import sys

def main():
    if len(sys.argv) != 4:
        sys.stdout.write("Usage: %s <get|set> <username> <password>\n" % sys.argv[0])
        return 0

    # Parse action
    action = sys.argv[3].lower()

    if action not in ["get", "set"]:
        sys.stdout.write("Invalid action: %s\n" % action)
        return 1

    # Create a client
    try:
        client = eetlijst.Eetlijst(username=sys.argv[1], password=sys.argv[2], login=True)
    except eetlijst.LoginError:
        sys.stderr.write("Username and/or password incorrect\n")
        return 1

    # Perform action
    if action == "get":
        get_action(client)
    else:
        set_action(client)

    return 0

def get_action(client):
    sys.stdout.write("%s\n" % client.get_noticeboard())

def set_action(client):
    sys.stdout.write("Type a new noticeboard message: ")
    sys.stdout.flush()

    message = sys.stdin.readline().strip()

    if len(message) == 0:
        sys.stdout.write("Empty message. Noticeboard not changed\n")
        return 1

    client.set_noticeboard(message)
    sys.stdout.write("Notice board updated\n")

# E.g. `noticeboard.py get username password'
if __name__ == "__main__":
    sys.exit(main())