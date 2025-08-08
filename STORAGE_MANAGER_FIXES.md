# Storage Manager Fixes

This document describes the fixes implemented to address issues in the Storage Manager component of the SKA Data Lifecycle Management system.

## Issues Fixed

### 1. UnboundLocalError for `copy_uid` Variable

**Problem:**
During the test `test_persist_new_data_items`, an error was encountered:
```
UnboundLocalError: local variable 'copy_uid' referenced before assignment
```

This occurred because the `copy_uid` variable was assigned inside a try block, but was then referenced after the except block even if an exception occurred, causing the variable to remain unbound.

**Solution:**
- Initialize `copy_uid = None` before the try block to ensure it's always defined
- Move the success-path code (logging, setting phases, and updating status) inside the try block so it only executes if the copy operation succeeds
- Keep the exception handling in the except block

This ensures that `copy_uid` is always defined, and the code that uses `copy_uid["uid"]` only executes if `copy_uid` was successfully assigned a value.

### 2. "Unable to identify a suitable new storage volume" Error

**Problem:**
During the test, the following error was encountered:
```
ERROR ska_dlm.dlm_storage.main:main.py:47 Unable to identify a suitable new storage volume!
```

This occurred when there were no storage volumes with a different ID than the current data item's storage ID, or when the data item didn't have a storage_id.

**Solution:**
- Add a check to see if the data item has a storage_id field
- If no storage_id is present, use the first available storage
- Add more detailed logging to help diagnose the issue, including logging the current storage_id and available storage volumes
- Improve the error handling to be more specific about what's missing (no storage_id, no storage volumes available, or no suitable new storage volume)

These changes help prevent the error by handling cases where a data item doesn't have a storage_id and providing more detailed error messages to help diagnose the issue.

## Implementation Details

### Changes to `persist_new_data_items` Function

1. **Fix for UnboundLocalError:**
```python
copy_uid = None  # Initialize before try block
try:
    copy_uid = dlm_migration.copy_data_item(
        uid=new_data_item["uid"],
        destination_id=dest_id,
    )
    # Success path code moved inside try block
    logger.info(
        "Persisted %s to volume %s",
        new_data_item["item_name"],
        new_storage["storage_name"],
    )
    data_item.set_phase(uid=new_data_item["uid"], phase="LIQUID")
    data_item.set_phase(uid=copy_uid["uid"], phase="LIQUID")
    stat[new_data_item["item_name"]] = True
except DataLifecycleError:
    logger.exception("Copy of data_item %s unsuccessful!", new_data_item["item_name"])
```

2. **Fix for Storage Volume Selection:**
```python
# Check if the data item has a storage_id
if "storage_id" not in new_data_item or not new_data_item["storage_id"]:
    logger.warning("Data item %s has no storage_id", new_data_item["item_name"])
    # Use the first available storage
    if storages:
        new_storage = [storages[0]]
    else:
        logger.error("No storage volumes available!")
        continue
else:
    # Filter out the current storage to find a different one
    new_storage = [s for s in storages if s["storage_id"] != new_data_item["storage_id"]]
    if not new_storage:
        logger.error("Unable to identify a suitable new storage volume!")
        logger.info("Current storage_id: %s", new_data_item["storage_id"])
        logger.info("Storage volumes found: %s", storages)
        continue
```

## Benefits

1. **Improved Robustness:**
   - The code now handles cases where exceptions occur during the copy operation
   - It also handles cases where data items don't have a storage_id

2. **Better Error Reporting:**
   - More detailed error messages help diagnose issues
   - Specific error messages for different failure scenarios

3. **Cleaner Code Structure:**
   - Success path code is now contained within the try block
   - Error handling is more explicit and comprehensive