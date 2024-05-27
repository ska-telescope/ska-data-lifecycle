make python-pre-test
# make python-do-test

echo ">>> Initialise locations"
ska-dlm storage init-location --location-name MyHost --location-type server

echo ">>> Initialise storage endpoints"
ska-dlm storage init-storage --location-name=MyHost --storage-type=disk --storage-interface=posix --storage-capacity=10000000 --storage-name=MyDisk1
ska-dlm storage init-storage --location-name=MyHost --storage-type=disk --storage-interface=posix --storage-capacity=10000000 --storage-name=MyDisk2

echo ">>> Configure rclone endpoints"
ska-dlm storage create-storage-config --storage-name=MyDisk1 --config='{"name":"MyDisk1","type":"local", "parameters":{}}'
ska-dlm storage create-storage-config --storage-name=MyDisk2 --config='{"name":"MyDisk2","type":"local", "parameters":{}}'
