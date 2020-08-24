from sqlalchemy import Column, String, INTEGER, TEXT, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
BaseModel = declarative_base()


class log(BaseModel):

    __tablename__ = "log"

    id = Column(INTEGER, primary_key=True, autoincrement=True)
    channel_uuid = Column(String(64))
    core_uuid = Column(String(64))
    freeswitch_log = Column(TEXT)
    dispatcher_log = Column(TEXT)
    freeswitch_state = Column(String(64))
    dispatcher_state = Column(String(64))
    call_type = Column(String(64))
    event_time = Column(TIMESTAMP)
