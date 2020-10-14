import os
import datetime
import logging
import json
import time
import redis
from shutil import copyfile, move, rmtree
from manage import app
from paho.mqtt import client as mqtt_client
# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker
from .common import common_log_analyse as com

# DB_CONNECT = app.config['DB_CONNECT']
host = app.config["HOST"]
port = app.config["PORT"]
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


def caller(core_uuid, caller_username, call_type, variable_sip_call_id):
    public_msg(core_uuid, caller_username)
    caller_log_tmp_file_path = local_file_path + "/tmp/{}_log".format(caller_username)
    logging.debug("caller check file is exist")
    msg = check_file(caller_log_tmp_file_path)
    if msg:
        caller_log = {"log_valid": "1", "state": "2", "err_msg": msg, "delay_time": "27017.2ms", "analyse_prog_err": ""}
        call_log_backup(caller_log_tmp_file_path)
        return write_node(caller_log, "caller", call_type, [])
    log_list = list()
    handle_info = com.analyse_main("caller", variable_sip_call_id, caller_log_tmp_file_path)
    logging.debug("get caller user start sign ")
    with open(caller_log_tmp_file_path, "rb") as caller_log_tmp_file:
        for line_b in caller_log_tmp_file:
            if line_b:
                log_list.append(line_b)

    write_node(handle_info, "caller", call_type, log_list)
    call_log_backup(caller_log_tmp_file_path)


def freeswitch(core_uuid, unique_id_list, filename, call_type):
    """
    截取当前通话相关的日志&&freeswitch日志分析
    """
    logging.debug("log handle freeswitch start")
    log_list = list()
    if not unique_id_list:
        return
    freeswitch_mode = "freeswitch"
    local_file = local_file_path + "/" + filename
    local_log = local_file_path + "/freeswitch/" + core_uuid
    if not os.path.exists(local_file_path + "/freeswitch"):
        os.makedirs(local_file_path + "/freeswitch")
    start_bytes = get_server_log_line(freeswitch_mode)
    new_size = os.path.getsize(local_log)
    with open(local_file, "rb") as old_local_file:

        with open(local_log, "wb") as new_local_file:
            old_local_file.seek(int(start_bytes))
            for line_b in old_local_file:
                if line_b:
                    line_str = str(line_b, encoding="utf-8")
                    if line_str and any(channel_uuid in line_str for channel_uuid in unique_id_list):
                        log_list.append(line_b)
                        new_local_file.write(line_b)
    set_server_log_line(freeswitch_mode, new_size)
    handle_info = com.analyse_main("nav", log_name=local_log)
    write_node(handle_info, freeswitch_mode, call_type, log_list)


def dispatcher(core_uuid, unique_id_list, filename, call_type):
    """
    dispatcher日志分析
    """

    logging.debug("log handle dispatcher start")
    log_list = list()
    if not unique_id_list:
        return
    dis_mode = "dispatcher"
    local_file = local_file_path + "/" + filename
    local_log = local_file_path + "/" + dis_mode + "/" + core_uuid
    if not os.path.exists(local_file_path + "/" + dis_mode):
        os.makedirs(local_file_path + "/" + dis_mode)
    logging.debug("remote log file path:%s, local log filepath:%s." % (local_file, local_log))
    start_bytes = get_server_log_line(dis_mode)
    new_size = os.path.getsize(local_log)
    with open(local_file, "rb") as old_local_file:
        with open(local_log, "wb") as new_local_file:
            for line_b in old_local_file:
                if line_b:
                    log_list.append(line_b)
                    new_local_file.write(line_b)
    set_server_log_line(dis_mode, new_size)
    handle_info = com.analyse_main("dis", log_name=local_log, offset_bytes=int(start_bytes))
    write_node(handle_info, dis_mode, call_type, log_list)


