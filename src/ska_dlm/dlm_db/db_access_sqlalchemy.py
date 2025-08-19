"""DB access classes, interfaces and utilities using SQLAlchemy."""

import contextlib
import logging
import os
from typing import Any, Dict, List, Optional, Tuple, Union

from sqlalchemy import Column, MetaData, Table, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from .. import CONFIG
from ..exceptions import DatabaseOperationError, DataLifecycleError

logger = logging.getLogger(__name__)


class DBQueryError(DataLifecycleError):
    """An error while performing a database query."""

    def __init__(self, query: str, method: str, params: Optional[Dict[str, Any]] = None, json: Optional[Dict[str, Any]] = None):
        """Create a DBQueryError.

        Parameters
        ----------
        query : str
            The SQL query.
        method : str
            The query method (SELECT, INSERT, UPDATE, DELETE).
        params : Dict[str, Any] | None
            The query parameters.
        json : Dict[str, Any] | None
            The JSON data for the query.
        """
        self.query = query
        self.method = method
        self.params = params
        self.json = json

    def __repr__(self):
        """Python representation."""
        return (
            f"DBQueryError("
            f"query={self.query!r}, "
            f"method={self.method!r}, "
            f"params={self.params!r}, "
            f"json={self.json!r})"
        )

    def __str__(self):
        """Pretty string representation."""
        # If we have json with message and details, use that
        if self.json and "message" in self.json and "details" in self.json:
            return f"DBQueryError: {self.json['message']}\n\tdetails: {self.json['details']}"
        return repr(self)


