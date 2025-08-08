# SQLAlchemy Dictionary to JSON Fix

## Issue Description

When running line 246 of `dm_storage_requests.py`, the following error was encountered:

```
psycopg2.ProgrammingError: can't adapt type 'dict'
```

This error was raised from line 943 of `sqlalchemy/engine/default.py` (library method).

## Root Cause

The error occurred in the `create_storage_config` function when trying to insert a Python dictionary into a PostgreSQL JSON column. The function creates a `post_data` dictionary that includes a nested dictionary in the "config" field:

```python
post_data = {
    "storage_id": storage_id,
    "config": config,  # This is a Python dictionary
    "config_type": config_type,
}
```

Then it tries to insert this data into the database:

```python
return DB.insert(CONFIG.DLM.storage_config_table, json=post_data)[0]["config_id"]
```

The issue is that psycopg2 (the PostgreSQL adapter for Python) doesn't know how to automatically convert a nested Python dictionary to a PostgreSQL JSON type. In the database schema, the "config" column is defined as a JSON type:

```sql
CREATE TABLE IF NOT EXISTS storage_config (
    config_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    storage_id uuid NOT NULL,
    config_type config_type DEFAULT 'rclone',
    config json NOT NULL,  # JSON type
    config_date timestamp without time zone DEFAULT now(),
    CONSTRAINT fk_cfg_storage_id
      FOREIGN KEY(storage_id)
      REFERENCES storage(storage_id)
      ON DELETE SET NULL
);
```

PostgreSQL's JSON type expects a string representation of JSON, but we were passing a Python dictionary.

## Solution

The solution is to convert the Python dictionary to a JSON string before inserting it into the database, and then parse it back to a Python dictionary when retrieving it.

### Changes Made

1. Added an import for the `json` module at the top of the file:
   ```python
   import json
   ```

2. Modified the `create_storage_config` function to convert the config dictionary to a JSON string:
   ```python
   post_data = {
       "storage_id": storage_id,
       "config": json.dumps(config),  # Convert to JSON string
       "config_type": config_type,
   }
   ```

3. Updated the `get_storage_config` function to parse the JSON string back to a Python dictionary:
   ```python
   result = DB.select(CONFIG.DLM.storage_config_table, params=params)
   # Parse the JSON string back to a Python dictionary
   return [json.loads(entry["config"]) if isinstance(entry["config"], str) else entry["config"] for entry in result] if result else []
   ```

### Why This Fixes the Issue

1. **Insertion**: When inserting data, we now convert the Python dictionary to a JSON string using `json.dumps()`. This string can be properly stored in PostgreSQL's JSON column.

2. **Retrieval**: When retrieving data, we parse the JSON string back to a Python dictionary using `json.loads()`. We also added a check to only parse the string if it's actually a string, to handle cases where the data might already be a dictionary (for backward compatibility).

3. **Usage**: We verified that all code that uses the config expects it to be a dictionary with a "name" key, which is consistent with our changes.

This approach ensures that the data is properly stored in the database and correctly retrieved for use in the application.

## Conclusion

By properly handling the conversion between Python dictionaries and JSON strings, we've fixed the "can't adapt type 'dict'" error and ensured that the code works correctly with PostgreSQL's JSON type.