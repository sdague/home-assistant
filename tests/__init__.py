"""Tests for Home Assistant."""

# By default any tests running the fake home assistant only run at
# INFO mode, and don't include timestamps. This makes it hard to see
# what is going on in travis-ci failures. Make the log format more
# like real home assistant, and make the default the DEBUG level.

import logging

logging.basicConfig(level=logging.DEBUG)
