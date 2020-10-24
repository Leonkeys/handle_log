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
host = app.config["LOCAL_HOST"]
port = app.config["LOCAL_PORT"]
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


def caller(caller_username, call_type, variable_sip_call_id):
    caller_log_tmp_file_path = local_file_path + "/tmp/{}_log".format(caller_username)
    logging.debug("caller check file ")
    msg = check_file(caller_log_tmp_file_path)
    if msg:
        caller_log = {"log_valid": "1", "state": "2", "err_msg": msg, "delay_time": "0", "analyse_prog_err": ""}
        if call_type == "videosingle":
            _show_log_path = show_log_path + "start_single_video_call/caller/whole_log"
        elif call_type == "audiosingle":
            _show_log_path = show_log_path + "start_single_audio_call/caller/whole_log"
        elif call_type == "videogroup":
            _show_log_path = show_log_path + "start_group_video_call/caller/whole_log"
        elif call_type in ["audiogroup", "mulgroup"]:
            # audiogroup
            _show_log_path = show_log_path + "start_group_audio_call/caller/whole_log"

        elif call_type == "urgentaudio":
            _show_log_path = show_log_path + "start_urgent_single_audio_call/caller/whole_log"
        del_tmp_path(_show_log_path)
        return write_node(caller_log, "caller", call_type, [])

    log_list = list()
    try:
        handle_info = com.analyse_main("caller", variable_sip_call_id, caller_log_tmp_file_path)
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        logging.error("caller analyse_main func error: %s" % error_msg)
        handle_info = {"log_valid": "1", "state": "2", "err_msg": error_msg, "delay_time": "0", "analyse_prog_err": ""}
    logging.debug("get caller user start sign ")
    try:
        with open(caller_log_tmp_file_path, "r", encoding="utf-8") as caller_log_tmp_file:
            for line_b in caller_log_tmp_file:
                if line_b:
                    print(line_b)
                    log_list.append(line_b)
    except:
        with open(caller_log_tmp_file_path, "r", encoding="gbk") as caller_log_tmp_file:
            for line_g in caller_log_tmp_file:
                if line_g:
                    log_list.append(line_g)

    write_node(handle_info, "caller", call_type, log_list)
    if os.path.isfile(caller_log_tmp_file_path):
        os.remove(caller_log_tmp_file_path)


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
    new_size = os.path.getsize(local_file)
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
    try:
        handle_info = com.analyse_main("nav", log_name=local_log)
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        handle_info = {"log_valid": "1", "state": "2", "err_msg": error_msg, "delay_time": "0", "analyse_prog_err": ""}
        logging.error("freeswitch analyse_main func error: %s" % error_msg)

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
    new_size = os.path.getsize(local_file)
    with open(local_file, "rb") as old_local_file:
        with open(local_log, "wb") as new_local_file:
            old_local_file.seek(int(start_bytes))
            for line_b in old_local_file:
                if line_b:
                    log_list.append(line_b)
                    new_local_file.write(line_b)
    set_server_log_line(dis_mode, new_size)
    try:
        handle_info = com.analyse_main("dis", log_name=local_log, offset_bytes=int(start_bytes))
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        logging.error("dispatcher analyse_main func error: %s" % error_msg)
        handle_info = {"log_valid": "1", "state": "2", "err_msg": error_msg, "delay_time": "0", "analyse_prog_err": ""}
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
    new_size = os.path.getsize(old_local_file)
    logging.debug("remote log file path:%s, local log filepath:%s." % (old_local_file, new_local_log))
    with open(old_local_file, "rb") as old_local_file:
        with open(new_local_log, "wb") as new_local_file:
            old_local_file.seek(int(start_bytes))
            for line_b in old_local_file:
                if line_b:
                    line_str = str(line_b, encoding="utf-8")
                    if line_str:
                        log_list.append(line_b)
                        new_local_file.write(line_b)
    set_server_log_line(api_mode, new_size)
    try:
        handle_info = com.analyse_main("api", log_name=new_local_log, offset_bytes=int(start_bytes))
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        logging.error("caller analyse_main func error: %s" % error_msg)
        handle_info = {"log_valid": "1", "state": "2", "err_msg": error_msg, "delay_time": "0", "analyse_prog_err": ""}
    logging.debug("api handle log write node")
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
    logging.debug("remote log file path:%s, local log filepath:%s." % (local_file, local_log))
    start_bytes = get_server_log_line(mqtt_mode)
    if os.path.exists(local_log):
        move(local_file, local_log)
        new_size = os.path.getsize(local_log)
        set_server_log_line(mqtt_mode, new_size)
        with open(local_log, "rb") as local_log_obj:
            local_log_obj.seek(int(start_bytes))
            for line in local_log_obj:
                log_list.append(line)

        try:
            handle_info = com.analyse_main("mqtt", log_name=local_log, offset_bytes=int(start_bytes))
        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            logging.error("caller analyse_main func error: %s" % error_msg)
            handle_info = {"log_valid": "1", "state": "2", "err_msg": error_msg, "delay_time": "0", "analyse_prog_err": ""}
    else:
        handle_info = {"log_valid": "1", "state": "1", "err_msg": "", "delay_time": "0", "analyse_prog_err": ""}
    logging.debug("mqtt handle log write node")
    write_node(handle_info, mqtt_mode, call_type, log_list)


