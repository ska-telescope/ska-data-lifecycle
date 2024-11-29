DOCS_SPHINXOPTS = -W --keep-going
PYTHON_LINE_LENGTH = 99

K8S_CHART = ska-dlm
KUBE_NAMESPACE ?=
HELM_RELEASE ?= $(K8S_CHART)-default  # unique value
KUBE_APP = $(HELM_RELEASE)
HELM_TIMEOUT ?= 5m
HELM_VALUES ?= resources/config-ci-dev-values.yaml resources/cluster-sdhp-values.yaml
K8S_CHART_PARAMS ?= $(foreach file,$(HELM_VALUES),--values $(file)) --wait --timeout=$(HELM_TIMEOUT) --set pgweb.enabled=true

include .make/base.mk
include .make/helm.mk
include .make/python.mk
include .make/oci.mk
include .make/k8s.mk

# MacOS Arm64 ingress has issues. Workaround is to run with
# `minikube tunnel` and connect via localhost
# See https://github.com/kubernetes/minikube/issues/13510
ifndef GITLAB_CI
ifeq ($(shell uname -m), arm64)
	K8S_HOST_URL ?= http://localhost
else
	K8S_HOST_URL ?= http://$(shell minikube ip)
endif
endif  # GITLAB_CI

SHARED_VOLUMES_DIR ?= ${PWD}/tests/volumes

# Make these available as environment variables
export KUBE_NAMESPACE K8S_HOST_URL SHARED_VOLUMES_DIR

.PHONY: docs-pre-build k8s-recreate-namespace k8s-do-test

docs-pre-build: ## setup the document build environment.
	poetry install --only main,docs

python-pre-test:
	docker compose --file tests/services.docker-compose.yaml -p dlm-test-services up --detach --wait
python-post-test:
	docker compose --file tests/services.docker-compose.yaml -p dlm-test-services down

docker-test: docker-pre-test docker-do-test docker-post-test
docker-pre-test:
	docker compose --file tests/testrunner.docker-compose.yaml -p dlm-test-services build
docker-do-test:
	docker compose --file tests/testrunner.docker-compose.yaml -p dlm-test-services run dlm_testrunner
docker-post-test:
	docker compose --file tests/testrunner.docker-compose.yaml -p dlm-test-services down

oci-build-gateway:
	make oci-build OCI_IMAGE=ska-data-lifecycle-test-gateway \
	OCI_IMAGE_FILE_PATH=tests/Dockerfile-gateway

oci-build-keycloak:
	make oci-build OCI_IMAGE=ska-data-lifecycle-test-keycloak \
	OCI_IMAGE_FILE_PATH=tests/Dockerfile-keycloak

k8s-recreate-namespace: k8s-delete-namespace k8s-namespace
k8s-do-test:
	$(PYTHON_VARS_BEFORE_PYTEST) $(PYTHON_RUNNER) pytest --env k8s $(PYTHON_VARS_AFTER_PYTEST) \
	 --cov=$(PYTHON_SRC) --cov-report=term-missing --cov-report html:build/reports/code-coverage --cov-report xml:build/reports/code-coverage.xml --junitxml=build/reports/unit-tests.xml $(PYTHON_TEST_FILE)

define DP_PVC
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: shared-mnl
  namespace: ${KUBE_NAMESPACE}
spec:
  accessModes:
  - ReadWriteMany
  resources:
    requests:
      storage: $${SHARED_CAPACITY}
  storageClassName: ""
  volumeMode: Filesystem
  volumeName: dpshared-${KUBE_NAMESPACE}-mnl
endef
export DP_PVC

# DP Cluster shared PV hack
## Delete the existing PVC and PV. Note that this is safe as the PV is shared clusterwide
## Recreate the PV and PVC before installing the app
k8s-pre-install-chart:
	if [[ "$(CI_RUNNER_TAGS)" == *"ska-k8srunner-dp"* ]] || [[ "$(CI_RUNNER_TAGS)" == *"ska-k8srunner-dp-gpu-a100"* ]] ; then \
	make k8s-namespace ;\
	kubectl -n ${KUBE_NAMESPACE} delete --now --ignore-not-found pvc/shared-mnl || true ;\
	kubectl delete --now --ignore-not-found pv/dpshared-${KUBE_NAMESPACE}-mnl || true ;\
	apt-get update && apt-get install gettext -y ;\
	export SHARED_CAPACITY=5Gi ; \
	echo "$${DP_PVC}" | envsubst | kubectl -n $(KUBE_NAMESPACE) apply -f - ;\
	kubectl get pv dpshared-dp-shared-mnl -o json | \
	jq ".metadata = { \"name\": \"dpshared-${KUBE_NAMESPACE}-mnl\" }" | \
	jq ".spec.csi.volumeHandle = \"dpshared-${KUBE_NAMESPACE}-mnlfs-pv\"" | \
	jq 'del(.spec.claimRef)' | \
	jq 'del(.status)' | \
	kubectl apply -f - ; \
	elif [[ "$(CI_RUNNER_TAGS)" == *"k8srunner"* ]] || [[ "$(CI_RUNNER_TAGS)" == *"k8srunner-gpu-v100"* ]] ; then \
		echo "techops not implemented yet!" ;\
	fi