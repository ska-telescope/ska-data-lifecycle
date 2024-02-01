include .make/base.mk
include .make/python.mk
include .make/oci.mk

DOCS_SPHINXOPTS = -W --keep-going
PYTHON_LINE_LENGTH = 99

docs-pre-build:
	poetry config virtualenvs.create false
	poetry install --only main,docs

.PHONY: docs-pre-build

DOCKER_COMPOSE := docker compose
POSTGREST_PID_FILE := .postgrest.pid

# We use GitlabCI services in CI so only use docker compose locally
python-pre-test:
	[[ -z $$GITLAB_CI ]] \
		&& $(MAKE) docker-compose-up \
		|| echo "Not starting docker-compose containers in CI"

	scripts/setup_services.sh $(POSTGREST_PID_FILE)

python-post-test:
	if [ -f $(POSTGREST_PID_FILE) ]; then \
		kill $$(cat $(POSTGREST_PID_FILE)); \
		if [ $$? -eq 0 ]; then \
			echo "postgREST process killed successfully"; \
			rm $(POSTGREST_PID_FILE); \
		else \
			echo "Failed to kill postgREST process"; \
		fi; \
	else \
		echo "$(POSTGREST_PID_FILE) not found, postgREST may not have been started"; \
	fi

	[[ -z "$$GITLAB_CI" ]] \
		&& $(MAKE) docker-compose-down \
		|| echo "Not stopping docker-compose containers in CI"


docker-compose-up:
	$(DOCKER_COMPOSE) --file docker/test-services.docker-compose.yml up --detach

docker-compose-down:
	$(DOCKER_COMPOSE) --file docker/test-services.docker-compose.yml down
