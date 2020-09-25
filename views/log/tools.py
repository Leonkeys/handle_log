import os
import threading
import logging
import json
import time
import redis
from shutil import copyfile, move
from manage import app
from paho.mqtt import client as mqtt_client
# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker
from .common import common_log_analyse as com

# DB_CONNECT = app.config['DB_CONNECT']
redis_host = app.config["REDIS_HOST"]
redis_port = app.config["REDIS_PORT"]
server_ip = app.config["SERVER_IP"]
server_user = app.config["USER"]
server_password = app.config["PASSWORD"]
local_file_path = app.config['LOCAL_FILE_PATH']
show_log_path = app.config["SHOW_LOG_PATH"]
mqtt_username = app.config["MQTT_USERNAME"]
mqtt_password = app.config["MQTT_PASSWORD"]
mqtt_host = app.config["MQTT_HOST"]
mqtt_port = app.config["MQTT_PORT"]
# engine = create_engine(DB_CONNECT)
# Session = sessionmaker(bind=engine)
lock = threading.Lock()
log_result = {
    "caller": {
        "call_id": None,
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
        "build_id": None,
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
        "call_id": "",
        "log_valid": "1",
        "call_type": ["audiosingle", "3509", "4500"],
        "state": {},
        "err_msg": None,
        "build_id": "151123456",
        "delay_time": 27017
    },
    "analyse_error": None}


def get_server_log(remote_path, local_file=None):
    """
    copy server running log
    request:
        remote_path  服务器端日志路径，根据所传日志动态传入
        local_path   本地日志存储路径

    """
    try:
        password = app.config['PASSWORD']
        user = app.config['USER']
        ip = app.config['SERVER_IP']
        local_path = local_file if local_file else local_file_path
        if isinstance(remote_path, list):
            for path in remote_path:
                info = os.system("sshpass -p {password} rsync {user}@{ip}:{remote_path} {local_path}/".format(
                    password=password, user=user, ip=ip, remote_path=path, local_path=local_path))
        elif isinstance(remote_path, str):

            info = os.system("sshpass -p {password} rsync {user}@{ip}:{remote_path} {local_path}/".format(
                password=password, user=user, ip=ip, remote_path=remote_path, local_path=local_path))
        # return {"a": info}
    except Exception as e:
        logging.warning(e)
        print("server log is not found:{}".format(remote_path))


def caller(core_uuid, caller_username, variable_sip_call_id):
    public_msg(core_uuid, caller_username)
    # Thread(target=public_msg, args=(core_uuid, caller_username)).start()
    caller_log_file_path = local_file_path + core_uuid + "/{}_log".format(caller_username)
    caller_log_tmp_file_path = local_file_path + "/tmp/{}_log".format(caller_username)
    msg = check_file(caller_log_tmp_file_path)
    if msg:
        caller_log = log_result.get("caller")
        caller_log["err_msg"] = msg
        return write_node(log_result.get('caller'), "caller", [])
    log_list = list()
    log_result.get("caller")["call_id"] = variable_sip_call_id
    # com.analyse_main(log_result, caller_log_tmp_file_path)
    start_line_str, start_bytes_str = _get_start_sign(caller_username)
    temp_file_bytes = os.path.getsize(caller_log_tmp_file_path)
    print(temp_file_bytes)
    start_line = int(start_line_str)
    start_bytes = int(start_bytes_str)
    start_bytes += temp_file_bytes
    with open(caller_log_tmp_file_path, "rb") as caller_log_tmp_file:
        for line_b in caller_log_tmp_file:
            if line_b:
                log_list.append(line_b)
                start_line += 1

    _set_start_sign(caller_username, start_line, start_bytes)
    write_node(log_result.get("caller"), "caller",  log_list)
    call_log_backup(caller_log_file_path, caller_log_tmp_file_path)


def freeswitch(core_uuid, unique_id_list, filename):
    """
    截取当前通话相关的日志&&freeswitch日志分析
    """
    log_list = list()
    if not unique_id_list:
        return
    local_file = local_file_path + "/" + filename
    local_log = local_file_path + "/freeswitch/" + core_uuid
    if not os.path.exists(local_file_path + "/freeswitch"):
        os.makedirs(local_file_path + "/freeswitch")
    with open(local_file, "rb") as old_local_file:

        with open(local_log, "wb") as new_local_file:
            for line_b in old_local_file:
                if line_b:
                    line_str = str(line_b, encoding="utf-8")
                    if line_str and any(channel_uuid in line_str for channel_uuid in unique_id_list):
                        log_list.append(line_b)
                        new_local_file.write(line_b)
    # com.analyse_main(log_result, local_log)
    mode = "freeswitch"
    print(log_result)
    write_node(log_result.get('navita'), mode, log_list)


