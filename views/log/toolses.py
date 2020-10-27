import os
import logging
import json
import time
import redis
from shutil import copyfile, rmtree
from manage import app
from paho.mqtt import client as mqtt_client
from .common import common_log_analyse as com

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
                    # daniu
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
    # elif Caller-Caller-ID-Number
    else:
        try:
            logging.debug("esl msg not include inbound: %s" % json.dumps(create_channel_info_list))
            if not create_channel_info_list:
                raise Exception("create_channel_dict_l is not exist (get_call_type)")
            call_info = create_channel_info_list[0]
            call_str = call_info.get("Caller-Caller-ID-Number")
            call_info = call_str.split("*")
            if len(call_info) > 3:
                call_type, build_id = call_info[0], call_info[-3]
            else:
                if "urgent" in call_str:
                    call_type = "urgentaudio"
                    build_id = call_str
                else:
                    logging.debug(json.dumps(call_info))
                    call_type = None
                    build_id = None
            return call_type, build_id
        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            logging.error(error_msg)


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

    if os.path.exists(conf_file_path + conf_file_name):
        os.remove(conf_file_path + conf_file_name)
        copyfile(template_conf_file_path + conf_file_name, conf_file_path + conf_file_name)
    else:
        copyfile(template_conf_file_path + conf_file_name, conf_file_path + conf_file_name)
    with open(os.path.join(conf_file_path, conf_file_name), "r") as conf_file:
        file_info = json.load(conf_file)
        file_info["build_id_next"] = build_id

    with open(os.path.join(conf_file_path, conf_file_name), "w") as conf_file:
        conf_file.truncate()
        json.dump(file_info, conf_file, ensure_ascii=False)


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


def get_server_log(remote_path, call_type, mode, unique_id_list, local_file=None):
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
        file_name = remote_path.rsplit("/", -1)[-1]
        local_path = local_file if local_file else local_file_path
        whole_log_path = get_whole_log_path(call_type, mode)

        if isinstance(remote_path, list):
            for path in remote_path:
                info = os.system("sshpass -p {password} rsync {user}@{ip}:{remote_path} {local_path}/".format(
                    password=password, user=user, ip=ip, remote_path=path, local_path=local_path))
        elif isinstance(remote_path, str):

            info = os.system("sshpass -p {password} rsync {user}@{ip}:{remote_path} {local_path}/".format(
                password=password, user=user, ip=ip, remote_path=remote_path, local_path=local_path))

        old_start_line, last_start_line = get_server_log_line(mode)
        new_start_bytes = os.path.getsize(os.path.join(local_path, file_name))
        set_server_log_line(mode, new_start_bytes)
        log_list = list()
        with open(os.path.join(local_path, file_name), "r") as remote_file:
            remote_file.seek(int(last_start_line))
            if mode == "freeswitch":
                for line in remote_file:
                    if line and any(channel_uuid in line for channel_uuid in unique_id_list):
                        log_list.append(line)
            else:
                for line in remote_file:
                    if line:
                        log_list.append(line)
        if mode == "api" and not log_list:
            redis_client = redis.StrictRedis(host=redis_host, port=redis_port, db=0, decode_responses=True)
            redis_client.hdel("api", "old_start_bytes", "last_start_bytes")
            redis_client.close()

        with open(whole_log_path, "w") as whole_log_path:
            for i in log_list:
                whole_log_path.write(i)

    except Exception as e:
        logging.warning(e)


