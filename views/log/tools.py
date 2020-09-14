import os
import json
from threading import Thread
from shutil import copyfile
from manage import app
from paho.mqtt import client as mqtt_client
# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker
from .common import common_log_analyse as com

# DB_CONNECT = app.config['DB_CONNECT']
caller_log_path = app.config["CALLER_LOG_PATH"]
LOCAL_FILE_PATH = app.config['LOCAL_FILE_PATH']
show_log_path = app.config["SHOW_LOG_PATH"]
mqtt_username = app.config["MQTT_USERNAME"]
mqtt_password = app.config["MQTT_PASSWORD"]
mqtt_host = app.config["MQTT_HOST"]
mqtt_port = app.config["MQTT_PORT"]
# engine = create_engine(DB_CONNECT)
# Session = sessionmaker(bind=engine)

log_result = {
    "caller": {
        "log_valid": "1",
        "call_type": ['audiosingle', '3509', '4500'],
        "state": "1",
        "err_msg": None,
        "build_id": "151123456",
        "delay_time": 0
    },
    "navita": {
        "log_valid": "1",
        "call_type": [None, None, None],
        "state": None,
        "err_msg": None,
        "build_id": "151123456",
        "delay_time": None
    },
    "dispatcher": {
        "log_valid": "1",
        "call_type": ["audiosingle", "3509", "4500"],
        "state": "1",
        "err_msg": None,
        "build_id": "151123456",
        "delay_time": 11111
    },
    "api": {
        "log_valid": "1",
        "call_type": ["audiosingle", "3509", "4500"],
        "state": "1",
        "err_msg": None,
        "build_id": "151123456",
        "delay_time": 10000
    },
    "mqtt": {
        "log_valid": "1",
        "call_type": ["audiosingle", "3509", "4500"],
        "state": "1",
        "err_msg": None,
        "build_id": "151123456",
        "delay_time": 27017
    },
    "callee": {
        "log_valid": "1",
        "call_type": ["audiosingle", "3509", "4500"],
        "state": "1",
        "err_msg": None,
        "build_id": "151123456",
        "delay_time": 27017
    },
    "analyse_error": None}


def caller(core_uuid, caller_username):
    Thread(target=public_msg, args=(core_uuid, caller_username)).start()
    caller_log_file_path = caller_log_path + core_uuid + "/caller_{}_log".format(caller_username)
    caller_log_tmp_file_path = caller_log_path + core_uuid + "/tmp/caller_{}_log".format(caller_username)
    msg = check_file(caller_log_tmp_file_path)
    if not msg:
        caller_log = log_result.get("caller")
        caller_log["err_msg"] = msg
        return write_node(log_result.get('caller'), "caller", [])
    log_list = list()
    com.analyse_main(log_result, caller_log_tmp_file_path)
    with open(caller_log_tmp_file_path, "rb") as caller_log_tmp_file_path:
        for line_b in caller_log_tmp_file_path:
            if line_b:
                log_list.append(line_b)
    write_node(log_result.get("caller"), "caller",  log_list)
    call_log_backup(caller_log_file_path, caller_log_tmp_file_path)


def freeswitch(core_uuid, unique_id_list, filename):
    """
    截取当前通话相关的日志&&freeswitch日志分析
    """
    log_list = list()
    if not unique_id_list:
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
                        log_list.append(line_b)
                        new_local_file.write(line_b)
    com.analyse_main(log_result, local_log)
    mode = "freeswitch"
    print(log_result)
    # log_result.get('navita').get('call_type')[0] = "audiogroup"
    write_node(log_result.get('navita'), mode, log_list)


def dispatcher(core_uuid, unique_id_list, filename):
    """
    dispatcher日志分析
    """

    log_list = list()
    if not unique_id_list:
        return
    local_file = LOCAL_FILE_PATH + "/" + filename
    local_log = LOCAL_FILE_PATH + "/dispatcher/" + core_uuid
    if not os.path.exists(LOCAL_FILE_PATH + "/dispatcher"):
        os.makedirs(LOCAL_FILE_PATH + "/dispatcher")

    with open(local_file, "rb") as old_local_file:
        with open(local_log, "wb") as new_local_file:
            for line_b in old_local_file:
                if line_b:
                    # line_str = str(line_b, encoding="utf-8")
                    # if line_str and any(channel_uuid in line_str for channel_uuid in unique_id_list):
                    # print(line_str)
                    log_list.append(line_b)
                    new_local_file.write(line_b)
    com.analyse_main(log_result, local_log)
    mode = "dispatcher"
    write_node(log_result.get("dispatcher"), mode, log_list)


