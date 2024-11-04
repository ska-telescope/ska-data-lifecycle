"""dlm_storage REST client"""

import json

import requests

from ska_dlm.exceptions import (
    InvalidQueryParameters,
    UnmetPreconditionForOperation,
    ValueAlreadyInDB,
)


def dlm_raise_for_status(response: requests.Response):
    """Raises a DLM exception for error response status codes."""
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        if exc.response.status_code == 422:  # Unprocessable Content
            try:
                obj = json.loads(response.text)
            except json.JSONDecodeError as dexc:
                raise dexc from exc
            if "exec" in obj:
                match obj["exec"]:
                    case "ValueAlreadyInDB":
                        raise ValueAlreadyInDB(obj["message"]) from exc
                    case "InvalidQueryParameters":
                        raise InvalidQueryParameters(obj["message"]) from exc
                    case "UnmetPreconditionForOperation":
                        raise UnmetPreconditionForOperation(obj["message"]) from exc
        raise
