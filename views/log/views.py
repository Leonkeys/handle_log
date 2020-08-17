import os
from . import log
from werkzeug.utils import secure_filename
from flask import request, redirect, flash

from manage import app
import pandas as pd


@log.route("/get", methods=["POST"])
def get_server_log():
    """
    copy server running log
    request:
        ip: server ip
        path: log path
        user: user
        pw: password
        sshpass -p nutrunck@@ scp root@192.168.22.90:/home/freeswitch/log/dispatcher.log ./
        freeswitch.log
    """
    ip = request.form.get("ip", "192.168.22.90")
    path = request.form.get('path', "/home/freeswitch/log")
    user = request.form.get("user", "root")
    password = request.form.get("pw", "nutrunck@@")
    file_name = request.form.get("file_name", "freeswitch.log")
    info = os.system("sshpass -p {password} scp {user}@{ip}:{path}/{file_name} /home/nufront/".format(
        password=password, user=user, ip=ip, path=path, file_name=file_name))
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
        # if 'file' not in request.files:
        #     flash('No file part')
        #     return redirect(request.url)
        file = request.files['file']
        #
        # if file.filename == '':
        #     flash('No selected file')
        #     return redirect(request.url)
        # if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.isfile(filepath):
            file.save(filepath)
        else:
            os.makedirs(app.config['UPLOAD_FOLDER'] + filename)
            file.save(filepath)
        return '{"filename":"%s"}' % filename
    # TODO 日志分析
    return ' '


def log_handle():
    """
    日志分析
    日至输出格式：(datetime|时间戳) + level + uuid + operation + message

    :return:
    """
    # TODO
    pass