class SQLAlchemyAccess(contextlib.AbstractContextManager):
    """SQL database client accessed directly through SQLAlchemy."""

    def __init__(
        self,
        db_uri: Optional[str] = None,
        host: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
        schema: str = "public",
    ):
        """Create the DB access.

        Parameters
        ----------
        db_uri : str | None
            The database URI. If provided, other connection parameters are ignored.
        host : str | None
            The database host.
        user : str | None
            The database user.
        password : str | None
            The database password.
        database : str | None
            The database name.
        schema : str
            The database schema.
        """
        # If db_uri is provided, use it directly
        if db_uri:
            self.db_uri = db_uri
        # Otherwise, construct the URI from individual parameters
        else:
            # Use environment variables if parameters are not provided
            host = host or os.environ.get("PGHOST", "localhost")
            user = user or os.environ.get("PGUSER", "postgres")
            password = password or os.environ.get("PGPASSWORD", "postgres")
            database = database or os.environ.get("PGDATABASE", CONFIG.DLM.dlm_db)
            
            self.db_uri = f"postgresql://{user}:{password}@{host}/{database}"
        
        self.schema = schema
        self._engine = create_engine(self.db_uri)
        self._session_factory = sessionmaker(bind=self._engine)
        self._session = None
        self._metadata = MetaData(schema=self.schema)
        self._tables = {}

    def __enter__(self):
        """Enter the database session."""
        self._session = self._session_factory()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Close the underlying database session."""
        if self._session:
            self._session.close()
            self._session = None

    def _get_table(self, table_name: str) -> Table:
        """Get or create a SQLAlchemy Table object for the given table name.

        Parameters
        ----------
        table_name : str
            The name of the table.

        Returns
        -------
        Table
            The SQLAlchemy Table object.
        """
        if table_name not in self._tables:
            # Reflect the table from the database
            self._tables[table_name] = Table(
                table_name, self._metadata, autoload_with=self._engine
            )
        return self._tables[table_name]

    def _postgrest_params_to_sqlalchemy(
        self, table: str, params: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Convert PostgREST-style query parameters to SQLAlchemy query and parameters.

        Parameters
        ----------
        table : str
            The table name.
        params : Dict[str, Any] | None
            The PostgREST-style query parameters.

        Returns
        -------
        Tuple[str, Dict[str, Any]]
            A tuple containing the SQLAlchemy query string and parameters.
        """
        if not params:
            return f"SELECT * FROM {self.schema}.{table}", {}

        # Start with a basic SELECT query
        query = f"SELECT * FROM {self.schema}.{table}"
        where_clauses = []
        query_params = {}
        limit = None
        order_by = None

        # Process the parameters
        for key, value in list(params.items()):  # Create a copy of items to avoid modification during iteration
            if key == "limit":
                limit = int(value)
            elif key == "order":
                order_by = value
            elif key == "select":
                # Replace the SELECT clause
                columns = value.split(",")
                query = f"SELECT {', '.join(columns)} FROM {self.schema}.{table}"
            elif key == "and" or key == "or":
                # Handle complex logical operators with nested conditions
                if isinstance(value, str) and value.startswith("(") and value.endswith(")"):
                    # Extract the conditions from the parentheses
                    conditions_str = value[1:-1]  # Remove the outer parentheses
                    conditions = conditions_str.split(",")
                    
                    # Process each condition
                    condition_clauses = []
                    for i, condition in enumerate(conditions):
                        # Parse the condition (format: field.operator.value)
                        parts = condition.split(".")
                        if len(parts) >= 3:
                            field = parts[0]
                            operator = parts[1]
                            condition_value = ".".join(parts[2:])  # Join the rest in case the value contains dots
                            
                            # Create a unique parameter name for this condition
                            param_name = f"{field}_{operator}_{i}"
                            
                            # Convert the operator to SQL syntax
                            if operator == "eq":
                                condition_clauses.append(f"{field} = :{param_name}")
                            elif operator == "gt":
                                condition_clauses.append(f"{field} > :{param_name}")
                            elif operator == "lt":
                                condition_clauses.append(f"{field} < :{param_name}")
                            elif operator == "gte":
                                condition_clauses.append(f"{field} >= :{param_name}")
                            elif operator == "lte":
                                condition_clauses.append(f"{field} <= :{param_name}")
                            elif operator == "neq":
                                condition_clauses.append(f"{field} != :{param_name}")
                            elif operator == "like":
                                condition_clauses.append(f"{field} LIKE :{param_name}")
                            elif operator == "ilike":
                                condition_clauses.append(f"{field} ILIKE :{param_name}")
                            else:
                                # Default to equality for unknown operators
                                condition_clauses.append(f"{field} = :{param_name}")
                            
                            # Add the parameter value
                            query_params[param_name] = condition_value
                    
                    # Combine the conditions with the appropriate logical operator
                    if condition_clauses:
                        logical_op = " AND " if key == "and" else " OR "
                        where_clauses.append("(" + logical_op.join(condition_clauses) + ")")
            else:
                # Handle filter operators (eq, gt, lt, etc.)
                if isinstance(value, str) and value.startswith("eq."):
                    where_clauses.append(f"{key} = :{key}")
                    query_params[key] = value[3:]  # Remove the "eq." prefix
                elif isinstance(value, str) and value.startswith("gt."):
                    where_clauses.append(f"{key} > :{key}")
                    query_params[key] = value[3:]  # Remove the "gt." prefix
                elif isinstance(value, str) and value.startswith("lt."):
                    where_clauses.append(f"{key} < :{key}")
                    query_params[key] = value[3:]  # Remove the "lt." prefix
                elif isinstance(value, str) and value.startswith("gte."):
                    where_clauses.append(f"{key} >= :{key}")
                    query_params[key] = value[4:]  # Remove the "gte." prefix
                elif isinstance(value, str) and value.startswith("lte."):
                    where_clauses.append(f"{key} <= :{key}")
                    query_params[key] = value[4:]  # Remove the "lte." prefix
                elif isinstance(value, str) and value.startswith("neq."):
                    where_clauses.append(f"{key} != :{key}")
                    query_params[key] = value[4:]  # Remove the "neq." prefix
                elif isinstance(value, str) and value.startswith("like."):
                    where_clauses.append(f"{key} LIKE :{key}")
                    query_params[key] = value[5:]  # Remove the "like." prefix
                elif isinstance(value, str) and value.startswith("ilike."):
                    where_clauses.append(f"{key} ILIKE :{key}")
                    query_params[key] = value[6:]  # Remove the "ilike." prefix
                elif isinstance(value, str) and value.startswith("in."):
                    # Handle IN operator
                    in_values = value[3:].split(",")  # Remove the "in." prefix
                    placeholders = [f":{key}_{i}" for i in range(len(in_values))]
                    where_clauses.append(f"{key} IN ({', '.join(placeholders)})")
                    for i, val in enumerate(in_values):
                        query_params[f"{key}_{i}"] = val
                else:
                    # Default to equality
                    where_clauses.append(f"{key} = :{key}")
                    query_params[key] = value

        # Add WHERE clause if there are any conditions
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        # Add ORDER BY clause if specified
        if order_by:
            query += f" ORDER BY {order_by}"

        # Add LIMIT clause if specified
        if limit:
            query += f" LIMIT {limit}"

        return query, query_params

    def insert(self, table: str, *, json: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Perform an insertion query, returning the JSON-encoded result as an object.

        Parameters
        ----------
        table : str
            The table name.
        json : Dict[str, Any] | None
            The data to insert.

        Returns
        -------
        List[Dict[str, Any]]
            The inserted rows.
        """
        if not json:
            return []

        try:
            # Get the table object
            table_obj = self._get_table(table)
            
            # Insert the data
            with self._session_factory() as session:
                # Construct the INSERT statement
                columns = ", ".join(json.keys())
                placeholders = ", ".join([f":{key}" for key in json.keys()])
                query = f"INSERT INTO {self.schema}.{table} ({columns}) VALUES ({placeholders}) RETURNING *"
                
                # Execute the query
                result = session.execute(text(query), json)
                rows = [dict(row._mapping) for row in result]
                session.commit()
                
                return rows
        except IntegrityError as e:
            # Handle integrity constraint violations (similar to 409 Conflict in HTTP)
            message = str(e)
            raise DatabaseOperationError(f"Database conflict on INSERT {table}", message) from e
        except SQLAlchemyError as e:
            # Handle other database errors (similar to 400 Bad Request in HTTP)
            error_json = {"message": str(e), "details": str(e.__cause__) if e.__cause__ else ""}
            raise DBQueryError(query=f"INSERT INTO {table}", method="INSERT", params=None, json=error_json) from e

    def update(
        self, table: str, *, json: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Perform an update query, returning the JSON-encoded result as an object.

        Parameters
        ----------
        table : str
            The table name.
        json : Dict[str, Any] | None
            The data to update.
        params : Dict[str, Any] | None
            The query parameters.

        Returns
        -------
        List[Dict[str, Any]]
            The updated rows.
        """
        if not json:
            return []

        try:
            # Get the table object
            table_obj = self._get_table(table)
            
            # Convert PostgREST-style params to SQLAlchemy query
            where_query, where_params = self._postgrest_params_to_sqlalchemy(table, params)
            
            # Extract the WHERE clause from the query
            where_clause = ""
            if " WHERE " in where_query:
                where_clause = "WHERE " + where_query.split(" WHERE ")[1]
            
            # Construct the UPDATE statement
            set_clause = ", ".join([f"{key} = :{key}" for key in json.keys()])
            query = f"UPDATE {self.schema}.{table} SET {set_clause}"
            if where_clause:
                query += f" {where_clause}"
            query += " RETURNING *"
            
            # Combine parameters
            combined_params = {**json, **where_params}
            
            # Execute the query
            with self._session_factory() as session:
                result = session.execute(text(query), combined_params)
                rows = [dict(row._mapping) for row in result]
                session.commit()
                
                return rows
        except IntegrityError as e:
            # Handle integrity constraint violations (similar to 409 Conflict in HTTP)
            message = str(e)
            raise DatabaseOperationError(f"Database conflict on UPDATE {table}", message) from e
        except SQLAlchemyError as e:
            # Handle other database errors (similar to 400 Bad Request in HTTP)
            error_json = {"message": str(e), "details": str(e.__cause__) if e.__cause__ else ""}
            raise DBQueryError(query=f"UPDATE {table}", method="PATCH", params=params, json=error_json) from e

    def select(self, table: str, *, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Perform a selection query, returning the JSON-encoded result as an object.

        Parameters
        ----------
        table : str
            The table name.
        params : Dict[str, Any] | None
            The query parameters.

        Returns
        -------
        List[Dict[str, Any]]
            The selected rows.
        """
        try:
            # Convert PostgREST-style params to SQLAlchemy query
            query, query_params = self._postgrest_params_to_sqlalchemy(table, params)
            
            # Execute the query
            with self._session_factory() as session:
                result = session.execute(text(query), query_params)
                rows = [dict(row._mapping) for row in result]
                
                return rows
        except IntegrityError as e:
            # Handle integrity constraint violations (similar to 409 Conflict in HTTP)
            message = str(e)
            raise DatabaseOperationError(f"Database conflict on SELECT {table}", message) from e
        except SQLAlchemyError as e:
            # Handle other database errors (similar to 400 Bad Request in HTTP)
            error_json = {"message": str(e), "details": str(e.__cause__) if e.__cause__ else ""}
            raise DBQueryError(query=f"SELECT FROM {table}", method="GET", params=params, json=error_json) from e

    def delete(self, table: str, *, params: Optional[Dict[str, Any]] = None) -> None:
        """Perform a deletion query.

        Parameters
        ----------
        table : str
            The table name.
        params : Dict[str, Any] | None
            The query parameters.
        """
        try:
            # Convert PostgREST-style params to SQLAlchemy query
            where_query, where_params = self._postgrest_params_to_sqlalchemy(table, params)
            
            # Extract the WHERE clause from the query
            where_clause = ""
            if " WHERE " in where_query:
                where_clause = "WHERE " + where_query.split(" WHERE ")[1]
            
            # Construct the DELETE statement
            query = f"DELETE FROM {self.schema}.{table}"
            if where_clause:
                query += f" {where_clause}"
            
            # Execute the query
            with self._session_factory() as session:
                session.execute(text(query), where_params)
                session.commit()
        except IntegrityError as e:
            # Handle integrity constraint violations (similar to 409 Conflict in HTTP)
            message = str(e)
            raise DatabaseOperationError(f"Database conflict on DELETE {table}", message) from e
        except SQLAlchemyError as e:
            # Handle other database errors (similar to 400 Bad Request in HTTP)
            error_json = {"message": str(e), "details": str(e.__cause__) if e.__cause__ else ""}
            raise DBQueryError(query=f"DELETE FROM {table}", method="DELETE", params=params, json=error_json) from e


# Function to create the global DB object
def create_db_access():
    """Create the global DB access object.

    Returns
    -------
    SQLAlchemyAccess
        The database access object.
    """
    # Get database connection parameters from environment variables or configuration
    db_uri = os.environ.get("DB_URI")
    #host = os.environ.get("PGHOST", "localhost")
    host = os.environ.get("PGHOST", "dlm_db")
    user = os.environ.get("PGUSER", "ska_dlm_admin")
    password = os.environ.get("PGPASSWORD", "password")
    #database = os.environ.get("PGDATABASE", CONFIG.DLM.dlm_db)
    database = "ska_dlm"
    schema = os.environ.get("PGSCHEMA", "public")
    
    # Create the DB access object
    db = SQLAlchemyAccess(
        db_uri=db_uri,
        host=host,
        user=user,
        password=password,
        database=database,
        schema=schema,
    )
    
    # Enter the context to initialize the session
    return db.__enter__()


# Global access object for convenience, already primed
DB = create_db_access()