def api(core_uuid, unique_id_list, filename, call_type):
    """
    api日志分析：欣欣接口调用数据库的日志分析
    """
    log_list = list()
    if not unique_id_list:
        return
    api_mode = "api"
    old_local_file = local_file_path + "/" + filename
    new_local_log = local_file_path + "/" + api_mode + "/" + core_uuid
    if not os.path.exists(local_file_path + "/" + api_mode):
        os.makedirs(local_file_path + "/" + api_mode)

    start_bytes = get_server_log_line(api_mode)
    new_size = os.path.getsize(new_local_log)
    logging.debug("remote log file path:%s, local log filepath:%s." % (old_local_file, new_local_log))
    with open(old_local_file, "rb") as old_local_file:
        with open(new_local_log, "wb") as new_local_file:
            for line_b in old_local_file:
                if line_b:
                    line_str = str(line_b, encoding="utf-8")
                    if line_str:
                        log_list.append(line_b)
                        new_local_file.write(line_b)
    set_server_log_line(api_mode, new_size)
    handle_info = com.analyse_main("api", log_name=new_local_log, offset_bytes=int(start_bytes))
    write_node(handle_info, api_mode, call_type, log_list)


def mqtt(core_uuid, unique_id_list, filename, call_type):
    """
    mqtt日志分析
    mqtt日志分析指mqtt消息通道收到的消息的分析不是本身服务运行状态分析
    """
    log_list = list()
    if not unique_id_list:
        return
    mqtt_mode = "mqtt"
    local_file = local_file_path + "/" + filename
    local_log = local_file_path + "/" + mqtt_mode + "/" + core_uuid
    if not os.path.exists(local_file_path + "/" + mqtt_mode):
        os.makedirs(local_file_path + "/" + mqtt_mode)
    move(local_file, local_log)
    logging.debug("remote log file path:%s, local log filepath:%s." % (local_file, local_log))
    start_bytes = get_server_log_line(mqtt_mode)
    new_size = os.path.getsize(local_log)
    with open(local_log, "rb") as local_log_obj:
        for line in local_log_obj:
            log_list.append(line)

    set_server_log_line(mqtt_mode, new_size)
    handle_info = com.analyse_main("mqtt", log_name=local_log, offset_bytes=int(start_bytes))
    write_node(handle_info, mqtt_mode, call_type, log_list)


def callee(core_uuid, callee_username_list, call_type, variable_sip_call_id):
    public_msg(core_uuid, callee_username_list)
    handle_info = {"log_valid": "1", "state": {}, "err_msg": "", "delay_time": {}, "analyse_prog_err": ""}
    clean_log_file(call_type)
    if isinstance(callee_username_list, list):
        for sip in callee_username_list:
            log_list = list()
            callee_log_tmp_file_path = local_file_path + "/tmp/{}_log".format(sip)
            msg = check_file(callee_log_tmp_file_path)
            if msg:
                handle_info["err_msg"] = msg
                handle_info.get("state")[sip] = 2
                logging.warning("log handle(sip): {sip} terminal log upload failed.".format(sip=sip))
                write_log(handle_info, log_list, "callee", call_sip=sip, call_type=call_type)
                continue
            with open(callee_log_tmp_file_path, "rb") as callee_log_tmp_file:
                for line_b in callee_log_tmp_file:
                    if line_b:
                        log_list.append(line_b)
            handle_info = com.analyse_main("callee", uuid=variable_sip_call_id, log_name=callee_log_tmp_file_path)
            logging.debug("log handle(sip): {sip} handle success".format(sip=sip))
            write_log(handle_info, log_list, "callee", call_sip=sip, call_type=call_type)
            call_log_backup(callee_log_tmp_file_path)
        write_conf("callee", handle_info, call_type=call_type)
        logging.debug("handle log ===============END===============")
    else:
        msg = "log_handle is err please call manager(callee mode need callee_username_list is a list not other type)"
        handle_info["err_msg"] = msg
        handle_info["state"] = 2
        write_node(handle_info, "callee", call_type, [])
        logging.warning("handle log ==============END==============")


def write_node(handle_msg, mode, call_type, log_list):
    """
    写和前端交互的文本  && 和需要展示的log日志文件
    """
    logging.debug("%s write_node " % mode)
    # call_type_list = [audiosingle, videosingle, audiogroup, videogroup, ...]
    # 视频单呼组呼，音频单呼组呼。
    if call_type in ["audiosingle", "videosingle", "videogroup", "audiogroup"]:
        write_conf(mode, handle_msg, call_type=call_type)
        write_log(handle_msg, log_list, mode, call_type=call_type)