def get_terminal_log(caller_username, callee_username_list, call_type):
    # clean tmp dir
    err_sip_list = []
    call_terminal_log_path = local_file_path + "/tmp/"
    if os.path.exists(call_terminal_log_path):
        ls_terminal_log_file = os.listdir(call_terminal_log_path)
        for _file in ls_terminal_log_file:
            if os.path.isdir(_file):
                d_file = call_terminal_log_path + _file
                rmtree(d_file)
            else:
                os.remove(os.path.join(call_terminal_log_path, _file))

    # clean show log path
    clean_log_file(call_type, "caller")
    clean_log_file(call_type, "callee")
    # caller
    public_msg(caller_username)

    caller_terminal_log_path = local_file_path + "/tmp/{}_log".format(caller_username)
    whole_log_path = get_whole_log_path(call_type, "caller")
    _err_sip_list = check_file(err_sip_list, caller_user=caller_username)
    err_sip_list = err_sip_list + _err_sip_list
    try:
        caller_log_list = list()
        with open(caller_terminal_log_path, "r", encoding="utf-8") as caller_terminal_log:
            for log in caller_terminal_log:
                caller_log_list.append(log)
    except:
        try:
            caller_log_list = list()
            with open(caller_terminal_log_path, "r", encoding="gbk") as caller_terminal_log:
                for log in caller_terminal_log:
                    caller_log_list.append(log)
        except:
            logging.error("caller {caller_sip} decode failed".format(caller_sip=caller_username))
            caller_clean_offset = True

    if not caller_log_list and not caller_clean_offset:
        redis_client = redis.StrictRedis(host=redis_host, port=redis_port, db=0, decode_responses=True)
        redis_client.hdel(caller_username, "start_line")
        redis_client.hdel(caller_username, "start_bytes")
        redis_client.close()
    with open(whole_log_path, "w") as show_log_file:
        for log in caller_log_list:
            show_log_file.write(log)

    update_whole_state(call_type, "caller")

    # callee
    user_info_list = list()
    public_msg(callee_username_list)

    _err_sip_list = check_file(err_sip_list, callee_user_list=callee_username_list)
    err_sip_list = err_sip_list + _err_sip_list
    for callee_username in callee_username_list:
        if callee_username in _err_sip_list:
            logging.debug("callee {callee_sip} upload log error".format(callee_sip=callee_username))
            continue
        logging.debug("get callee terminal log :%s" % callee_username)
        callee_terminal_log_path = local_file_path + "/tmp/{}_log".format(callee_username)

        if call_type == "videosingle":
            callee_show_log_path = show_log_path + "start_single_video_call/callee/whole_log"
        elif call_type == "audiosingle":
            callee_show_log_path = show_log_path + "start_single_audio_call/callee/whole_log"
        elif call_type == "videogroup":
            callee_show_log_path = show_log_path + "start_group_video_call/callee/" + callee_username + "/whole_log"
        elif call_type in ["audiogroup", "mulgroup"]:
            callee_show_log_path = show_log_path + "start_group_audio_call/callee/" + callee_username + "/whole_log"
        elif call_type == "urgentaudio":
            callee_show_log_path = show_log_path + "start_urgent_single_audio_call/callee/whole_log"
        if call_type in ["audiogroup", "mulgroup", "videogroup"]:
            user_info = dict()
            user_info["name"] = callee_username
            user_info_list.append(user_info)

        # msg = check_file(callee_terminal_log_path)
        # if msg:
        #     if os.path.isfile(callee_show_log_path):
        #         os.remove(callee_show_log_path)
        #     err_sip_list.append(callee_username)
        # else:
        callee_log_list = list()
        try:
            with open(callee_terminal_log_path, "r", encoding="utf-8") as callee_terminal_log:
                for log in callee_terminal_log:
                    callee_log_list.append(log)
        except:
            try:
                callee_log_list = list()
                with open(callee_terminal_log_path, "r", encoding="gbk") as callee_terminal_log_g:
                    for log in callee_terminal_log_g:
                        callee_log_list.append(log)
            except:
                logging.error("callee {callee_sip} log decode failed".format(callee_sip=callee_username))
                clean_sip_offset = True
        path, file_name = os.path.split(callee_show_log_path)
        if not os.path.exists(path):
            os.makedirs(path)

        if not callee_log_list and not clean_sip_offset:
            redis_client = redis.StrictRedis(host=redis_host, port=redis_port, db=0, decode_responses=True)
            redis_client.hdel(caller_username, "start_line")
            redis_client.hdel(caller_username, "start_bytes")
            redis_client.close()
        with open(callee_show_log_path, "w") as show_log_file:
            for log in callee_log_list:
                show_log_file.write(log)

    update_whole_state(call_type, "callee", user_info_list=user_info_list)
    return err_sip_list


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


