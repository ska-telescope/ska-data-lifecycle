# UUID JSON Serialization Fix

## Issue Description

When running the test `test_register_data_item_with_metadata`, the following error was encountered:

```
TypeError: Object of type UUID is not JSON serializable
```

This error occurred because the code was trying to serialize a Python dictionary containing UUID objects to JSON using the standard `json.dumps()` function, which doesn't know how to handle UUID objects.

## Root Cause

The issue was in the `update_data_item` function in `src/ska_dlm/data_item/data_item_requests.py`. This function is called by `set_metadata`, which is in turn called by `register_data_item` in `src/ska_dlm/dlm_ingest/dlm_ingest_requests.py`.

The flow of execution is as follows:

1. `register_data_item` adds a UUID object to the metadata dictionary:
   ```python
   metadata["uid"] = uid  # uid is a UUID object
   metadata["item_name"] = item_name
   set_metadata(uid, metadata)
   ```

2. `set_metadata` passes the metadata to `update_data_item`:
   ```python
   return update_data_item(uid=uid, post_data={"metadata": metadata_post})
   ```

3. `update_data_item` tries to serialize the metadata to JSON:
   ```python
   post_data_copy["metadata"] = json.dumps(post_data["metadata"])
   ```

The error occurs at step 3 because the standard `json.dumps()` function doesn't know how to serialize UUID objects to JSON.

## Solution

The solution is to use a custom JSON encoder that can handle UUID objects. We implemented this in two steps:

1. Created a new file `src/ska_dlm/json_utils.py` with a custom JSON encoder:
   ```python
   class UUIDEncoder(json.JSONEncoder):
       """JSON encoder that can handle UUID objects."""

       def default(self, obj: Any) -> Any:
           """Convert UUID objects to strings."""
           if isinstance(obj, uuid.UUID):
               # Convert UUID objects to strings
               return str(obj)
           # Let the base class handle other types
           return super().default(obj)
   ```

2. Updated the `json.dumps()` call in `update_data_item` to use this encoder:
   ```python
   post_data_copy["metadata"] = json.dumps(post_data["metadata"], cls=UUIDEncoder)
   ```

This ensures that UUID objects in the metadata dictionary are properly serialized to JSON strings.

## Benefits

1. **Fixes the Error**: The custom JSON encoder properly handles UUID objects, preventing the "Object of type UUID is not JSON serializable" error.

2. **Maintains Compatibility**: The UUID objects are serialized to strings, which is a standard way to represent UUIDs in JSON.

3. **Minimal Changes**: The fix is localized to the JSON serialization code, without requiring changes to the rest of the codebase.

## Future Considerations

1. **Deserialization**: If needed, we could also implement a custom JSON decoder to convert UUID strings back to UUID objects when deserializing. However, this isn't strictly necessary for fixing the current issue, as the error occurs during serialization, not deserialization.

2. **Other Non-Serializable Types**: If other non-serializable types are used in the codebase, the custom encoder could be extended to handle them as well.

## Conclusion

By implementing a custom JSON encoder that can handle UUID objects, we've fixed the "Object of type UUID is not JSON serializable" error that was occurring when running the `test_register_data_item_with_metadata` test. This ensures that metadata containing UUID objects can be properly serialized to JSON and stored in the database.