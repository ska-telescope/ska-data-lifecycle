#from sqlalchemy import select
#from sqlalchemy.orm import sessionmaker
#from ska_dlm.dlm_db.db_direct_access import DB_DIRECT_SESSION, db_direct_engine
import inflect
from datetime import timedelta

import ska_dlm.dlm_request.dlm_request_requests as dlm_request
import ska_dlm.data_item as data_item

#session = sessionmaker(bind=db_direct_engine)()
#stmt = select(DataItem).params(params=params)
#results = session.execute(stmt).scalars().all()
#engine = inflect.engine()
#success = True
"""Test data_item init."""
#from ska_dlm.dlm_ingest.dlm_ingest_requests import init_data_item
#engine = inflect.engine()
#success = True
#for i in range(1, 51, 1):
#    ordinal = engine.number_to_words(engine.ordinal(i))
#    uid = init_data_item(f"this/is/the/{ordinal}/test/item")
#    if uid is None:
#        success = False




uid = dlm_request.query_data_item()[0]["uid"]
#logger.info(f"uid: {uid}, uidtype: {type(uid)}")
ret = data_item.set_state(uid=uid, state="READY")
#logger.info(f"ret: {ret}, rettype: {type(ret)}")
#logger.info(f"timedelta: {timedelta(0)}")

test=dlm_request.query_expired(offset=timedelta(0))
test2=dlm_request.query_expired(offset=timedelta(days=1))
print(test)
print(test2)
