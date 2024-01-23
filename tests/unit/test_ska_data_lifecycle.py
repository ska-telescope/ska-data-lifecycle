#!/usr/bin/env python

"""Tests for `ska_data_lifecycle` package."""

import logging
import inflect
from ska_dlm import dlm_ingest

LOG = logging.getLogger("data-lifecycle-test")
LOG.setLevel(logging.DEBUG)


def test_example():
    """Placeholder test."""
    value = True
    assert value


def test_ingest():
    """Test data_item init"""
    q = inflect.engine()
    success = True
    for i in range(1, 51, 1):
        ordinal = q.number_to_words(q.ordinal(i))
        uid = dlm_ingest.init_data_item(f"this/is/the/{ordinal}/test/item")
        if len(uid) != 36:
            success = False
    assert success
