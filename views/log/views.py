import os
import threading
import queue
from . import log
from werkzeug.utils import secure_filename
from flask import request, redirect, flash
from .tools import *
import json
from ESL import *
from manage import app


q = queue.Queue(20)
local_file_path = app.config["LOCAL_FILE_PATH"]


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
        # if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.isfile(filepath):
            file.save(filepath)
        else:
            os.makedirs(app.config['UPLOAD_FOLDER'] + filename)
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

    con = ESLconnection("192.168.22.40", "8021", "ClueCon")

    if con.connected():
        con.events("json", "CHANNEL_CREATE")
        # celery
        while 1:
            msg = con.recvEvent()
            if msg:
                print(msg.serialize("json"))
                q.put(msg)


def log_handle():
    while 1:
        msg = q.get()
        # print(msg.serialize("json"))
        create_channel_dict = json.loads(msg.serialize("json"))
        caller_username = create_channel_dict.get("Caller-Username")  # 呼叫者id
        caller_destination_number = create_channel_dict.get("Caller-Destination-Number")  # 被呼叫者id
        core_uuid = create_channel_dict.get("Core-UUID")
        channel_call_uuid = create_channel_dict.get("Unique-ID")

        log_path_list = app.config['LOG_PATH_LIST']
        local_path = app.config['LOCAL_FILE_PATH']
        for func, remote_log_path in log_path_list.items():
            filename = remote_log_path.split("/")[-1]
            get_server_log(remote_log_path, local_path)
            log_threading = threading.Thread(target=call_func, args=(func, core_uuid, channel_call_uuid, filename))
            log_threading.start()
            # call_func(func, core_uuid, channel_call_uuid, filename)
            # freeswitch(core_uuid, channel_call_uuid, filename)


if __name__ == '__main__':
    listen_ESL()
