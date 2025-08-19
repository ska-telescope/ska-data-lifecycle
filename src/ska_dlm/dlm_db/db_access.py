"""DB access classes, interfaces and utilities."""

import contextlib
import logging

from .. import CONFIG
from .db_access_sqlalchemy import SQLAlchemyAccess

logger = logging.getLogger(__name__)

# Import the DB object and DBQueryError from db_access_sqlalchemy
from .db_access_sqlalchemy import DB, DBQueryError

# Re-export the DB object and DBQueryError for backward compatibility
__all__ = ["DB", "DBQueryError"]
