# SQLAlchemy Item Tags Fix

## Issue Description

When running the test `test_update_item_tags`, the following error was encountered:

```
psycopg2.ProgrammingError: can't adapt type 'dict'
```

This error was raised from line 943 of `sqlalchemy/engine/default.py` (library method) and was called by `src/ska_dlm/data_item/data_item_requests.py:136`.

## Root Cause

The error occurred in the `update_data_item` function when trying to insert a Python dictionary into a PostgreSQL JSON column. The function was passing a `post_data` dictionary that contained an `item_tags` key with a nested dictionary value directly to `DB.update`. However, PostgreSQL's JSON type expects a string representation of JSON, not a Python dictionary.

In the database schema, the `item_tags` column in the `data_item` table is defined as a JSON type:

```sql
CREATE TABLE IF NOT EXISTS data_item (
    ...
    item_tags json DEFAULT NULL,
    ...
);
```

PostgreSQL's JSON type expects a string representation of JSON, but we were passing a Python dictionary.

## Solution

The solution is to convert the Python dictionary to a JSON string before inserting it into the database, and then parse it back to a Python dictionary when retrieving it. We already had similar handling for the `metadata` field, so we extended this to handle the `item_tags` field as well.

### Changes Made

1. Modified the `update_data_item` function to convert dictionary values in `item_tags` to JSON strings:
   ```python
   # Convert dictionary values to JSON strings for PostgreSQL JSON columns
   if post_data:
       # Create a copy of post_data to avoid modifying the original
       post_data_copy = post_data.copy()
       
       # Convert metadata dictionary to JSON string if present
       if "metadata" in post_data and isinstance(post_data["metadata"], dict):
           post_data_copy["metadata"] = json.dumps(post_data["metadata"], cls=UUIDEncoder)
           
       # Convert item_tags dictionary to JSON string if present
       if "item_tags" in post_data and isinstance(post_data["item_tags"], dict):
           post_data_copy["item_tags"] = json.dumps(post_data["item_tags"], cls=UUIDEncoder)
           
       return DB.update(CONFIG.DLM.dlm_table, params=params, json=post_data_copy)[0]
   ```

2. Updated the `query_data_item` function to parse JSON strings back to Python dictionaries for the `item_tags` field:
   ```python
   # Parse JSON strings back to Python dictionaries for metadata and item_tags
   for result in results:
       # Handle metadata field
       if "metadata" in result and isinstance(result["metadata"], str):
           try:
               result["metadata"] = json.loads(result["metadata"])
           except (json.JSONDecodeError, TypeError):
               # If the metadata is not a valid JSON string, leave it as is
               pass
       
       # Handle item_tags field
       if "item_tags" in result and isinstance(result["item_tags"], str):
           try:
               result["item_tags"] = json.loads(result["item_tags"])
           except (json.JSONDecodeError, TypeError):
               # If the item_tags is not a valid JSON string, leave it as is
               pass
   ```

### Why This Fixes the Issue

1. **Insertion**: When inserting or updating data, we now convert the Python dictionary to a JSON string using `json.dumps()`. This string can be properly stored in PostgreSQL's JSON column.

2. **Retrieval**: When retrieving data, we parse the JSON string back to a Python dictionary using `json.loads()`. We also added error handling to handle cases where the JSON parsing might fail.

3. **Compatibility**: The changes maintain backward compatibility with the existing code that expects `item_tags` to be a Python dictionary when retrieved from the database.

This approach ensures that the data is properly stored in the database and correctly retrieved for use in the application.

## Conclusion

By properly handling the conversion between Python dictionaries and JSON strings for the `item_tags` field, we've fixed the "can't adapt type 'dict'" error and ensured that the code works correctly with PostgreSQL's JSON type. This is similar to the fix we previously implemented for the `metadata` field.