def dispatcher(core_uuid, unique_id_list, filename):
    """
    dispatcher日志分析
    """

    log_list = list()
    if not unique_id_list:
        return
    local_file = local_file_path + "/" + filename
    local_log = local_file_path + "/dispatcher/" + core_uuid
    if not os.path.exists(local_file_path + "/dispatcher"):
        os.makedirs(local_file_path + "/dispatcher")

    with open(local_file, "rb") as old_local_file:
        with open(local_log, "wb") as new_local_file:
            for line_b in old_local_file:
                if line_b:
                    # line_str = str(line_b, encoding="utf-8")
                    # if line_str and any(channel_uuid in line_str for channel_uuid in unique_id_list):
                    log_list.append(line_b)
                    new_local_file.write(line_b)
    # com.analyse_main(log_result, local_log)
    mode = "dispatcher"
    write_node(log_result.get("dispatcher"), mode, log_list)


def api(core_uuid, unique_id_list, filename):
    """
    api日志分析：欣欣接口调用数据库的日志分析
    """
    log_list = list()
    if not unique_id_list:
        return
    old_local_file = local_file_path + "/" + filename
    new_local_log = local_file_path + "/api/" + core_uuid
    if not os.path.exists(local_file_path + "/api"):
        os.makedirs(local_file_path + "/api")

    with open(old_local_file, "rb") as old_local_file:
        with open(new_local_log, "wb") as new_local_file:
            for line_b in old_local_file:
                if line_b:
                    line_str = str(line_b, encoding="utf-8")
                    if line_str:
                        log_list.append(line_b)
                        new_local_file.write(line_b)
    # com.analyse_main(log_result, new_local_log)
    mode = "api"
    write_node(log_result.get("api"), mode, log_list)


def mqtt(core_uuid, unique_id_list, filename):
    """
    mqtt日志分析
    mqtt日志分析指mqtt消息通道收到的消息的分析不是本身服务运行状态分析
    """
    log_list = list()
    if not unique_id_list:
        return

    local_file = local_file_path + "/" + filename
    local_log = local_file_path + "/mqtt/" + core_uuid
    if not os.path.exists(local_file_path + "/mqtt"):
        os.makedirs(local_file_path + "/mqtt")
    move(local_file, local_log)
    with open(local_log, "rb") as local_log_obj:
        for line in local_log_obj:
            log_list.append(line)
    # com.analyse_main(log_result, local_log)
    mode = "mqtt"
    write_node(log_result.get("mqtt"), mode, log_list)


def callee(core_uuid, callee_username, variable_sip_call_id):
    public_msg(core_uuid, callee_username)
    callee_log_file_path = local_file_path + core_uuid + "/callee_{}_log".format(callee_username)
    callee_log_tmp_file_path = local_file_path + core_uuid + "/tmp/callee_{}_log".format(callee_username)
    msg = check_file(callee_log_tmp_file_path)
    if msg:
        callee_log = log_result.get("callee")
        callee_log["err_msg"] = msg
        return write_node(log_result.get('callee'), "callee", [])
    log_result.get("callee")["variable_sip_call_id"] = variable_sip_call_id
    # com.analyse_main(log_result, callee_log_tmp_file_path)
    start_line_str, start_bytes_str = _get_start_sign(callee_username)
    temp_file_bytes = os.path.getsize(callee_log_tmp_file_path)
    start_line = int(start_line_str)
    start_bytes = int(start_bytes_str)
    start_bytes += temp_file_bytes
    log_list = list()
    with open(callee_log_tmp_file_path, "rb") as callee_log_tmp_file:
        for line_b in callee_log_tmp_file:
            if line_b:
                log_list.append(line_b)
                start_line += 1

    _set_start_sign(callee_username, start_line, start_bytes)
    write_node(log_result.get("callee"), "callee",  log_list)
    call_log_backup(callee_log_file_path, callee_log_tmp_file_path)


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
        conf_file_name = ""

    if mode == "caller" and os.path.exists(conf_file_path + conf_file_name):
        os.remove(conf_file_path + conf_file_name)
        copyfile(template_conf_file_path + conf_file_name, conf_file_path + conf_file_name)
    file_msg_list = []
    with open(conf_file_path + conf_file_name, "r+") as conf_file_path:
        for conf_line in conf_file_path:
            file_msg_list.append(conf_line)
        if state:
            if isinstance(state, dict):
                file_msg_list[mode_write_line - 1] = json.dumps(state) + "\n"
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


