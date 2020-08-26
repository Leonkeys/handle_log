import os
from shutil import copyfile
from manage import app
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DB_CONNECT = app.config['DB_CONNECT']
LOCAL_FILE_PATH = app.config['LOCAL_FILE_PATH']
engine = create_engine(DB_CONNECT)
Session = sessionmaker(bind=engine)


def freeswitch(core_uuid, unique_id_list, filename):
    """
    截取当前通话相关的日志&&freeswitch日志分析
    """
    if not unique_id_list or not unique_id_list:
        return
    local_file = LOCAL_FILE_PATH + "/" + filename
    local_log = LOCAL_FILE_PATH + "/freeswitch/" + core_uuid
    if not os.path.exists(LOCAL_FILE_PATH + "/freeswitch"):
        os.makedirs(LOCAL_FILE_PATH + "/freeswitch")
    with open(local_file, "rb") as old_local_file:

        with open(local_log, "wb") as new_local_file:
            for line_b in old_local_file:
                if line_b:
                    line_str = str(line_b, encoding="utf-8")
                    if line_str and any(channel_uuid in line_str for channel_uuid in unique_id_list):

                        # print(line_str)
                        new_local_file.write(line_b)
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


def write_node(handle_msg, mode):
    """
    写和前端交互的文本
    """
    call_type = handle_msg.get("call_type")
    state = handle_msg.get('state')
    err_msg = handle_msg.get('err_msg', "None")
    build_id = handle_msg.get("build_id")
    delay_time = handle_msg.get("delay_time")
    write_line = 0
    template_conf_file_path = app.config["TEMPLATE_CONF_FILE_PATH"]
    conf_file_path = app.config["CONF_FILE_PATH"]

    if mode == "freeswitch":
        write_line = 10
    if call_type == "audiosingle":
        if os.path.exists(conf_file_path + "singel_call_audio.conf"):
            os.remove(conf_file_path + "singel_call_audio.conf")
        copyfile(template_conf_file_path + "singel_call_audio.conf", conf_file_path + "singel_call_audio.conf")
        file_msg_list = []
        with open(conf_file_path + "singel_call_audio.conf", "r+") as conf_file_path:
            for conf_line in conf_file_path:
                file_msg_list.append(conf_line)
            file_msg_list[write_line] = state
            file_msg_list[4] = build_id
            file_msg_list[25] = delay_time
            conf_file_path.seek(0)
            for line in file_msg_list:
                conf_file_path.write(line)

