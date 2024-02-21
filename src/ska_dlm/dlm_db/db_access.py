"""DB access classes, interfaces and utilities."""
import contextlib
import logging

import requests

from .. import CONFIG
from ..exceptions import DataLifecycleError

logger = logging.getLogger(__name__)


class DBQueryError(DataLifecycleError):
    """An error while performing a database query."""

    def __init__(self, url: str, method: str, params: dict | tuple | None, json: object | None):
        """Create a DBQueryError."""
        self.url = url
        self.method = method
        self.params = params
        self.json = json

    def __str__(self):
        """Convert to string."""
        return f"DBQueryError(url='{self.url}', method='{self.method}', params={self.params})"


_DEFAULT_HEADERS = {"Prefer": "missing=default, return=representation"}


class PostgRESTAccess(contextlib.AbstractContextManager):
    """DB acesss through the PostREST HTTP API."""

    def __init__(self, api_url: str, timeout: int | float = 10, headers: dict | None = None):
        """Create the DB access."""
        self._api_url = api_url
        self._session = requests.Session()
        self._session.headers = dict(headers if headers else _DEFAULT_HEADERS)
        self._session.timeout = timeout

    def __exit__(self, _exc_type, _exc_value, _traceback) -> bool | None:
        """Close the underlying requests session."""
        self._session.close()

    def insert(self, table: str, *, json: object | None):
        """Perform an insertion query, returning the JSON-encoded result as an object."""
        return self._query(table, "POST", json=json)

    def update(self, table: str, *, json: object | None, params: dict | list | None = None):
        """Perform an update query, returning the JSON-encoded result as an object."""
        result = self._query(table, "PATCH", params=params, json=json)
        return True if result is None else result

    def select(self, table: str, *, params: dict | list | None = None):
        """Perform a selection query, returning the JSON-encoded result as an object."""
        return self._query(table, "GET", params=params)

    def delete(self, table: str, *, params: dict | list | None = None):
        """Perform a deletion query."""
        self._query(table, "DELETE", params=params)

    def _query(
        self,
        table: str,
        method: str,
        params: dict | list | None = None,
        json: object | None = None,
        **kwargs,
    ):
        url = f"{self._api_url}/{table}"
        try:
            response = self._session.request(method, url, params=params, json=json, **kwargs)
            response.raise_for_status()
        except Exception as ex:
            raise DBQueryError(url=url, method=method, params=params, json=json) from ex
        return response.json()


# global access object for convenience, already primed
DB = PostgRESTAccess(CONFIG.REST.base_url)
# pylint: disable-next=unnecessary-dunder-call
DB.__enter__()
