"""DB access classes, interfaces and utilities."""

import logging
from sqlalchemy import MetaData, Table, create_engine, select
from sqlalchemy.orm import sessionmaker

# from .. import CONFIG

logger = logging.getLogger(__name__)


# engine = create_engine("postgresql+psycopg2://user:password@localhost/dbname")
db_direct_engine = create_engine("postgresql+psycopg2://ska_dlm_admin:password@dlm_db:5432/ska_dlm")
Session = sessionmaker(bind=db_direct_engine)
DB_DIRECT_SESSION = Session()