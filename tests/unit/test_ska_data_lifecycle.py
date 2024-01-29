#!/usr/bin/env python

"""Tests for `ska_data_lifecycle` package."""

import logging
from datetime import timedelta

import inflect

from ska_dlm import dlm_ingest, dlm_request

LOG = logging.getLogger("data-lifecycle-test")
LOG.setLevel(logging.DEBUG)


def test_example():
    """Placeholder test."""
    value = True
    assert value


def test_ingest():
    """Test data_item init."""
    qry = inflect.engine()
    success = True
    for i in range(1, 51, 1):
        ordinal = qry.number_to_words(qry.ordinal(i))
        uid = dlm_ingest.init_data_item(f"this/is/the/{ordinal}/test/item")
        if len(uid) != 36:
            success = False
    assert success


def test_query_expired_empty():
    """Test the query expired returning an empty set."""
    result = dlm_request.query_expired()
    success = not result
    assert success


def test_query_expired():
    """Test the query expired returning records."""
    offset = timedelta(days=1)
    result = dlm_request.query_expired(offset)
    success = len(result) > 0
    assert success
