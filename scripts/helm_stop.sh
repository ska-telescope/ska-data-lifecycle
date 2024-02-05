#!/bin/bash

# shellcheck disable=SC2046
source $(dirname "$0")/helm_common.sh

helm uninstall $HELM_NAME