# Contributing Guidelines

## Running your changes

If you've made changes to rebase-helper and want to see their behavior on your local Linux
system, then run:

    $ pip3 install --user --editable .

## Running tests

You need the following packages in order to run the tests:

    $ sudo yum install tox python3-pytest

To run a large test suite use the following command:

    $ make test

Or to run an individual test use `pytest` command with an individual test python file:

    $ pytest rebasehelper/tests/test_specfile.py