def write_conf(mode, handle_msg, call_type=None):
    """
    单呼 组呼写conf文件
    """

    if not call_type:
        call_type = handle_msg.get("call_type")[0]
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
    if call_type == "audiosingle":
        conf_file_name = "start_single_audio_call.conf"
    elif call_type == "videosingle":
        conf_file_name = "start_single_video_call.conf"
    elif call_type == "audiogroup":
        conf_file_name = "start_group_audio_call.conf"
    elif call_type == "videogroup":
        conf_file_name = "start_group_video_call.conf"
    else:
        conf_file_name = ""

    logging.debug("write config node file path:%s" % conf_file_path + conf_file_name)
    file_msg_list = []
    with open(conf_file_path + conf_file_name, "r+") as conf_file_path:
        for conf_line in conf_file_path:
            file_msg_list.append(conf_line)
        if state:
            if isinstance(state, dict):
                if len(state) > 1:
                    file_msg_list[mode_write_line - 1] = json.dumps(state) + "\n"
                else:
                    for i in state.values():
                        file_msg_list[mode_write_line - 1] = str(i) + "\n"
            else:
                file_msg_list[mode_write_line - 1] = str(state) + "\n"
        if delay_time:
            if isinstance(delay_time, dict):
                total_delay_time = {}
                for sip, _time in delay_time.items():
                    time = float(_time.replace("ms", ""))
                    old_delay_time = float(file_msg_list[45].replace("ms\n", ""))
                    total_delay_time[sip] = str(time + old_delay_time) + "ms"
                file_msg_list[delay_time_write_line - 1] = json.dumps(delay_time) + "\n"
                file_msg_list[45] = json.dumps(total_delay_time) + "\n"

            else:
                file_msg_list[delay_time_write_line - 1] = str(delay_time) + "\n"
                old_delay_time = float(file_msg_list[45].replace("ms\n", ""))
                file_msg_list[45] = str(old_delay_time + float(delay_time.replace("ms", ""))) + "ms\n"
        conf_file_path.seek(0)
        for line in file_msg_list:
            conf_file_path.write(line)


def write_log(handle_msg, log_list, mode, call_sip=None, call_type=None):
    """
    编辑需要展示的日志文件内容
    单呼 组呼 写日志文件
    """
    logging.debug("%s start to write log file " % mode)
    err_msg = handle_msg.get("err_msg")
    if not call_type:
        call_type = handle_msg.get("call_type")[0]
    if call_type == "audiosingle":
        mode_show_log_path = show_log_path + "start_single_audio_call/" + mode + "/"
    elif call_type == "videosingle":
        mode_show_log_path = show_log_path + "start_single_video_call/" + mode + "/"
    elif call_type == "audiogroup":
        mode_show_log_path = show_log_path + "start_group_audio_call/" + mode + "/"
    else:
        # videogroup
        mode_show_log_path = show_log_path + "start_group_video_call/" + mode + "/"
    if mode == "callee" and call_sip:
        mode_show_log_path = mode_show_log_path + call_sip + "/"
    if not os.path.exists(mode_show_log_path):
        os.makedirs(mode_show_log_path)
    logging.debug("%s write file path:%s" % (mode, mode_show_log_path))
    if err_msg:
        if isinstance(err_msg, dict):
            err_msg = json.dumps(err_msg)
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
            "url": "http://{}:{}/log/upload".format(host, port)
        }
        msg_str = json.dumps(msg)
        # logging.debug("{datetime}: public payload: {msg}".format(datetime=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%s"), msg=msg_str))
        logging.debug("public topic: %s , payload: %s " % ("/5476752146/log_analyse/{}".format(sip), msg_str))
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
    for i in range(15):
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
#
#
# def _set_start_sign(call_name, start_line, start_bytes):
#     redis_client = redis.StrictRedis(host=redis_host, port=redis_port, db=0, decode_responses=True)
#     redis_client.hset(name=call_name, key="start_line", value=start_line)
#     redis_client.hset(name=call_name, key="start_bytes", value=start_bytes)
#     redis_client.close()
#


def call_log_backup(call_log_tmp_file_path):
    path, file = call_log_tmp_file_path.rsplit("/", 1)
    if os.path.exists(path):
        rmtree(path)


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
    logging.debug("{}{}".format(caller_sip_call_id, callee_sip_call_id))
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

    return caller_username, list(set(callee_username_list))


