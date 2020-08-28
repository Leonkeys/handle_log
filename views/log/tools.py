import os
from shutil import copyfile
from manage import app
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .common import common_log_analyse  as com



DB_CONNECT = app.config['DB_CONNECT']
LOCAL_FILE_PATH = app.config['LOCAL_FILE_PATH']
engine = create_engine(DB_CONNECT)
Session = sessionmaker(bind=engine)

log_result={ "navita":{"log_valid":"1","call_type":[None,None,None], "state":None, "err_msg":None,"build_id":None,"delay_time":None}, "dis":{ "log_valid":"1", "dis_start":"nonono"}, "analyse_error":None}





# def caller():
#     # TODO 呼叫方日志分析
#     msg = {
#         "":""
#     }
#
#     write_node(msg, mode="caller")

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

    handle_msg = {
        "call_type": "audiosingle",
        "state": "1",
        "err_msg": "",
        "build_id": "audiosingle*3509*3510.00",
        "delay_time": "0.666"
    }
    mode = "freeswitch"
    write_node(handle_msg, mode)


def dispatcher(core_uuid, unique_id_list, filename):
    """
    dispatcher日志分析
    """

    if not unique_id_list or not unique_id_list:
        return
    local_file = LOCAL_FILE_PATH + "/" + filename
    local_log = LOCAL_FILE_PATH + "/dispatcher/" + core_uuid
    if not os.path.exists(LOCAL_FILE_PATH + "/dispatcher"):
        os.makedirs(LOCAL_FILE_PATH + "/dispatcher")

    with open(local_file, "rb") as old_local_file:
        with open(local_log, "wb") as new_local_file:
            for line_b in old_local_file:
                if line_b:
                    line_str = str(line_b, encoding="utf-8")
                    if line_str and any(channel_uuid in line_str for channel_uuid in unique_id_list):
                        # print(line_str)
                        new_local_file.write(line_b)
    # TODO dispatcher日志分析

    handle_msg = {
        "call_type": "audiosingle",
        "state": "1",
        "err_msg": "",
        "build_id": "audiosingle*3509*3510.00",
        "delay_time": "0.666"
    }
    mode = "dispatcher"
    write_node(handle_msg, mode)


def mqtt():
    """
    mqtt日志分析
    """
    pass


def write_node(handle_msg, mode):
    """
    写和前端交互的文本
    """
    call_type = handle_msg.get("call_type", None)
    state = handle_msg.get('state', "0")
    err_msg = handle_msg.get('err_msg', "None")
    build_id = handle_msg.get("build_id", "")
    delay_time = handle_msg.get("delay_time", "")
    write_line = 0

    if mode == "caller":
        write_line = 7
    if mode == "freeswitch":
        write_line = 10
    if mode == "dispatcher":
        write_line = 13
    if mode == "callee":
        write_line = 22

    # call_type_list = [audiosingle, videosingle, audiogroup, videogroup, ...]
    # 视频单呼组呼，音频单呼组呼。
    if call_type in ["audiosingle", "vediosingle", "audiosingle", "vediosingle"]:
        n_call(call_type, mode, state, build_id, delay_time, write_line)


def n_call(call_type, mode, state, build_id=None, delay_time=None, write_line=None):

    template_conf_file_path = app.config["TEMPLATE_CONF_FILE_PATH"]
    conf_file_path = app.config["CONF_FILE_PATH"]
    conf_file_name = "single_call_audio.conf" if call_type == "audiosingle" else "single_call_video.conf"
    if mode == "caller" and os.path.exists(conf_file_path + conf_file_name):
        os.remove(conf_file_path + conf_file_name)
    copyfile(template_conf_file_path + conf_file_name, conf_file_path + conf_file_name)
    file_msg_list = []
    with open(conf_file_path + conf_file_name, "r+") as conf_file_path:
        for conf_line in conf_file_path:
            file_msg_list.append(conf_line)
        if state:
            file_msg_list[write_line] = state + "\n"
        if build_id:
            file_msg_list[3] = build_id + "\n"
        if delay_time:
            old_delay_time = float(file_msg_list[25].replace("\n", ""))
            file_msg_list[25] = str(old_delay_time + float(delay_time)) + "\n"
        conf_file_path.seek(0)
        for line in file_msg_list:
            conf_file_path.write(line)

