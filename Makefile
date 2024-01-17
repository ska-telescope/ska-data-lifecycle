include .make/base.mk
include .make/python.mk
include .make/oci.mk

DOCS_SPHINXOPTS = -W --keep-going
PYTHON_LINE_LENGTH = 99

docs-pre-build:
	poetry config virtualenvs.create false
	poetry install --only main,docs

.PHONY: docs-pre-build