def get_call_type(create_channel_info_list):
    for create_channel_info in create_channel_info_list:
        if create_channel_info.get("Call-Direction") != "inbound":
            continue
        call_info_str = create_channel_info.get("Caller-Destination-Number")
        if call_info_str:
            if call_info_str.isdigit():
                caller_user_sip_id = create_channel_info.get("variable_sip_from_user")
                callee_user_sip_id = create_channel_info.get("variable_sip_to_user")
                if create_channel_info.get("variable_sip_h_X-NF-Video"):
                    call_type = "videosingle"
                    build_id = call_type + "*" + caller_user_sip_id + "*" + callee_user_sip_id + "*00"
                    return call_type, build_id
                else:
                    call_type = "audiosingle"
                    build_id = call_type + "*" + caller_user_sip_id + "*" + callee_user_sip_id + "*00"
                    return call_type, build_id

            elif "group" in call_info_str:
                call_sip_info = create_channel_info.get("Caller-Destination-Number").split("*")
                call_type = call_sip_info[0]
                build_id = call_sip_info[-2]
                return call_type, build_id
            # elif "urgent" in call_info_str:
            #     call_type = "urgentaudio"
            #     build_id = call_info_str


def write_build_id(call_type, build_id):
    conf_file_name = ""
    if call_type == "audiosingle":
        conf_file_name = "start_single_audio_call.conf"
    elif call_type == "videosingle":
        conf_file_name = "start_single_video_call.conf"
    elif call_type == "audiogroup":
        conf_file_name = "start_group_audio_call.conf"
    elif call_type == "videogroup":
        conf_file_name = "start_group_video_call.conf"

    conf_file_path = app.config["CONF_FILE_PATH"]
    template_conf_file_path = app.config["TEMPLATE_CONF_FILE_PATH"]
    if not conf_file_name:
        raise Exception("call type is not exist")
    if os.path.exists(conf_file_path + conf_file_name):
        os.remove(conf_file_path + conf_file_name)
        copyfile(template_conf_file_path + conf_file_name, conf_file_path + conf_file_name)
    file_msg_list = []
    write_line = 16
    with open(conf_file_path + conf_file_name, "r+") as write_conf_file_path:
        for conf_line in write_conf_file_path:
            file_msg_list.append(conf_line)

        file_msg_list[write_line - 1] = build_id + "\n"
        write_conf_file_path.seek(0)
        for line in file_msg_list:
            write_conf_file_path.write(line)


def update_start_sign(call_sip, filepath):
    file_bytes = os.path.getsize(filepath)
    file_line = 0
    with open(filepath, "rb") as call_filepath:
        for line_b in call_filepath:
            if line_b:
                file_line += 1

    redis_client = redis.StrictRedis(host=redis_host, port=redis_port, db=0, decode_responses=True)
    start_line = redis_client.hget(name=call_sip, key="start_line")
    start_bytes = redis_client.hget(name=call_sip, key="start_bytes")
    if not start_line or not start_bytes:
        start_line, start_bytes = 0, 0
    else:
        start_line, start_bytes = int(start_line), int(start_bytes)
    start_line += file_line
    start_bytes += file_bytes
    redis_client.hset(name=call_sip, key="start_line", value=start_line)
    redis_client.hset(name=call_sip, key="start_bytes", value=start_bytes)
    redis_client.close()
    logging.debug("update start sign: {}".format(call_sip))


def clean_log_file(call_type):

    if call_type in ["audiosingle", "singlecall"]:
        mode_show_log_path = show_log_path + "start_single_audio_call/callee/"
    elif call_type == "videosingle":
        mode_show_log_path = show_log_path + "start_single_video_call/callee/"
    elif call_type == "audiogroup":
        mode_show_log_path = show_log_path + "start_group_audio_call/callee/"
    else:
        # videogroup
        mode_show_log_path = show_log_path + "start_group_video_call/callee/"

    if os.path.exists(mode_show_log_path):
        ls_log_path = os.listdir(mode_show_log_path)

        for _file in ls_log_path:
            c_path = os.path.join(mode_show_log_path, _file)
            if os.path.isdir(c_path):
                rmtree(c_path)
            else:
                os.remove(c_path)


def set_server_log_line(mode, end_line):
    redis_client = redis.StrictRedis(host=redis_host, port=redis_port, db=2, decode_responses=True)
    redis_client.set(mode, end_line)
    redis_client.close()


def get_server_log_line(mode):
    redis_client = redis.StrictRedis(host=redis_host, port=redis_port, db=2, decode_responses=True)
    start_line = redis_client.get(mode)
    if not start_line:
        start_line = 0
    redis_client.close()
    return start_line
