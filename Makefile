DOCS_SPHINXOPTS = -W --keep-going
PYTHON_LINE_LENGTH = 99

KUBE_NAMESPACE ?= ska-dlm
HELM_RELEASE ?= test
HELM_TIMEOUT ?= 5m
HELM_VALUES ?=
TEST_INGRESS ?= http://$(shell minikube ip)

DOCKER_COMPOSE := docker compose
POSTGREST_PID_FILE := .postgrest.pid
RCLONE_PID_FILE := .rclone.pid
DLM_SM_PID_FILE := .dlmsm.pid

include .make/base.mk
include .make/helm.mk
include .make/python.mk
include .make/oci.mk
include .make/k8s.mk

# Make these available as environment variables
export KUBE_NAMESPACE TEST_INGRESS

.PHONY: docs-pre-build k8s-recreate-namespace \
	update-chart-dependencies install-dlm uninstall-dlm

docs-pre-build: ## setup the document build environment.
	poetry config virtualenvs.create false
	poetry install --only main,docs

# We use GitlabCI services in CI so only use docker compose locally
python-pre-test:  ## setup the services for python-test
	[[ -z $$GITLAB_CI ]] \
		&& $(MAKE) docker-compose-up \
		|| echo "Not starting docker-compose containers in CI"

	scripts/setup_services.sh $(POSTGREST_PID_FILE) $(RCLONE_PID_FILE) $(DLM_SM_PID_FILE)

python-post-test:  ## teardown the services after python-test
	scripts/teardown_services.sh $(POSTGREST_PID_FILE) $(RCLONE_PID_FILE) $(DLM_SM_PID_FILE)

	[[ -z "$$GITLAB_CI" ]] \
		&& $(MAKE) docker-compose-down \
		|| echo "Not stopping docker-compose containers in CI"

kill-test-processes:  ## kill left-over process from testing
	scripts/kill_test_processes.sh

docker-compose-up:  ## startup the docker services
	$(DOCKER_COMPOSE) --file docker/test-services.docker-compose.yml up --detach

docker-compose-down: ## teardown the docker services
	$(DOCKER_COMPOSE) --file docker/test-services.docker-compose.yml down

k8s-recreate-namespace: k8s-delete-namespace k8s-namespace

update-chart-dependencies:
	helm dependency update charts/ska-dlm

install-and-init-dlm: HELM_VALUES = resources/initialised-dlm.yaml
install-and-init-dlm: install-dlm

install-dlm:
	helm install -n $(KUBE_NAMESPACE) $(HELM_RELEASE) charts/ska-dlm $(foreach file,$(HELM_VALUES),--values $(file)) --wait --timeout=$(HELM_TIMEOUT)

uninstall-dlm:
	helm uninstall -n $(KUBE_NAMESPACE) $(HELM_RELEASE) --wait