def api(core_uuid, unique_id_list, filename_list):
    """
    api日志分析：欣欣接口调用数据库的日志分析
    """
    log_list = list()
    if not unique_id_list:
        return
    if isinstance(filename_list, list):
        for filename in filename_list:
            old_local_file = LOCAL_FILE_PATH + "/" + filename
            new_local_log = LOCAL_FILE_PATH + "/api/" + core_uuid
            if not os.path.exists(LOCAL_FILE_PATH + "/api"):
                os.makedirs(LOCAL_FILE_PATH + "/api")

            with open(old_local_file, "rb") as old_local_file:
                with open(new_local_log, "wb") as new_local_file:
                    for line_b in old_local_file:
                        if line_b:
                            line_str = str(line_b, encoding="utf-8")
                            if line_str:
                                log_list.append(line_b)
                                new_local_file.write(line_b)
            com.analyse_main(log_result, new_local_log)
            log_list = [
                b"api\n",
                b"aaaaaaaaaaaaaaaaaaaaa\n",
                b"ppppppppppppppppppppp\n",
                b"iiiiiiiiiiiiiiiiiiiii\n"
            ]
            mode = "api"
            write_node(log_result.get("api"), mode, log_list)


def mqtt(core_uuid, unique_id_list, filename):
    """
    mqtt日志分析
    mqtt日志分析指mqtt消息通道收到的消息的分析不是本身服务运行状态分析
    """
    mode = "mqtt"
    log_list = [
        b"mqtt\n",
        b"qqqqqqqqqqqqqqqqqqqqqqq\n",
        b"wwwwwwwwwwwwwwwwwwwwwwwww\n",
        b"eeeeeeeeeeeeeeeeeeeeeeeeeee\n",
        b"rrrrrrrrrrrrrrrrrrrrrrrrrrrr\n"
    ]
    write_node(log_result.get("mqtt"), mode, log_list)


def callee(core_uuid, unique_id_list):
    mode = "callee"
    log_list = [
        b"callee\n"
        b"qqqqqqqqqqqqqqqqqqqqqqq\n",
        b"wwwwwwwwwwwwwwwwwwwwwwwww\n",
        b"eeeeeeeeeeeeeeeeeeeeeeeeeee\n",
        b"rrrrrrrrrrrrrrrrrrrrrrrrrrrr\n"
    ]
    write_node(log_result.get("callee"), mode, log_list)


def write_node(handle_msg, mode, log_list):
    """
    写和前端交互的文本  && 和需要展示的log日志文件
    """
    call_type = handle_msg.get("call_type", None)

    # call_type_list = [audiosingle, videosingle, audiogroup, videogroup, ...]
    # 视频单呼组呼，音频单呼组呼。
    if call_type[0] in ["audiosingle", "videosingle", "videogroup", "audiogroup", "singlecall"]:
        write_conf(mode, handle_msg)
        write_log(handle_msg, log_list, mode)


