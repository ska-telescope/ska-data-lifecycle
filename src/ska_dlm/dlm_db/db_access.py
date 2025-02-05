"""DB access classes, interfaces and utilities."""

import contextlib
import logging

import requests

from .. import CONFIG
from ..exceptions import DataLifecycleError

logger = logging.getLogger(__name__)


class DBQueryError(DataLifecycleError):
    """An error while performing a database query."""

    def __init__(self, url: str, method: str, params: dict | list | None, json: dict | None):
        """Create a DBQueryError.

        Parameters
        ----------
        url : str
            The query url.
        method : str
            The query HTTP method.
        params : dict | tuple | None
            The query HTTP params.
        json : object | None
            The query JSON body.
        """
        self.url = url
        self.method = method
        self.params = params
        self.json = json

    def __repr__(self):
        """Python representation."""
        return (
            f"DBQueryError("
            f"url={self.url!r}, "
            f"method={self.method!r}, "
            f"params={self.params!r}, "
            f"json={self.json!r})"
        )

    def __str__(self):
        """Pretty string representation."""
        # print postgrest response json
        if self.json and "message" in self.json and "message" in self.json:
            return f"DBQueryError: {self.json['message']}\n\tdetails: {self.json['details']}"
        return repr(self)


_DEFAULT_HEADERS = {"Prefer": "missing=default, return=representation"}


class PostgRESTAccess(contextlib.AbstractContextManager):
    """SQL database client accessed through the PostgREST HTTP API."""

    def __init__(self, api_url: str, timeout: int | float = 10, headers: dict | None = None):
        """Create the DB access."""
        self.api_url = api_url
        self._session = requests.Session()
        self._session.headers = dict(headers if headers else _DEFAULT_HEADERS)
        self._timeout = timeout

    def __enter__(self):
        """Enter the request session."""
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        """Close the underlying requests session."""
        self._session.close()

    def insert(self, table: str, *, json: object | None) -> list:
        """Perform an insertion query, returning the JSON-encoded result as an object."""
        return self._query(table, "POST", json=json)

    def update(
        self, table: str, *, json: object | None, params: dict | list | None = None
    ) -> bool | list[dict]:
        """Perform an update query, returning the JSON-encoded result as an object."""
        result = self._query(table, "PATCH", params=params, json=json)
        return True if result is None else result

    def select(self, table: str, *, params: dict | list | None = None) -> list[dict]:
        """Perform a selection query, returning the JSON-encoded result as an object."""
        return self._query(table, "GET", params=params)

    def delete(self, table: str, *, params: dict | list | None = None) -> None:
        """Perform a deletion query."""
        self._query(table, "DELETE", params=params)

    def _query(
        self,
        table: str,
        method: str,
        params: dict | list | None = None,
        json: dict | None = None,
        **kwargs,
    ) -> list[dict]:
        url = f"{self.api_url}/{table}"
        try:
            response = self._session.request(
                method, url, params=params, json=json, timeout=self._timeout, **kwargs
            )
            response.raise_for_status()
        except requests.RequestException as ex:
            if ex.response is None:
                raise
            match ex.response.status_code:
                case 400:
                    json = ex.response.json()
                    raise DBQueryError(url=url, method=method, params=params, json=json) from ex
                case _:
                    raise
        return response.json()


# global access object for convenience, already primed
DB = PostgRESTAccess(CONFIG.REST.base_url)
# pylint: disable-next=unnecessary-dunder-call
DB.__enter__()