def check_file(error_sip_list, caller_user=None, callee_user_list=None):
    '''
    检查终端日志文件是否上传成功。
    '''
    time.sleep(15)
    if callee_user_list and isinstance(callee_user_list, list):
        for callee_user in callee_user_list:
            callee_terminal_log_path = local_file_path + "/tmp/{}_log".format(callee_user)
            if not os.path.isfile(callee_terminal_log_path):
                error_sip_list.append(callee_user)

    if caller_user and isinstance(caller_user, str):
        caller_terminal_log_path = local_file_path + "/tmp/{}_log".format(caller_user)
        if not os.path.isfile(caller_terminal_log_path):
            error_sip_list.append(caller_user)
    return error_sip_list


def get_server_log_line(mode):
    redis_client = redis.StrictRedis(host=redis_host, port=redis_port, db=2, decode_responses=True)
    last_start_bytes = redis_client.hget(name=mode, key="last_start_bytes")
    old_start_bytes = redis_client.hget(name=mode, key="old_start_bytes")
    if not last_start_bytes or not old_start_bytes:
        last_start_bytes, old_start_bytes = "0", "0"
    redis_client.close()
    return old_start_bytes, last_start_bytes


def caller(caller_username, call_type, variable_sip_call_id, err_sip_list):
    caller_log_tmp_file_path = local_file_path + "/tmp/{}_log".format(caller_username)
    whole_log_path = get_whole_log_path(call_type, "caller")

    if caller_username in err_sip_list:
        msg = "terminal upload log error"
        caller_log = {"log_valid": "1", "state": "2", "err_msg": msg, "delay_time": "0", "analyse_prog_err": ""}

        return write_node(caller_log, "caller", call_type)
    else:
        try:
            # handle_info = com.analyse_main("caller", variable_sip_call_id, whole_log_path)
            handle_info = {"log_valid":"1", "state":"1", "err_msg": "", "delay_time":"20.665", "analyse_prog_err":""}
        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            logging.error("caller analyse_main func error: %s" % error_msg)
            handle_info = {"log_valid": "1", "state": "2", "err_msg": error_msg, "delay_time": "0", "analyse_prog_err": ""}
        logging.debug("get caller user start sign ")
        write_node(handle_info, "caller", call_type)
        if os.path.isfile(caller_log_tmp_file_path):
            os.remove(caller_log_tmp_file_path)


def freeswitch(call_type):
    whole_log_path = get_whole_log_path(call_type, "freeswitch")
    try:
        handle_info = {"log_valid": "1", "state": "1", "err_msg": "", "delay_time": "0", "analyse_prog_err": ""}
        # handle_info = com.analyse_main("nav", log_name=whole_log_path)
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        handle_info = {"log_valid": "1", "state": "2", "err_msg": error_msg, "delay_time": "0", "analyse_prog_err": ""}
        logging.error("freeswitch analyse_main func error: %s" % error_msg)

    write_node(handle_info, "freeswitch", call_type)


def dispatcher(call_type):
    whole_log_path = get_whole_log_path(call_type, "dispatcher")
    try:
        handle_info = {"log_valid": "1", "state": "1", "err_msg": "", "delay_time": "0", "analyse_prog_err": ""}
        # handle_info = com.analyse_main('dis', log_name=whole_log_path)
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        handle_info = {"log_valid": "1", "state": "2", "err_msg": error_msg, "analyse_prog_err": ""}
        logging.error("dispatcher analyse_main func error: %s" % error_msg)

    write_node(handle_info, "dispatcher", call_type)


def api(call_type):
    whole_log_path = get_whole_log_path(call_type, "api")
    try:
        handle_info = {"log_valid": "1", "state": "1", "err_msg": "", "delay_time": "0", "analyse_prog_err": ""}
        # handle_info = com.analyse_main("api", log_name=whole_log_path)
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        handle_info = {"log_valid": "1", "state": "2", "err_msg": error_msg, "analyse_prog_err":""}
        logging.error("api analyse_main func error :%s" % error_msg)

    write_node(handle_info, "api", call_type)