def callee(core_uuid, callee_username_list, call_type, variable_sip_call_id):
    handle_info = {"log_valid": "1", "state": "2", "err_msg": "", "delay_time": "0", "analyse_prog_err": ""}
    clean_log_file(call_type)
    if isinstance(callee_username_list, list):
        if "single" in call_type or "urgent" in call_type:
            if not callee_username_list:
                handle_info = {"log_valid": "2", "state": "2", "err_msg": "callee is not exist", "analyse_prog_err": ""}
                return write_node(handle_info, "callee", call_type, [])
            callee_sip = callee_username_list[0]
            callee_log_tmp_file_path = local_file_path + "/tmp/{}_log".format(callee_sip)
            msg = check_file(callee_log_tmp_file_path)
            if msg:
                logging.warning("log handle(sip): {sip} terminal log upload failed.".format(sip=callee_sip))
                handle_info = {"log_valid": "0", "state": "2", "err_msg": msg, "delay_time": "0", "analyse_prog_err": ""}
                if call_type == "videosingle":
                    _show_log_path = show_log_path + "start_single_video_call/callee/whole_log"
                elif call_type == "audiosingle":
                    _show_log_path = show_log_path + "start_single_audio_call/callee/whole_log"
                elif call_type == "urgentaudio":
                    _show_log_path = show_log_path + "start_urgent_single_audio_call/caller/whole_log"
                if os.path.isfile(_show_log_path):
                    os.remove(_show_log_path)
                return write_node(handle_info, "callee", call_type, [])

            log_list = list()
            try:
                handle_info = com.analyse_main("callee", variable_sip_call_id, callee_log_tmp_file_path)
            except Exception as e:
                import traceback
                error_msg = traceback.format_exc()
                handle_info = {"log_valid": "1", "state": "2", "err_msg": error_msg, "delay_time": "0", "analyse_prog_err": ""}

            logging.debug("get callee user start sign ")
            try:
                with open(callee_log_tmp_file_path, "r", encoding="utf-8") as callee_log_tmp_file:
                    for line_b in callee_log_tmp_file:
                        if line_b:
                            log_list.append(line_b)
            except:
                log_list = list()
                with open(callee_log_tmp_file_path, "r", encoding="gbk") as callee_log_tmp_file_g:
                    for line_g in callee_log_tmp_file_g:
                        if line_g:
                            log_list.append(line_g)

            write_node(handle_info, "callee", call_type, log_list)
            del_tmp_path(callee_log_tmp_file_path)
            logging.debug("callee handle log=================END=================(single)")

        else:
            user_info_list = list()
            delay_time_mean = 0
            for sip in callee_username_list:
                log_list = list()
                callee_log_tmp_file_path = local_file_path + "/tmp/{}_log".format(sip)
                msg = check_file(callee_log_tmp_file_path)
                if msg:
                    handle_info["state"] = "2"
                    _handle_info = {"log_valid": "1", "state": "2", "err_msg": msg, "delay_time": "0", "analyse_prog_err": ""}
                    logging.warning("log handle(sip): {sip} terminal log upload failed.".format(sip=sip))
                    write_log(_handle_info, "callee", call_type=call_type, log_list=log_list, call_sip=sip)
                    continue
                try:
                    with open(callee_log_tmp_file_path, "r", encoding="utf-8") as callee_log_tmp_file:
                        for line_b in callee_log_tmp_file:
                            if line_b:
                                log_list.append(line_b)
                except:
                    log_list = list()
                    with open(callee_log_tmp_file_path, "r", encoding="gbk") as callee_log_tmp_file_g:
                        for line_g in callee_log_tmp_file_g:
                            if line_g:
                                log_list.append(line_g)
                try:
                    _handle_info = com.analyse_main("callee", uuid=variable_sip_call_id, log_name=callee_log_tmp_file_path)
                except Exception as e:
                    handle_info["state"] = "2"
                    import traceback
                    error_msg = traceback.format_exc()
                    _handle_info = {"log_valid": "1", "state": "2", "err_msg": error_msg, "delay_time": "0", "analyse_prog_err": ""}
                    logging.error(error_msg)

                user_info = dict()
                user_info["name"] = sip
                user_info["state"] = _handle_info.get("state")
                user_info["delay_time"] = _handle_info.get('delay_time', "0")
                user_info_list.append(user_info)

                delay_time_mean = round((int(handle_info.get("delay_time")) + delay_time_mean) / 2, ndigits=5)
                logging.debug("log handle(sip): {sip} handle success".format(sip=sip))
                write_log(_handle_info, "callee", call_type=call_type, log_list=log_list, call_sip=sip)
                del_tmp_path(callee_log_tmp_file_path)

            write_conf("callee", handle_info, call_type=call_type, user_info=user_info_list)
            logging.debug("handle log ===============END===============(group)")
    else:
        msg = "log_handle is err please call manager(callee mode need callee_username_list is a list not other type)"
        handle_info["err_msg"] = msg
        handle_info["state"] = 2
        write_node(handle_info, "callee", call_type, [])
        logging.warning("handle log ==============END==============")


