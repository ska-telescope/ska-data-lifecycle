#!/bin/bash

# shellcheck disable=SC2046
source $(dirname "$0")/helm_common.sh

# start chart and delay so that we don't fail straight away
helm install $HELM_NAME ./charts/ska-dlm
sleep $DELAY_SECONDS

attempt=1
while [[ $attempt -le $MAX_RETRIES ]]; do
    kubectl exec --stdin --tty ska-dlm-postgres-0 -- psql -U postgres -h localhost -p 5432 < setup/DB/ska_dlm_meta.sql
    if [[ $? -eq 0 ]]; then
        # successful connection
        break
    fi
    echo "Attempt $attempt failed for postgres. Retrying in $DELAY_SECONDS second(s)..."
    sleep $DELAY_SECONDS
    ((attempt++))
done

if [[ $attempt -gt $MAX_RETRIES ]]; then
    echo "Max retries reached for postgres. Unable to establish connection."
    helm uninstall $HELM_NAME
    exit 1
fi

docker_ps_line=`docker ps -a | grep postgrest`
container_id="${docker_ps_line%% *}"

echo
echo Using docker to stop postgrest container, k8s will restart it
docker stop $container_id;sleep 1;docker rm $container_id
echo finished
echo
echo Now make sure 'minikube tunnel' has been run \(to get a node IP address\)
echo and got to the following URL to confirm it is running
echo \\t http://\<tunnel IP address\>:30080