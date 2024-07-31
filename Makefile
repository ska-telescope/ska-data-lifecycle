DOCS_SPHINXOPTS = -W --keep-going
PYTHON_LINE_LENGTH = 99

K8S_CHART = ska-dlm
KUBE_NAMESPACE ?= ska-dlm
HELM_RELEASE ?= test
HELM_TIMEOUT ?= 5m
HELM_VALUES ?= resources/initialised-dlm.yaml
K8S_CHART_PARAMS ?= $(foreach file,$(HELM_VALUES),--values $(file)) --wait --timeout=$(HELM_TIMEOUT)

include .make/base.mk
include .make/helm.mk
include .make/python.mk
include .make/oci.mk
include .make/k8s.mk

# MacOS Arm64 ingress has issues. Workaround is to run with
# `minikube tunnel` and connect via localhost
# See https://github.com/kubernetes/minikube/issues/13510
ifeq ($(shell uname -m), arm64)
	TEST_INGRESS ?= http://localhost
else
	TEST_INGRESS ?= http://$(shell minikube ip)
endif

# Make these available as environment variables
export KUBE_NAMESPACE TEST_INGRESS

.PHONY: docs-pre-build k8s-recreate-namespace k8s-do-test

docs-pre-build: ## setup the document build environment.
	poetry install --only main,docs

python-pre-test:
	docker compose --file tests/services.docker-compose.yaml -p dlm-test-services up --detach
python-post-test:
	docker compose --file tests/services.docker-compose.yaml -p dlm-test-services down

docker-test: docker-pre-test docker-do-test docker-post-test
docker-pre-test:
	docker compose -f tests/testrunner.docker-compose.yaml build
docker-do-test:
	docker compose --file tests/testrunner.docker-compose.yaml run dlm_testrunner
docker-post-test:
	docker compose --file tests/testrunner.docker-compose.yaml down

k8s-recreate-namespace: k8s-delete-namespace k8s-namespace
k8s-do-test:
	$(PYTHON_VARS_BEFORE_PYTEST) $(PYTHON_RUNNER) pytest --env k8s $(PYTHON_VARS_AFTER_PYTEST) \
	 --cov=$(PYTHON_SRC) --cov-report=term-missing --cov-report html:build/reports/code-coverage --cov-report xml:build/reports/code-coverage.xml --junitxml=build/reports/unit-tests.xml $(PYTHON_TEST_FILE)
