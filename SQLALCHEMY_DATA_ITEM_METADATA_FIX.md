# SQLAlchemy Data Item Metadata Fix

## Issue Description

When running the test `test_register_data_item_with_metadata`, the following error was encountered:

```
psycopg2.ProgrammingError: can't adapt type 'dict'
```

This error was raised from `sqlalchemy/engine/default.py:943: ProgrammingError` and was originally called from `ska_dlm/data_item/data_item_requests.py:113`.

## Root Cause

The error occurred in the `update_data_item` function when trying to insert a Python dictionary into a PostgreSQL JSON column. The function was passing a `post_data` dictionary that contained a `metadata` key with a nested dictionary value directly to `DB.update`. However, PostgreSQL's JSON type expects a string representation of JSON, not a Python dictionary.

In the database schema, the `metadata` column in the `data_item` table is defined as a JSONB type:

```sql
CREATE TABLE IF NOT EXISTS data_item (
    ...
    metadata jsonb DEFAULT NULL,
    ...
);
```

PostgreSQL's JSONB type expects a string representation of JSON, but we were passing a Python dictionary.

## Solution

The solution is to convert the Python dictionary to a JSON string before inserting it into the database, and then parse it back to a Python dictionary when retrieving it.

### Changes Made

1. Added an import for the `json` module at the top of the file:
   ```python
   import json
   ```

2. Modified the `update_data_item` function to convert dictionary values to JSON strings:
   ```python
   # Convert dictionary values to JSON strings for PostgreSQL JSON columns
   if post_data and "metadata" in post_data and isinstance(post_data["metadata"], dict):
       # Create a copy of post_data to avoid modifying the original
       post_data_copy = post_data.copy()
       # Convert the metadata dictionary to a JSON string
       post_data_copy["metadata"] = json.dumps(post_data["metadata"])
       return DB.update(CONFIG.DLM.dlm_table, params=params, json=post_data_copy)[0]
   ```

3. Modified the `query_data_item` function to parse JSON strings back to Python dictionaries:
   ```python
   # Parse JSON strings back to Python dictionaries for metadata
   for result in results:
       if "metadata" in result and isinstance(result["metadata"], str):
           try:
               result["metadata"] = json.loads(result["metadata"])
           except (json.JSONDecodeError, TypeError):
               # If the metadata is not a valid JSON string, leave it as is
               pass
   ```

### Why This Fixes the Issue

1. **Insertion**: When inserting or updating data, we now convert the Python dictionary to a JSON string using `json.dumps()`. This string can be properly stored in PostgreSQL's JSONB column.

2. **Retrieval**: When retrieving data, we parse the JSON string back to a Python dictionary using `json.loads()`. We also added error handling to handle cases where the metadata might not be a valid JSON string.

3. **Compatibility**: The changes maintain backward compatibility with the existing code that expects metadata to be a Python dictionary when retrieved from the database.

This approach ensures that the data is properly stored in the database and correctly retrieved for use in the application.

## Conclusion

By properly handling the conversion between Python dictionaries and JSON strings, we've fixed the "can't adapt type 'dict'" error and ensured that the code works correctly with PostgreSQL's JSONB type.