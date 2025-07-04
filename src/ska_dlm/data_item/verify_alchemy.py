# pip install sqlalchemy psycopg[binary]

######
# Set Up SQLAlchemy Engine, Base, and Session
######
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import declarative_base, sessionmaker, registry

# Connect to the DB
engine = create_engine("postgresql+psycopg://user:password@localhost:5432/dbname")

# ORM Base class (for dynamic table mapping)
Base = declarative_base()

# Create a session factory
Session = sessionmaker(bind=engine)
session = Session()


######
# Reflect the Table and Generate ORM-Like Classes
######
from sqlalchemy.orm import mapper
from sqlalchemy import Table

# Use this for dynamic class creation
class_registry = {}

def generate_orm_class(table_name: str):
    metadata = MetaData()
    metadata.reflect(bind=engine, only=[table_name])
    table = metadata.tables[table_name]

    # Dynamically create a new ORM class
    class_name = table_name.capitalize()
    orm_class = type(class_name, (Base,), {"__table__": table})

    # Optional: Register for reuse
    class_registry[table_name] = orm_class
    return orm_class


#######
# Use the Generated ORM Class
#######
# Create an ORM class from an existing table
DlmTable = generate_orm_class("dlm_table")  # Replace with actual table name

# Query it using ORM
results = session.query(DlmTable).filter(DlmTable.status == "ready").all()

for row in results:
    print(row.id, row.status)



#######
# Once you call generate_orm_class("dlm_table"), the returned class behaves just like a regular ORM-mapped class
#######



#### Let’s say you've already created the ORM-like class from a table:
DlmTable = generate_orm_class("dlm_table")


#### Now, to query for rows where a column (e.g. "status") equals "ready":
from sqlalchemy.orm import Session

# Create a session
with Session(engine) as session:
    results = session.query(DlmTable).filter(DlmTable.status == "ready").all()

for row in results:
    print(row.id, row.status)


#### Generalized Query Using a params Dict
#### If your filters come from a params dictionary:
params = {"status": "ready", "priority": "high"}
#### then
from sqlalchemy import and_

with Session(engine) as session:
    # Build filter conditions
    filters = [getattr(DlmTable, key) == value for key, value in params.items() if hasattr(DlmTable, key)]

    results = session.query(DlmTable).filter(and_(*filters)).all()

for row in results:
    print(row)


#### Notes:
#### getattr(DlmTable, key) gets the column dynamically.
#### hasattr(...) guards against missing or invalid columns.
#### If you want to support operators like __gt, __in, etc., you can parse the keys accordingly — let me know if you want that logic.



#### auto code        with Session(engine) as session:




#### Great — here’s how to extend the dynamic SQLAlchemy ORM query builder to support richer operators like: