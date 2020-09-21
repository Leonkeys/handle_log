import os
import logging
import threading
import queue
from . import log
from flask import request, redirect
from .tools import *
import json
from ESL import *
from manage import app
q = queue.Queue(20)
redis_host = app.config['REDIS_HOST']
redis_port = app.config["REDIS_PORT"]
ESL_HOST = app.config['ESL_HOST']
ESL_PORT = app.config['ESL_PORT']
ESL_PASSWORD = app.config['ESL_PASSWORD']
local_file_path = app.config["LOCAL_FILE_PATH"]
remote_log_path_list = app.config['REMOTE_LOG_PATH_LIST']


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


@log.route("/upload", methods=["GET", "POST"])
def upload_file():
    """
    android and windows upload file
    request:
        file
        call_mode  呼叫类型 callee||caller
        core_uuid  标识呼叫的uuid
        call_sip
    :return:
    """
    if request.method == 'POST':
        print("api is ready")
        if 'file' not in request.files:
            print('No file part')
            return redirect(request.url)
        file = request.files.get('file')
        call_sip = request.form.get('call_sip')

        if file.filename == '':
            print('No selected file')
            return redirect(request.url)
        filename = "{}_log".format(call_sip)
        file_floder_path = local_file_path + "/tmp"
        filepath = os.path.join(file_floder_path, filename)
        print(filepath)
        if not os.path.exists(file_floder_path):
            os.makedirs(file_floder_path)
            with open(filepath, "wb") as filepath:
                filepath.write(file.read())
        else:
            if not os.path.exists(file_floder_path):
                os.makedirs(file_floder_path)
            file.save(filepath)
        return '{"filename":"%s"}' % filename
    return ' '


def call_func(func, *args, **kwargs):
    """
    callback
    """
    eval(func)(*args, **kwargs)


def listen_ESL():
    '''
    ADD_SCHEDULE DEL_SCHEDULE CHANNEL_DESTROY CHANNEL_CREATE CHANNEL_ANSWER CHANNEL_HANGUP CUSTOM conference::maintenance
    '''
    print("listen esl start")
    msg_dict = dict()
    con = ESLconnection(ESL_HOST, ESL_PORT, ESL_PASSWORD)

    if con.connected():
        con.events("json", "CHANNEL_CREATE CHANNEL_PROGRESS")
        # celery
        while 1:
            msg = con.recvEvent()
            if msg:
                # print(msg.serialize("json"))
                create_channel_dict = json.loads(msg.serialize("json"))
                core_uuid = create_channel_dict.get("Core-UUID")
                if core_uuid not in msg_dict:
                    msg_dict[core_uuid] = [create_channel_dict]
                    threading.Timer(2, put_msg, [core_uuid, msg_dict]).start()

                elif core_uuid in msg_dict:
                    msg_dict[core_uuid].append(create_channel_dict)


def put_msg(core_uuid, msg_dict):
    q.put(msg_dict[core_uuid])
    del msg_dict[core_uuid]


def log_handle():
    print("log_handle-start")
    while 1:
        create_channel_dict_l = q.get()
        caller_username = create_channel_dict_l[0].get("variable_sip_from_user")  # 呼叫者id
        callee_username = create_channel_dict_l[0].get("variable_sip_to_user")  # 被呼叫者id
        core_uuid = create_channel_dict_l[0].get("Core-UUID")
        caller_sip_uuid, callee_sip_uuid = get_sip_uuid(create_channel_dict_l)
        unique_id_list = [i.get("Unique-ID") for i in create_channel_dict_l]

        caller(core_uuid, caller_username, caller_sip_uuid)
        for func, remote_log_path in remote_log_path_list.items():
            if func == "mqtt":
                remote_log_path = get_mqtt_log_path(remote_log_path)
                filename = "emqttd.log"
                remote_log_path = remote_log_path + "/" + filename
            elif func == "api":
                filename = time.strftime("%Y%m%d", time.localtime()) + ".log"
                remote_log_path = remote_log_path + filename
            else:  # str
                filename = remote_log_path.split("/")[-1]
            if remote_log_path:
                get_server_log(remote_log_path)
            call_func(func, core_uuid, unique_id_list, filename)

        callee(core_uuid, callee_username, callee_sip_uuid)


if __name__ == '__main__':
    listen_ESL()
