import os
import threading
import queue
from . import log
from werkzeug.utils import secure_filename
from flask import request, redirect, flash, render_template
from .tools import *
import json
from ESL import *
from manage import app


q = queue.Queue(20)
local_file_path = app.config["LOCAL_FILE_PATH"]
ESL_HOST = app.config['ESL_HOST']
ESL_PORT = app.config['ESL_PORT']
ESL_PASSWORD = app.config['ESL_PASSWORD']

remote_log_path_list = app.config['REMOTE_LOG_PATH_LIST']


def get_server_log(remote_path, local_path=None):
    """
    copy server running log
    request:
        remote_path  服务器端日志路径，根据所传日志动态传入
        local_path   本地日志存储路径

    """

    password = app.config['PASSWORD']
    user = app.config['USER']
    ip = app.config['SERVER_IP']
    local_path = local_path if local_path else local_file_path
    info = os.system("sshpass -p {password} rsync {user}@{ip}:{remote_path} {local_path}/".format(
        password=password, user=user, ip=ip, remote_path=remote_path, local_path=local_path))
    return {"a": info}

# @log.route("/TRUNCKLOG", methods=["GET"])
# def index():
#     return render_template("index.html")


@log.route("/upload", methods=["GET", "POST"])
def upload_file():
    """
    android and windows upload file
    request:
        file
    :return:
    """
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']

        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        filename = secure_filename(file.filename)
        filepath = os.path.join(local_file_path, filename)
        if os.path.isfile(filepath):
            file.save(filepath)
        else:
            if not local_file_path:
                os.makedirs(local_file_path)
            os.mknod(filepath)
            file.save(filepath)
        return '{"filename":"%s"}' % filename
    return ' '


def call_func(func, *args, **kwargs) -> int:
    """
    callback
    """
    return eval(func)(*args, **kwargs)


def listen_ESL():
    '''
    ADD_SCHEDULE DEL_SCHEDULE CHANNEL_DESTROY CHANNEL_CREATE CHANNEL_ANSWER CHANNEL_HANGUP CUSTOM conference::maintenance
    '''

    msg_dict = dict()
    con = ESLconnection(ESL_HOST, ESL_PORT, ESL_PASSWORD)

    if con.connected():
        con.events("json", "CHANNEL_CREATE")
        # celery
        while 1:
            msg = con.recvEvent()
            if msg:
                print(msg.serialize("json"))
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
    while 1:
        create_channel_dict_l = q.get()
        print(create_channel_dict_l)
        # create_channel_dict = json.loads(msg.serialize("json"))
        # caller_username = create_channel_dict_l.get("Caller-Username")  # 呼叫者id
        # caller_destination_number = create_channel_dict_l.get("Caller-Destination-Number")  # 被呼叫者id
        core_uuid = create_channel_dict_l[0].get("Core-UUID")
        unique_id_list = [i.get("Unique-ID") for i in create_channel_dict_l]

        caller()
        for func, remote_log_path in remote_log_path_list.items():
            filename = remote_log_path.split("/")[-1]
            get_server_log(remote_log_path, local_file_path)
            # log_threading = threading.Thread(target=call_func, args=(func, core_uuid, channel_call_uuid, filename))
            # log_threading.start()
            call_func(func, core_uuid, unique_id_list, filename)


if __name__ == '__main__':
    listen_ESL()
