# SQLAlchemy Migration

This document describes the changes made to migrate the SKA Data Lifecycle Management system from using PostgREST to directly accessing the PostgreSQL database using SQLAlchemy.

## Overview

The SKA Data Lifecycle Management system previously used PostgREST as an intermediary to access the PostgreSQL database. This added an extra layer of complexity and potential points of failure. By migrating to SQLAlchemy, we have simplified the architecture and improved performance by connecting directly to the database.

## Changes Made

### Code Changes

1. **SQLAlchemy Database Access Implementation**
   - Created a new implementation in `src/ska_dlm/dlm_db/db_access_sqlalchemy.py`
   - Maintained the same interface as the original PostgREST-based implementation
   - Implemented conversion of PostgREST-style query parameters to SQLAlchemy queries
   - Added support for environment variables for database connection parameters

2. **Configuration Updates**
   - Created a new configuration file `src/ska_dlm/config_sqlalchemy.yaml`
   - Added database connection parameters for SQLAlchemy
   - Maintained backward compatibility with the existing configuration

3. **Import Updates**
   - Updated all modules that import from `ska_dlm.dlm_db.db_access` to import from `ska_dlm.dlm_db.db_access_sqlalchemy` instead
   - Updated `src/ska_dlm/__init__.py` to use `config_sqlalchemy.yaml` instead of `config.yaml`

### Kubernetes Deployment Changes

1. **ConfigMap and Secret**
   - Created a new ConfigMap template for database connection parameters
   - Created a new Secret template for database password
   - Updated the dlm-configmap.yaml file to include the config_sqlalchemy.yaml file

2. **Deployment Templates**
   - Updated all deployment templates to load environment variables from the SQLAlchemy ConfigMap and Secret
   - Maintained backward compatibility with the existing configuration

## Benefits

1. **Simplified Architecture**
   - Eliminated the need for an intermediary service (PostgREST)
   - Reduced network overhead and potential points of failure

2. **Performance Improvements**
   - Reduced latency by eliminating the HTTP request/response cycle
   - Enabled more efficient query execution

3. **Enhanced Functionality**
   - Provided more advanced query capabilities
   - Supported transactions and other database features
   - Offered better error handling and debugging
   - Added support for complex logical operators in queries

4. **Better Type Safety**
   - Provided type checking and validation at the Python level
   - Reduced the risk of runtime errors due to type mismatches

## Future Work

1. **Remove PostgREST**
   - Once all components are successfully using SQLAlchemy, the PostgREST service can be removed
   - Update the Kubernetes deployment templates to remove the PostgREST service
   - Remove the PostgREST-specific configuration from the application

2. **Optimize SQLAlchemy Usage**
   - Implement connection pooling and other performance optimizations
   - Use SQLAlchemy's ORM features for more advanced database operations
   - Implement more advanced error handling and retry mechanisms

## Environment Variables

The following environment variables are used to configure the SQLAlchemy database connection:

- `PGHOST`: The PostgreSQL host
- `PGUSER`: The PostgreSQL user
- `PGPASSWORD`: The PostgreSQL password
- `PGDATABASE`: The PostgreSQL database
- `PGSCHEMA`: The PostgreSQL schema

These environment variables are set in the Kubernetes deployment templates using the SQLAlchemy ConfigMap and Secret.

## Configuration File

The `config_sqlalchemy.yaml` file contains the following configuration:

```yaml
DLM:
  dlm_db: "ska_dlm_meta"
  dlm_table: "data_item"
  storage_table: "storage"
  storage_config_table: "storage_config"
  location_table: "location"
  migration_table: "migration"
  storage_manager:
    storage_warning_percentage: 80.0
    polling_interval: 10 # seconds
  migration_manager:
    polling_interval: 10 # seconds
DB:
  host: "postgresql"
  user: "postgres"
  password: "postgres"
  database: "ska_dlm_meta"
  schema: "public"
RCLONE:
  - "http://rclone"
```

The `DB` section contains the database connection parameters for SQLAlchemy.

## Complex Logical Operators

One of the challenges in migrating from PostgREST to SQLAlchemy was handling complex logical operators in queries. PostgREST supports a specific syntax for logical operators like "and" and "or" with nested conditions, which needed to be properly translated to SQLAlchemy queries.

### Issue

In the original PostgREST implementation, complex logical conditions could be expressed using the following syntax:

```python
params["and"] = "(date.gte.2023-01-01,date.lte.2023-12-31)"  # AND condition
params["or"] = "(source_storage_id.eq.123,destination_storage_id.eq.123)"  # OR condition
```

These complex expressions weren't handled by the initial SQLAlchemy implementation, which only supported simple filter operators like "eq.", "gt.", etc.

### Solution

The `_postgrest_params_to_sqlalchemy` method was enhanced to handle these complex logical operators:

1. It now detects when a parameter key is "and" or "or"
2. It parses the complex expression enclosed in parentheses
3. It extracts the individual conditions (e.g., "date.gte.2023-01-01" and "date.lte.2023-12-31")
4. It converts each condition to a SQLAlchemy-compatible format
5. It combines the conditions with the appropriate logical operator (AND or OR)

### Examples

The following examples show how complex logical operators are used in the codebase:

1. **AND Operator** - Used in `dlm_migration_requests.py` to filter migrations by date range:

```python
params["and"] = f"(date.gte.{start_date},date.lte.{end_date})"
```

This is converted to a SQLAlchemy query like:
```sql
WHERE (date >= :date_gte_0 AND date <= :date_lte_1)
```

2. **OR Operator** - Used in `dlm_migration_requests.py` to filter migrations by storage ID:

```python
params["or"] = f"(source_storage_id.eq.{storage_id},destination_storage_id.eq.{storage_id})"
```

This is converted to a SQLAlchemy query like:
```sql
WHERE (source_storage_id = :source_storage_id_eq_0 OR destination_storage_id = :destination_storage_id_eq_1)
```

These enhancements ensure that all PostgREST-style queries used in the codebase work correctly with the SQLAlchemy implementation.