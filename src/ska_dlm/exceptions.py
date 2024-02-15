"""Common exceptions raised by ska-dlm components."""


class DataLifecycleError(Exception):
    """Base class for all ska-dlm exceptions."""


class InvalidQueryParameters(DataLifecycleError, ValueError):
    """An invalid set of parameters has been given to perform a query."""


class ValueAlreadyInDB(DataLifecycleError, ValueError):
    """A value that is meant to be inserted already exists in the database."""


class UnmetPreconditionForOperation(DataLifecycleError, RuntimeError):
    """A pre-condition for a certain operation is not met."""
