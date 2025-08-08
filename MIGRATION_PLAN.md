# Migration Plan: PostgREST to SQLAlchemy

This document outlines the plan for migrating the SKA Data Lifecycle Management system from using PostgREST to directly accessing the PostgreSQL database using SQLAlchemy.

## Background

The current implementation uses PostgREST as an intermediary to access the PostgreSQL database. This adds an extra layer of complexity and potential points of failure. By migrating to SQLAlchemy, we can simplify the architecture and improve performance by connecting directly to the database.

## Migration Steps

### 1. Preparation

1. Install required dependencies:
   ```bash
   pip install sqlalchemy psycopg2-binary
   ```

2. Update `pyproject.toml` to include the new dependencies:
   ```toml
   [tool.poetry.dependencies]
   sqlalchemy = "^2.0.0"
   psycopg2-binary = "^2.9.0"
   ```

### 2. Implementation

1. Create a new SQLAlchemy-based database access implementation:
   - File: `src/ska_dlm/dlm_db/db_access_sqlalchemy.py`
   - This file provides the same interface as the original PostgREST-based implementation but uses SQLAlchemy to connect directly to the database.

2. Update the configuration to support direct database connection:
   - File: `src/ska_dlm/config_sqlalchemy.yaml`
   - This file includes the necessary database connection parameters for SQLAlchemy.

3. Create a feature flag to switch between PostgREST and SQLAlchemy:
   - Update `src/ska_dlm/__init__.py` to include a feature flag for using SQLAlchemy.
   - This allows for a gradual migration and easy rollback if issues are encountered.

### 3. Testing

1. Create a test script to verify the SQLAlchemy implementation:
   - File: `tests/unit/test_db_access_sqlalchemy.py`
   - This script tests the basic CRUD operations using the SQLAlchemy implementation.

2. Update existing tests to work with both PostgREST and SQLAlchemy:
   - Modify tests to use the appropriate database access implementation based on the feature flag.

### 4. Deployment

1. Update the Kubernetes deployment templates to include the necessary environment variables for SQLAlchemy:
   - Add environment variables for database connection parameters (PGHOST, PGUSER, PGPASSWORD, PGDATABASE, PGSCHEMA).
   - Update the ConfigMap to include the new configuration file.

2. Deploy the updated application with the feature flag set to use PostgREST initially:
   - This allows for a safe deployment without immediately switching to SQLAlchemy.

3. Gradually enable SQLAlchemy for specific components:
   - Start with non-critical components to minimize risk.
   - Monitor for issues and roll back if necessary.

4. Once all components are successfully using SQLAlchemy, remove the PostgREST dependency:
   - Update the Kubernetes deployment templates to remove the PostgREST service.
   - Remove the PostgREST-specific configuration from the application.

### 5. Cleanup

1. Remove the PostgREST-based implementation:
   - File: `src/ska_dlm/dlm_db/db_access.py`
   - Replace with the SQLAlchemy-based implementation.

2. Remove the feature flag and related code:
   - Simplify the codebase by removing the feature flag and related conditional logic.

3. Update documentation to reflect the new architecture:
   - Update the README and other documentation to describe the direct database access using SQLAlchemy.

## Implementation Details

### Feature Flag Implementation

Add a feature flag to `src/ska_dlm/__init__.py`:

```python
# Feature flag for using SQLAlchemy
USE_SQLALCHEMY = os.environ.get("USE_SQLALCHEMY", "false").lower() == "true"

# Load the appropriate configuration file
if USE_SQLALCHEMY:
    CONFIG = read_config(DLM_HOME / "config_sqlalchemy.yaml")
else:
    CONFIG = read_config(DLM_HOME / "config.yaml")

# Import the appropriate database access implementation
if USE_SQLALCHEMY:
    from .dlm_db.db_access_sqlalchemy import DB
else:
    from .dlm_db.db_access import DB
```

### Database Access Implementation

The SQLAlchemy-based implementation (`db_access_sqlalchemy.py`) provides the same interface as the original PostgREST-based implementation (`db_access.py`), allowing for a seamless transition.

Key features:
- Same method signatures: `insert()`, `update()`, `select()`, `delete()`
- Conversion of PostgREST-style query parameters to SQLAlchemy queries
- Support for environment variables for database connection parameters
- Error handling compatible with the original implementation

### Configuration Updates

The new configuration file (`config_sqlalchemy.yaml`) includes the necessary database connection parameters for SQLAlchemy while maintaining backward compatibility with the existing configuration.

## Rollback Plan

If issues are encountered during the migration, the following rollback steps can be taken:

1. Set the feature flag to use PostgREST:
   ```bash
   export USE_SQLALCHEMY=false
   ```

2. Restart the application to apply the change.

3. If necessary, roll back any code changes that are specific to SQLAlchemy.

## Timeline

The migration should be completed in phases:

1. **Phase 1 (Week 1)**: Implementation and initial testing
2. **Phase 2 (Week 2)**: Deployment and gradual enablement
3. **Phase 3 (Week 3)**: Cleanup and documentation

## Conclusion

Migrating from PostgREST to SQLAlchemy will simplify the architecture, improve performance, and reduce potential points of failure. The migration plan outlined above provides a safe and gradual approach to this transition, with the ability to roll back if issues are encountered.