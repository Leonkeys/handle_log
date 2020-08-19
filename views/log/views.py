import os
from . import log
from werkzeug.utils import secure_filename
from flask import request, redirect, flash
from .tools import *
import json
from ESL import *
from manage import app
import pandas as pd


# @log.route("/get", methods=["POST"])
def get_server_log(remote_path, local_path=None):
    """
    copy server running log
    request:
        remote_path  服务器端日志路径，根据所传日志动态传入
        local_path   本地日志存储路径

    """
    # ip = request.form.get("ip", "192.168.22.90")
    # path = request.form.get('path', "/home/freeswitch/log")
    # user = request.form.get("user", "root")
    # password = request.form.get("pw", "nutrunck@@")
    # file_name = request.form.get("file_name", "freeswitch.log")
    # sshpass -p "nutrunck@@" rsync  root@192.168.22.90:/home/navita/log/freeswitch.log ./
    password = app.config['password']
    user = app.config['user']
    ip = app.config['server_ip']
    local_path = local_path if local_path else app.config['local_path']
    info = os.system("sshpass -p {password} rsync {user}@{ip}:{remote_path} {local_path}".format(
        password=password, user=user, ip=ip, remote_path=remote_path, local_path=local_path))
    # TODO 日志分析
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
    return func(*args, **kwargs)


def listen_ESL():
    '''
    ADD_SCHEDULE DEL_SCHEDULE CHANNEL_DESTROY CHANNEL_CREATE CHANNEL_ANSWER CHANNEL_HANGUP CUSTOM conference::maintenance
    '''

    con = ESLconnection("192.168.22.90", "8021", "ClueCon")

    if con.connected():
        con.events("json", "CHANNEL_CREATE")
        # celery
        while 1:
            msg = con.recvEvent()
            if msg:
                print(msg.serialize("json"))
                create_channel_dict = json.loads(msg.serialize("json"))
                caller_username = create_channel_dict.get("Caller-Username")  # 呼叫者id
                caller_destination_number = create_channel_dict.get("Caller-Destination-Number")  # 被呼叫者id
                channel_call_uuid = create_channel_dict.get("Channel-Call-UUID")

                log_path_list = app.config['log_path_list']
                local_path = app.config['local_path']
                for func, remote_log_path in log_path_list.items():
                    filename = remote_log_path.split("/")[-1]
                    get_server_log(remote_log_path, local_path)
                    result = call_func(func, channel_call_uuid, filename)
                    # TODO 写和前端交互的文本
                    write_node(func)
                import time
                time.sleep(1)


if __name__ == '__main__':
    listen_ESL()