def mqtt(call_type):
    whole_log_path = get_whole_log_path(call_type, "mqtt")
    try:
        handle_info = {"log_valid": "1", "state": "1", "err_msg": "", "delay_time": "0", "analyse_prog_err": ""}
        # handle_info = com.analyse_main("api", log_name=whole_log_path)
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        handle_info = {"log_valid": "1", "state": "2", "err_msg": error_msg, "analyse_prog_err":""}
        logging.error("mqtt analyse_main func error :%s" % error_msg)

    write_node(handle_info, "mqtt", call_type)


def callee(callee_username_list, call_type, callee_sip_uuid, err_sip_list):
    handle_info = {"log_valid": "1", "state": "1", "err_msg": "", "delay_time": "0", "analyse_prog_err": ""}
    # clean_log_file(call_type)
    if isinstance(callee_username_list, list):
        if "single" in call_type or "urgent" in call_type:
            if not callee_username_list:
                handle_info = {"log_valid": "2", "state": "2", "err_msg": "callee is not exist", "analyse_prog_err": ""}
                return write_node(handle_info, "callee", call_type, [])
            callee_sip = callee_username_list[0]
            callee_log_tmp_file_path = local_file_path + "/tmp/{}_log".format(callee_sip)
            if callee_sip in err_sip_list:
                logging.warning("log handle(sip): {sip} terminal log upload failed.".format(sip=callee_sip))
                handle_info = {"log_valid": "2", "state": "2", "err_msg": "terminal upload log time out", "delay_time": "0", "analyse_prog_err": ""}
                whole_log_path = get_whole_log_path(call_type, "callee")
                if os.path.isfile(whole_log_path):
                    os.remove(whole_log_path)
                return write_node(handle_info, "callee", call_type, [])

            try:
                handle_info = {"log_valid": "1", "state": "1", "err_msg": "", "delay_time": "60.1166",
                               "analyse_prog_err": ""}
                # handle_info = com.analyse_main("callee", callee_sip_uuid, callee_log_tmp_file_path)
            except Exception as e:
                import traceback
                error_msg = traceback.format_exc()
                handle_info = {"log_valid": "1", "state": "2", "err_msg": error_msg, "delay_time": "0", "analyse_prog_err": ""}
            logging.debug("get callee user start sign")

            write_node(handle_info, "callee", call_type)
            path, _ = os.path.split(callee_log_tmp_file_path)
            files = os.listdir(path)
            for file in files:
                os.remove(os.path.join(path, file))
            logging.debug("callee handle log=================END=================(single)")

        else:
            user_info_list = list()
            for sip in callee_username_list:
                user_info = dict()
                user_info["name"] = sip

                callee_log_tmp_file_path = local_file_path + "/tmp/{}_log".format(sip)
                if sip in err_sip_list:
                    handle_info["state"] = "2"
                    _handle_info = {"log_valid": "1", "state": "2", "err_msg": "terminal upload log time out", "delay_time": "0", "analyse_prog_err": ""}
                    logging.warning("log handle(sip): {sip} terminal log upload failed.".format(sip=sip))
                    write_log(_handle_info, "callee", call_type=call_type, call_sip=sip)
                    user_info["state"] = _handle_info.get("state")
                    user_info["delay_time"] = _handle_info.get('delay_time', "0")
                    user_info_list.append(user_info)
                    continue
                try:
                    _handle_info = {"log_valid": "1", "state": "1", "err_msg": "", "delay_time": "60.11",
                                   "analyse_prog_err": ""}
                    # _handle_info = com.analyse_main("callee", uuid=callee_sip_uuid, log_name=callee_log_tmp_file_path)
                except Exception as e:
                    handle_info["state"] = "2"
                    import traceback
                    error_msg = traceback.format_exc()
                    _handle_info = {"log_valid": "1", "state": "2", "err_msg": error_msg, "delay_time": "0", "analyse_prog_err": ""}
                    logging.error(error_msg)

                user_info["state"] = _handle_info.get("state")
                user_info["delay_time"] = _handle_info.get('delay_time', "0")
                user_info_list.append(user_info)
                logging.debug("log handle(sip): {sip} handle success".format(sip=sip))
                write_log(_handle_info, "callee", call_type=call_type, call_sip=sip)
                if os.path.isfile(callee_log_tmp_file_path):
                    os.remove(callee_log_tmp_file_path)

            write_conf(handle_info, "callee", call_type=call_type, user_info=user_info_list)
            logging.debug("handle log ===============END===============(group)")
    else:
        msg = "log_handle is err please call manager(callee mode need callee_username_list is a list not other type)"
        handle_info["err_msg"] = msg
        handle_info["state"] = 2
        write_node(handle_info, "callee", call_type)
        logging.warning("handle log ==============END==============")