def write_log(handle_msg, log_list, mode, call_sip=None):
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
    if mode == "callee" and call_sip:
        mode_show_log_path = mode_show_log_path + call_sip + "/"
    if not os.path.exists(mode_show_log_path):
        os.makedirs(mode_show_log_path)
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


def public_msg(core_uuid, call_username):
    client = mqtt_client.Client()
    client.connect(host=mqtt_host, port=mqtt_port, keepalive=600)
    client.username_pw_set(mqtt_username, mqtt_password)

    def _public_msg(sip):
        start_line, start_bytes = _get_start_sign(sip)
        msg = {
            "offset": {
                "start_line": int(start_line),
                "start_bytes": int(start_bytes)
            },
            "url": "http://{}:{}/log/upload".format("192.168.22.194", "8004")
        }
        msg_str = json.dumps(msg)
        print("public payload:", msg_str)
        client.publish("/5476752146/log_analyse/{}".format(sip), msg_str, 1)
    if isinstance(call_username, list):
        for sip in call_username:
            _public_msg(sip)
    else:
        _public_msg(call_username)


def check_file(call_log_path):
    '''
    检查终端日志文件是否上传成功。
    '''
    for i in range(5):
        if os.path.exists(call_log_path):
            return
        time.sleep(1)
    return "terminal log upload failed"


def _get_start_sign(call_name):
    redis_client = redis.StrictRedis(host=redis_host, port=redis_port, db=0, decode_responses=True)
    start_line = redis_client.hget(name=call_name, key="start_line")
    start_bytes = redis_client.hget(name=call_name, key="start_bytes")
    redis_client.close()
    if not start_line or not start_bytes:
        return 0, 0
    return start_line, start_bytes


def _set_start_sign(call_name, start_line, start_bytes):
    redis_client = redis.StrictRedis(host=redis_host, port=redis_port, db=0, decode_responses=True)
    redis_client.hset(name=call_name, key="start_line", value=start_line)
    redis_client.hset(name=call_name, key="start_bytes", value=start_bytes)
    redis_client.close()


def call_log_backup(call_log_file_path, call_log_tmp_file_path):
    # tem_file_list = list()
    # with open(call_log_tmp_file_path, 'rb') as call_log_tmp_file:
    #     for line in call_log_tmp_file:
    #         tem_file_list.append(line)
    # with open(call_log_file_path, "ab") as call_log_file_path:
    #     for lines in tem_file_list:
    #         call_log_file_path.write(lines)
    file_path = call_log_file_path.split("/")[0]
    if os.path.exists(file_path):
        os.removedirs(call_log_tmp_file_path)


def get_mqtt_log_path(old_path):
    local_path = local_file_path + "/mqtt/"
    local_path_file = local_path + "TruncMQTT_log_dir"
    if not os.path.exists(local_path_file):

        info = os.system("sshpass -p {password} scp {user}@{ip}:{remote_path} {local_path}/".format(
            password=server_password, user=server_user, ip=server_ip, remote_path=old_path, local_path=local_path))
        file_name = old_path.split("/")[-1]
        local_path_file = local_path + file_name
    remote_path_list = list()
    with open(local_path_file, "r") as local_file:
        for line in local_file:
            line = line.split("\n")[0]
            remote_path_list.append(line)

    return remote_path_list[0]


def get_sip_uuid(esl_list):
    caller_sip_call_id = None
    callee_sip_call_id = None
    for esl in esl_list:
        if esl.get("Event-Name") == "CHANNEL_CREATE" and esl.get("variable_sip_call_id"):
            caller_sip_call_id = esl.get("variable_sip_call_id")

        if esl.get("Event-Name") == "CHANNEL_PROGRESS" and esl.get("variable_sip_call_id"):
            callee_sip_call_id = esl.get("variable_sip_call_id")
    print(caller_sip_call_id, callee_sip_call_id)
    return caller_sip_call_id, callee_sip_call_id


def get_call_username(create_channel_dict_l):
    caller_username = None
    callee_username_list = list()
    for create_channel_dict in create_channel_dict_l:
        if create_channel_dict.get("Caller-Caller-ID-Number") and create_channel_dict.get("Event-Name") == "CHANNEL_CREATE":
            if create_channel_dict.get("Caller-Caller-ID-Number").isdigit():
                caller_username = create_channel_dict.get("Caller-Caller-ID-Number")
        if create_channel_dict.get("Caller-Callee-ID-Number") and create_channel_dict.get("Event-Name") == "CHANNEL_CREATE":
            if create_channel_dict.get("Caller-Callee-ID-Number").isdigit():
                callee_username_list.append(create_channel_dict.get("Caller-Callee-ID-Number"))

    return caller_username, callee_username_list
