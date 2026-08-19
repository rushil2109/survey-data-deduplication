-include .env

PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
PYTHON_BIN := $(if $(wildcard $(VENV_PYTHON)),$(VENV_PYTHON),$(PYTHON))
INPUT ?= examples/responses.json

export PYTHONPATH := src

.PHONY: help setup install test mock-server run

help:
	@printf '%s\n' \
		'make setup         Create the virtual environment and install dependencies' \
		'make test          Run the test suite' \
		'make mock-server   Start the local mock API' \
		'make run           Deduplicate and upload INPUT (default: examples/responses.json)'

setup:
	@if [ -f .env ]; then \
		:; \
	else \
		cp .env.example .env; \
		printf '%s\n' 'Created .env from .env.example. Review it before running the API.'; \
	fi
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install -r requirements.txt

install: setup

test: setup
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(PYTHON_BIN) -m pytest -q

mock-server: setup
	set -a; . .env; set +a; $(PYTHON_BIN) -m mock_server

run: setup
	set -a; . .env; set +a; $(PYTHON_BIN) -m survey_deduplication.cli $(INPUT)