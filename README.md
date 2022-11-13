# Python-eetlijst
Unofficial Python API for interfacing with Eetlijst.nl, a Dutch website used by
students to manage dinner status and expenses.

[![Linting](https://github.com/basilfx/python-eetlijst/actions/workflows/lint.yml/badge.svg)](https://github.com/basilfx/python-eetlijst/actions/workflows/lint.yml)
[![Testing](https://github.com/basilfx/python-eetlijst/actions/workflows/test.yml/badge.svg)](https://github.com/basilfx/python-eetlijst/actions/workflows/test.yml)
[![PyPI version](https://badge.fury.io/py/python-eetlijst.svg)](https://badge.fury.io/py/python-eetlijst)

Current features include:

* List all residents
* Get the name of the list
* Get or set the noticeboard
* Get or set the dinner status

## Installation
To install this module, run `pip install python-eetlijst` to install from Pip.
If you prefer to install the latest version from Github, use
`pip install git+https://github.com/basilfx/python-eetlijst`.

## Examples
Three examples are included in the `examples/` folder. The purpose is to
demonstrate some functionality.

### dinner.py
Print or set the current dinner status, in a terminal window. Run it with
`python dinner.py <username> <password> get|set`.

It shall print something similar to this, when getting the current status:

```
Dinner status for 2014-03-30. The deadline is 16:00:00, and has passed.

In total, 4 people (including guests) will attend diner.

Unknown1 | Unknown2 | Unknown3 | Unknown4 | Unknown5
   C     |  D + 2   |    X     |    X     |    ?

X = No, C = Cook, D = Dinner, ? = Unknown
```

### noticeboard.py
View or change the current noticeboard. Run it with
`python noticeboard.py <username> <password> get|set`.

### session.py
Given a session id, print the name of the Eetlijst list. Run it with
`python session.py <session_id>`

## Contributing
See the [`CONTRIBUTING.md`](CONTRIBUTING.md) file.

## Tests
Currently, a minimal set of tests have been written. These tests only verify
the 'scraping' functionality and correct sesision handling, by faking
responses. However, they do not test any submit functionality, since it would
require an active connection with Eetlijst.nl during the tests.

To run the tests, please clone this repository and run `poetry run pytest`.

## Documentation
This is future work :-)

For now, please look at the source code, the tests and the examples.

## License
See the [`LICENSE.md`](LICENSE.md) file (GPLv3 license). You may change the
code freely, but any change must be made available to the public.

## Disclaimer
Use this library at your own risk. I cannot be held responsible for any
damages.

This page and its content is not affiliated with Eetlijst.nl.