def write_node(handle_msg, mode, call_type, log_list, user_info=None):
    """
    写和前端交互的文本  && 和需要展示的log日志文件
    """
    logging.debug("%s write_node " % mode)
    # 视频单呼组呼，音频单呼组呼。
    if call_type in ["audiosingle", "videosingle", "videogroup", "audiogroup", "mulgroup", "urgentaudio"]:
        write_conf(mode, handle_msg, call_type=call_type, user_info=user_info)
        write_log(handle_msg, mode, call_type=call_type, log_list=log_list)


def write_conf(mode, handle_msg, call_type=None, user_info=None):
    """
    单呼 组呼写conf文件
    """

    state = handle_msg.get('state', "0")
    delay_time = handle_msg.get("delay_time")
    conf_file_path = app.config["CONF_FILE_PATH"]

    if call_type == "audiosingle":
        conf_file_name = "start_single_audio_call.json"
    elif call_type == "videosingle":
        conf_file_name = "start_single_video_call.json"
    elif call_type in ["audiogroup", "mulgroup"]:
        conf_file_name = "start_group_audio_call.json"
    elif call_type == "videogroup":
        conf_file_name = "start_group_video_call.json"
    elif call_type == "urgentaudio":
        conf_file_name = "start_urgent_single_audio_call.json"
    else:
        conf_file_name = ""

    logging.debug("write config node file path:%s" % conf_file_path + conf_file_name)
    with open(conf_file_path + conf_file_name, "r") as conf_file:
        conf_json = json.load(conf_file)
        if state:
            conf_json.get("step_list").get(mode)["state"] = state
        if delay_time:
            delay_time = str(delay_time)
            conf_json.get("step_list").get(mode)["delay_time"] = delay_time
        if mode == "callee" and user_info:
            conf_json.get("step_list").get(mode)["user_list"] = user_info
    with open(os.path.join(conf_file_path, conf_file_name), "w") as conf_file:
        conf_file.truncate()
        json.dump(conf_json, conf_file, ensure_ascii=False)


def write_log(handle_msg, mode, call_type=None, log_list=None, call_sip=None):
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
    elif call_type in ["audiogroup", "mulgroup"]:
        mode_show_log_path = show_log_path + "start_group_audio_call/" + mode + "/"
    elif call_type == "videogroup":
        # videogroup
        mode_show_log_path = show_log_path + "start_group_video_call/" + mode + "/"
    elif call_type == "urgentaudio":
        mode_show_log_path = show_log_path + "start_urgent_single_audio_call/" + mode + "/"
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
    if isinstance(log_list, list):
        whole_log_file = mode_show_log_path + "whole_log"
        with open(whole_log_file, "w") as whole_log_file:
            whole_log_file.truncate()
            for log in log_list:
                whole_log_file.write(log)
    if handle_msg:
        handle_log_file = mode_show_log_path + "handle_log"
        with open(handle_log_file, "w") as handle_log_file:
            handle_msg_str = json.dumps(handle_msg)
            handle_log_file.write(handle_msg_str)


def public_msg(call_username):
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
        logging.debug("public topic: %s , payload: %s " % ("/5476752146/log_analyse/{}".format(sip), msg_str))
        client.publish("/5476752146/log_analyse/{}".format(sip), msg_str, 1)
    if isinstance(call_username, list):
        for sip in call_username:
            _public_msg(sip)
    else:
        _public_msg(call_username)
    client.disconnect()


