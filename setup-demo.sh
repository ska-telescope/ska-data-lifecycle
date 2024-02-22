make python-pre-test

echo ">>> Initialise locations"
ska-dlm storage init-location --location-name MyHost --location-type server
# LOCATION=`ska-dlm storage init-location --location-name Pawsey --location-type HPC-centre`
# echo ">>> location_id: $LOCATION"

echo ">>> Initialise storage endpoints"
ska-dlm storage init-storage --location-name=MyHost --storage-type=disk --storage-interface=posix --storage-capacity=10000000 --storage-name=MyDisk1
ska-dlm storage init-storage --location-name=MyHost --storage-type=disk --storage-interface=posix --storage-capacity=10000000 --storage-name=MyDisk2
# ska-dlm storage init-storage --storage-capacity=5000000000 --storage-name=myacacia --location-id=$LOCATION --storage-type=object-store --storage-interface=s3 --storage-phase-level="LIQUID"
# ska-dlm storage init-storage --help
# ska-dlm storage init-storage --storage-capacity=5000000000 --storage-name=myacacia --json-data="{\"storage_name\": \"myacacia\", \"storage_type\": \"object-store\", \"storage_interface\": \"s3\", \"storage_capacity\": 5000000000, \"storage_phase_level\":\"LIQUID\", \"location_id\":\"${LOCATION}\"}"

echo ">>> Configure rclone endpoints"
ska-dlm storage create-storage-config --storage-name=MyDisk1 --config='{"name":"MyDisk1","type":"local", "parameters":{}}'
ska-dlm storage create-storage-config --storage-name=MyDisk2 --config='{"name":"MyDisk2","type":"local", "parameters":{}}'
# ska-dlm storage create-storage-config --storage-name=myacacia --config='{"name":"myacacia","type":"s3", "parameters":{"access_key_id": "YQ5CTPOXS0VJMR68P915","endpoint": "https://projects.pawsey.org.au","provider": "Ceph","secret_access_key": "vT3WlB28w0LBquWgnGXyjqIHLzAKabuCDBznLzXO"}}' >/dev/null 2>&1
