DOCS_SPHINXOPTS = -W --keep-going
PYTHON_LINE_LENGTH = 99

K8S_CHART = ska-dlm
KUBE_NAMESPACE ?= ska-dlm
HELM_RELEASE ?= test
HELM_TIMEOUT ?= 5m
HELM_VALUES ?= resources/initialised-dlm.yaml
K8S_CHART_PARAMS ?= $(foreach file,$(HELM_VALUES),--values $(file)) --wait --timeout=$(HELM_TIMEOUT) --set pgweb.enabled=true

# MacOS Arm64 ingress has issues. Workaround is to run with
# `minikube tunnel` and connect via localhost
# See https://github.com/kubernetes/minikube/issues/13510
ifeq ($(shell uname -m), arm64)
	TEST_INGRESS ?= http://localhost
else
	TEST_INGRESS ?= http://$(shell minikube ip)
endif

include .make/base.mk
include .make/helm.mk
include .make/python.mk
include .make/oci.mk
include .make/k8s.mk

# Make these available as environment variables
export KUBE_NAMESPACE TEST_INGRESS

.PHONY: docs-pre-build k8s-recreate-namespace k8s-do-test

docs-pre-build: ## setup the document build environment.
	poetry config virtualenvs.create false
	poetry install --only main,docs

k8s-recreate-namespace: k8s-delete-namespace k8s-namespace

k8s-do-test: python-test
	echo "running k8s tests on host machine"

# TODO: use independent test services for testing
python-pre-test: k8s-install-chart

# TODO: use independent test services for testing
python-post-test: k8s-uninstall-chart
