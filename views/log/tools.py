import os
from manage import app
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DB_CONNECT = app.config['DB_CONNECT']
ALLOWED_EXTENSIONS = app.config['ALLOWED_EXTENSIONS']
LOCAL_FILE_PATH = app.config['LOCAL_FILE_PATH']
engine = create_engine(DB_CONNECT)
Session = sessionmaker(bind=engine)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def freeswitch(core_uuid, channel_call_uuid, filename):
    """
    截取当前通话相关的日志&&freeswitch日志分析
    """
    if not channel_call_uuid or not channel_call_uuid:
        return
    local_file = LOCAL_FILE_PATH + "/" + filename
    local_log = LOCAL_FILE_PATH + "/freeswitch/" + core_uuid + "/" + channel_call_uuid
    new_file_list = []
    if not os.path.exists(LOCAL_FILE_PATH + "/freeswitch/" + core_uuid):
        os.makedirs(LOCAL_FILE_PATH + "/freeswitch/" + core_uuid)
    with open(local_file, "rb") as old_local_file:

        with open(local_log, "wb") as new_local_file:
            for line_b in old_local_file:
                if line_b:
                    line_str = str(line_b, encoding="utf-8")
                    if line_str and channel_call_uuid in line_str:

                        # print(line_str)
                        new_local_file.write(line_b)
                        new_file_list.append(line_str)
    # TODO freeswitch日志分析

    return 1


def dispatcher():
    """
    dispatcher日志分析
    """
    pass


def mqtt():
    """
    mqtt日志分析
    """
    pass


def api():
    """
    api日志分析
    """
    pass


def write_node(func):
    """
    写和前端交互的文本
    """