def write_conf(mode, handle_msg):
    """
    单呼 组呼写conf文件
    """
    call_type = handle_msg.get("call_type")
    state = handle_msg.get('state', "0")
    delay_time = handle_msg.get("delay_time")
    template_conf_file_path = app.config["TEMPLATE_CONF_FILE_PATH"]
    conf_file_path = app.config["CONF_FILE_PATH"]
    if mode == "caller":
        mode_write_line = 6
        delay_time_write_line = 34
    elif mode == "freeswitch":
        mode_write_line = 8
        delay_time_write_line = 36
    elif mode == "dispatcher":
        mode_write_line = 24
        delay_time_write_line = 38
    elif mode == "api":
        mode_write_line = 10
        delay_time_write_line = 40
    elif mode == "mqtt":
        mode_write_line = 12
        delay_time_write_line = 42
    else:
        # callee
        mode_write_line = 14
        delay_time_write_line = 44
    build_id = None
    if call_type[0] in ["singlecall", "audiosingle"]:
        if mode == "caller":
            build_id = call_type[0] + "*" + call_type[1] + "*" + call_type[2] + ".00"
        conf_file_name = "start_single_audio_call.conf"
    elif call_type[0] == "videosingle":
        if mode == "caller":
            build_id = call_type[0] + "*" + call_type[1] + "*" + call_type[2] + ".00"
        conf_file_name = "start_single_video_call.conf"

    elif call_type[0] == "audiogroup":
        if mode == "caller":
            build_id = handle_msg.get("build_id", "-")
        conf_file_name = "start_group_audio_call.conf"
    elif call_type[0] == "videogroup":
        if mode == "caller":
            build_id = handle_msg.get("build_id", "-")
        conf_file_name = "start_group_video_call.conf"
    else:
        build_id = None
        conf_file_name = None

    if mode == "caller" and os.path.exists(conf_file_path + conf_file_name):
        os.remove(conf_file_path + conf_file_name)
        copyfile(template_conf_file_path + conf_file_name, conf_file_path + conf_file_name)
    file_msg_list = []
    with open(conf_file_path + conf_file_name, "r+") as conf_file_path:
        for conf_line in conf_file_path:
            file_msg_list.append(conf_line)
        if state:
            file_msg_list[mode_write_line - 1] = state + "\n"
        if build_id:
            file_msg_list[3] = file_msg_list[15]
            file_msg_list[15] = build_id + "\n"
        if delay_time:
            file_msg_list[delay_time_write_line - 1] = str(delay_time) + "\n"
            old_delay_time = int(file_msg_list[45].replace("\n", ""))
            file_msg_list[45] = str(old_delay_time + int(delay_time)) + "\n"
        conf_file_path.seek(0)
        for line in file_msg_list:
            conf_file_path.write(line)


def write_log(handle_msg, log_list, mode):
    """
    编辑需要展示的日志文件内容
    单呼 组呼 写日志文件
    """
    err_msg = handle_msg.get("err_msg")
    call_type = handle_msg.get("call_type")
    if call_type[0] in ["audiosingle", "singlecall"]:
        mode_show_log_path = show_log_path + "start_single_audio_call/" + mode + "/"
    elif call_type[0] == "videosingle":
        mode_show_log_path = show_log_path + "start_single_video_call/" + mode + "/"
    elif call_type[0] == "audiogroup":
        mode_show_log_path = show_log_path + "start_group_audio_call/" + mode + "/"
    else:
        # videogroup
        mode_show_log_path = show_log_path + "start_group_video_call/" + mode + "/"
    if err_msg:
        err_log_file = mode_show_log_path + "err_log"
        with open(err_log_file, "w") as err_log_file:
            err_log_file.write(err_msg)
    if log_list:
        whole_log_file = mode_show_log_path + "whole_log"
        with open(whole_log_file, "wb") as whole_log_file:
            for log in log_list:
                whole_log_file.write(log)
    if handle_msg:
        handle_log_file = mode_show_log_path + "handle_log"
        with open(handle_log_file, "w") as handle_log_file:
            handle_msg_str = json.dumps(handle_msg)
            handle_log_file.write(handle_msg_str)


def public_msg(core_uuid, caller_username):
    client = mqtt_client.Client()
    client.connect(host=mqtt_host, port=mqtt_port, keepalive=600)
    client.username_pw_set(mqtt_username, mqtt_password)
    caller_log_file_path = caller_log_path + core_uuid + "/caller_{}_log".format(caller_username)
    lines = 0
    if os.path.exists(caller_log_file_path):
        lines = get_line(caller_log_file_path)
    msg = {
        "offset": {
            "start_line": lines,
        },
    }
    msg_str = json.dumps(msg)
    client.publish("/log_analyse/{}".format(caller_username), msg_str, 1)


def check_file(call_log_path):
    '''
    检查终端日志文件是否上传成功。
    '''
    for i in range(10):
        if os.path.exists(call_log_path):
            return
    return "terminal log upload failed"


def call_log_backup(call_log_file_path, call_log_tmp_file_path):
    with open(call_log_file_path, "ab") as call_log_file_path:
        call_log_file_path.write(call_log_tmp_file_path)
    os.remove(call_log_tmp_file_path)


def get_line(call_log_file_path):
    count = 0
    with open(call_log_file_path, "r") as call_log_file_path:
        buffer = call_log_file_path.read(8*1024*1024)
        if not buffer:
            return count
        count += buffer.count("\n")


def clean_line():
    import time
    stamp = time.time()
    print('clean line%s' % stamp)