def write_node(handle_info, mode, call_type, user_info=None):
    """
    写和前端交互的文本  && 和需要展示的log日志文件
    """
    logging.debug("%s write_node " % mode)
    # 视频单呼组呼，音频单呼组呼。
    if call_type in ["audiosingle", "videosingle", "videogroup", "audiogroup", "mulgroup", "urgentaudio"]:
        write_conf(handle_info, mode, call_type=call_type, user_info=user_info)
        write_log(handle_info, mode, call_type=call_type)


def write_conf(handle_info, mode, call_type=None, user_info=None):
    state = handle_info.get('state', "2")
    delay_time = handle_info.get("delay_time")
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
            delay_time = str(round(int(delay_time), 2))
            conf_json.get("step_list").get(mode)["delay_time"] = delay_time
        if mode == "callee" and user_info:
            conf_json.get("step_list").get(mode)["user_list"] = user_info
    with open(os.path.join(conf_file_path, conf_file_name), "w") as conf_file:
        conf_file.truncate()
        json.dump(conf_json, conf_file, ensure_ascii=False)


def write_log(handle_info, mode, call_type=None, call_sip=None):
    logging.debug("%s start to write log file " % mode)
    err_msg = handle_info.get("err_msg")
    if not call_type:
        call_type = handle_info.get("call_type")[0]
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

    if handle_info:
        handle_log_file = mode_show_log_path + "handle_log"
        with open(handle_log_file, "w") as handle_log_file:
            handle_msg_str = json.dumps(handle_info)
            handle_log_file.write(handle_msg_str)


def get_whole_log_path(call_type, mode):
    if call_type == "audiosingle":
        return show_log_path + "start_single_audio_call/" + mode + "/whole_log"
    elif call_type == "videosingle":
        return show_log_path + "start_single_video_call/" + mode + "/whole_log"
    elif call_type in ["audiogroup", "mulgroup"]:
        return show_log_path + "start_group_audio_call/" + mode + "/whole_log"
    elif call_type == "videogroup":
        return show_log_path + "start_group_video_call/" + mode + "/whole_log"
    elif call_type == "urgentaudio":
        return show_log_path + "start_urgent_single_audio_call/" + mode + "/whole_log"


def set_server_log_line(mode, new_start_bytes):
    redis_client = redis.StrictRedis(host=redis_host, port=redis_port, db=2, decode_responses=True)
    last_start_bytes = redis_client.hget(name=mode, key="last_start_bytes")
    if not last_start_bytes:
        last_start_bytes = "0"
    redis_client.hset(name=mode, key="old_start_bytes", value=last_start_bytes)
    redis_client.hset(name=mode, key="last_start_bytes", value=new_start_bytes)
    redis_client.close()


def clean_log_file(call_type, mode):
    whole_log_path = get_whole_log_path(call_type, mode)
    mode_show_log_path, _ = os.path.split(whole_log_path)
    if os.path.exists(mode_show_log_path):
        ls_log_path = os.listdir(mode_show_log_path)
        for _file in ls_log_path:
            c_path = os.path.join(mode_show_log_path, _file)
            if os.path.isdir(c_path):
                rmtree(c_path)
            else:
                os.remove(c_path)


def update_whole_state(call_type, mode, user_info_list=None):
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
    conf_file_path = app.config["CONF_FILE_PATH"]

    with open(os.path.join(conf_file_path, conf_file_name), "r") as conf_file:
        conf_json = json.load(conf_file)
        conf_json.get("step_list").get(mode)["show_whole_log"] = True
        if user_info_list:
            conf_json.get("step_list").get(mode)["user_list"] = user_info_list

    with open(os.path.join(conf_file_path, conf_file_name), "w") as conf_file:
        conf_file.truncate()
        json.dump(conf_json, conf_file, ensure_ascii=False)
