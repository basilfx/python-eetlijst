#!/usr/bin/env python

import eetlijst
import sys


def main():
    if len(sys.argv) != 4:
        sys.stdout.write(
            "Usage: %s <username> <password> <get|set>\n" % sys.argv[0])
        return 0

    # Parse action
    action = sys.argv[3].lower()

    if action not in ["get", "set"]:
        sys.stdout.write("Invalid action: %s\n" % action)
        return 1

    # Create a client
    try:
        client = eetlijst.Eetlijst(
            username=sys.argv[1], password=sys.argv[2], login=True)
    except eetlijst.LoginError:
        sys.stderr.write("Username and/or password incorrect\n")
        return 1

    # Perform action
    if action == "get":
        get_action(client)
    elif action == "set":
        set_action(client)


def set_action(client):
    residents = client.get_residents()
    row = client.get_statuses(limit=1)[0]

    if row.has_deadline_passed():
        sys.stdout.write(
            "The deadline is %s, and has passed. Changing status is not "
            "possible today.\n" % row.deadline.time())
        return

    # Print all residents
    sys.stdout.write("Available residents:\n")

    for index, resident in enumerate(residents):
        sys.stdout.write("* %d: %s\n" % (index, resident))

    # Read number until it's a valid one
    while True:
        sys.stdout.write("Pick a number: ")
        sys.stdout.flush()

        index = sys.stdin.readline().strip()

        if len(index) == 0:
            continue

        # Try to parse it as valid integer
        try:
            index = int(index)
            break
        except ValueError:
            continue

    # Print mappings
    sys.stdout.write("Available values:\n")
    sys.stdout.write("* None: no status\n")
    sys.stdout.write("* -N: take dinner\n")
    sys.stdout.write("* 0: don't take dinner\n")
    sys.stdout.write("* +N: take dinner and cook\n")

    # Read value until it's a valid one
    while True:
        sys.stdout.write("Pick a value: ")
        sys.stdout.flush()

        value = sys.stdin.readline().strip().lower()

        if len(value) == 0:
            continue

        if value == "none":
            value = None
            break
        else:
            try:
                value = int(value)
                break
            except ValueError:
                continue

    # Set status
    client.set_status(index, value, timestamp=row.timestamp)
    sys.stdout.write("Value changed.\n")


def get_action(client):
    residents = client.get_residents()
    row = client.get_statuses(limit=1)[0]

    # Print a small header
    sys.stdout.write("Dinner status for %s. " % row.timestamp)

    if row.deadline:
        if row.has_deadline_passed():
            sys.stdout.write(
                "The deadline is %s, and has passed.\n\n" %
                row.deadline.time())
        else:
            sys.stdout.write("The deadline is %s, so there is %s left.\n\n" % (
                row.deadline.time(), row.time_left()))
    else:
        sys.stdout.write("There is no deadline.\n\n")

    # Print the status as a horizontal list
    names = []
    values = []

    for name, status in zip(residents, row.statuses):
        # Convert to meaningful representation
        if status.value is None:
            value = "?"
        elif status.value == 0:
            value = "X"
        elif status.value == 1:
            value = "C"
        elif status.value == -1:
            value = "D"
        elif status.value > 1:
            value = "C + %d" % (status.value - 1)
        elif status.value < -1:
            value = "D + %d" % (-1 * status.value - 1)

        # Add to rows
        width = max(len(name), len(value))

        names.append(name.center(width))
        values.append(value.center(width))

    # Print it all
    sys.stdout.write(
        "In total, %d people (including cooks and guests) will attend "
        "dinner.\n\n" % row.get_count())

    sys.stdout.write(" | ".join(names) + "\n")
    sys.stdout.write(" | ".join(values) + "\n\n")

    sys.stdout.write("X = No, C = Cook, D = Diner, ? = Unknown\n")

# E.g. `dinner.py username password get'
if __name__ == "__main__":
    sys.exit(main())
