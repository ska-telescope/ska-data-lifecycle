from datetime import datetime
import sys
import os


from time import sleep

from ska_dlm import dlm_storage, dlm_request

SLEEP_DURATION = 2 #seconds


def expire_UIDs():
    expired_data_items = dlm_request.query_expired()

    for uid in expired_data_items:
        dlm_storage.expire_data_item(uid)

    if len(expired_data_items) > 0:
        print(f'Expired {len(expired_data_items)} data items')


def main():
    while True:
        expire_UIDs()

        sleep(SLEEP_DURATION)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        try:
            sys.exit(130)
        except SystemExit:
            os._exit(130)