def check_file(call_log_path):
    '''
    检查终端日志文件是否上传成功。
    '''
    for i in range(15):
        if os.path.isfile(call_log_path):
            return
        time.sleep(1)
    return "terminal log upload failed"


def _get_start_sign(call_name):
    if call_name:
        redis_client = redis.StrictRedis(host=redis_host, port=redis_port, db=0, decode_responses=True)
        start_line = redis_client.hget(name=call_name, key="start_line")
        start_bytes = redis_client.hget(name=call_name, key="start_bytes")
        redis_client.close()
    else:
        start_line, start_bytes = 0, 0
    if not start_line or not start_bytes:
        return 0, 0
    return start_line, start_bytes


def del_tmp_path(call_log_tmp_file_path):
    path, file = call_log_tmp_file_path.rsplit("/", 1)
    if os.path.exists(path):
        rmtree(path)


def get_mqtt_log_path(old_path):
    local_path = local_file_path + "/mqtt/"
    local_path_file = local_path + "TruncMQTT_log_dir"
    if not os.path.exists(local_path):
        os.makedirs(local_path)
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

            elif "group" in call_info_str and "urgent" not in call_info_str:
                call_sip_info = create_channel_info.get("Caller-Destination-Number").split("*")
                call_type = call_sip_info[0]
                build_id = call_sip_info[-2]
                return call_type, build_id
            elif "urgent" in call_info_str:
                call_type = "urgentaudio"
                build_id = call_info_str
                return call_type, build_id
    else:
        if not create_channel_info_list:
            raise Exception("create_channel_dict_l is not exist (get_call_type)")
        call_info = create_channel_info_list[0]
        call_str = call_info.get("Caller-Caller-ID-Number")
        call_info = call_str.split("*")
        call_type, build_id = call_info[0], call_info[-3]
        return call_type, build_id


def write_build_id(call_type, build_id):
    conf_file_name = ""
    if call_type == "audiosingle":
        conf_file_name = "start_single_audio_call.json"
    elif call_type == "videosingle":
        conf_file_name = "start_single_video_call.json"
    elif call_type in ["audiogroup", "mulgroup"]:
        conf_file_name = "start_group_audio_call.json"
    elif call_type == "videogroup":
        conf_file_name = "start_group_video_call.json"
    elif call_type == "urgentaudio":
        conf_file_name = "start_urgent_single_audio_call.json"

    conf_file_path = app.config["CONF_FILE_PATH"]
    template_conf_file_path = app.config["TEMPLATE_CONF_FILE_PATH"]
    if not conf_file_name:
        logging.error("call type is not exist")
        return
        # raise Exception("call type is not exist")

    if os.path.exists(conf_file_path + conf_file_name):
        os.remove(conf_file_path + conf_file_name)
        copyfile(template_conf_file_path + conf_file_name, conf_file_path + conf_file_name)
    else:
        copyfile(template_conf_file_path + conf_file_name, conf_file_path + conf_file_name)
    # import fcntl
    with open(os.path.join(conf_file_path, conf_file_name), "r") as conf_file:
        file_info = json.load(conf_file)
        file_info["build_id_next"] = build_id

    with open(os.path.join(conf_file_path, conf_file_name), "w") as conf_file:
        conf_file.truncate()
        json.dump(file_info, conf_file, ensure_ascii=False)


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

    if call_type in "audiosingle":
        mode_show_log_path = show_log_path + "start_single_audio_call/callee/"
    elif call_type == "videosingle":
        mode_show_log_path = show_log_path + "start_single_video_call/callee/"
    elif call_type in ["audiogroup", "mulgroup"]:
        mode_show_log_path = show_log_path + "start_group_audio_call/callee/"
    elif call_type == "videogroup":
        # videogroup
        mode_show_log_path = show_log_path + "start_group_video_call/callee/"
    elif call_type == "urgentaudio":
        mode_show_log_path = show_log_path + "start_urgent_single_audio_call/callee/"

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


def get_terminal_log(caller_username, callee_username_list, call_type):
    call_terminal_log_path = local_file_path + "/tmp/"
    if os.path.exists(call_terminal_log_path):
        ls_terminal_log_file = os.listdir(call_terminal_log_path)
        for _file in ls_terminal_log_file:
            if os.path.isdir(_file):
                d_file = call_terminal_log_path + _file
                rmtree(d_file)
            else:
                os.remove(os.path.join(call_terminal_log_path, _file))

    # caller
    public_msg(caller_username)
    public_msg(callee_username_list)
