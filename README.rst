Python-eetlijst
===============

Unofficial Python API for interfacing with Eetlijst.nl, a Dutch website
used by students to manage dinner status and expenses.

|Build Status|

Current features include:

-  List all residents
-  Get name of the list
-  Get or set the noticeboard
-  Get or set the dinner status

Installation
------------

To install this module, run ``pip install python-eetlijst`` to install
from Pip. If you prefer to install the latest version from Github, use
``pip install git+https://github.com/basilfx/python-eetlijst``.

Examples
--------

Three examples are included in the ``examples/`` folder. The purpose is
to demonstrate some functionality.

dinner.py
~~~~~~~~~

Print or set the current dinner status, in a terminal window. Run it
with ``diner.py <username> <password> get|set``.

It shall print something similar to this, when getting the current
status:

::

    Dinner status for 2014-03-30. The deadline is 16:00:00, and has passed.

    In total, 4 people (including guests) will attend diner.

    Unknown1 | Unknown2 | Unknown3 | Unknown4 | Unknown5
       C     |  D + 2   |    X     |    X     |    ?

    X = No, C = Cook, D = Dinner, ? = Unknown

noticeboard.py
~~~~~~~~~~~~~~

View or change the current noticeboard. Run it with
``noticeboard.py <username> <password> get|set``.

session.py
~~~~~~~~~~

Given a session id, print the name of the Eetlijst list. Run it with
``session.py <session_id>``

Tests
-----

Currently, basic tests have been written. These tests only verify the
'scraping' functionality and correct sesision handling, by faking
responses. However, they do not test any submit functionality, since it
would require an active connection with Eetlijst.nl during the tests.

To run the tests, please clone this repository and run
``python setup.py test``.

Documentation
-------------

This is future work :-)

For now, please look at the source code, the tests and the examples.

License
-------

See the ``LICENSE`` file (GPLv3 license). You may change the code
freely, but any change must be made available to the public.

.. |Build Status| image:: https://travis-ci.org/basilfx/python-eetlijst.svg?branch=master
   :target: https://travis-ci.org/basilfx/python-eetlijst
