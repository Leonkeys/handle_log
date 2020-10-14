import os
import logging
import redis
import threading
import queue
from . import log
from flask import request, redirect, make_response
from .tools import *
import json
from ESL import *
from manage import app
from concurrent.futures import ThreadPoolExecutor
start_call_queue = queue.Queue(20)
end_call_queue = queue.Queue(20)
redis_host = app.config['REDIS_HOST']
redis_port = app.config["REDIS_PORT"]
ESL_HOST = app.config['ESL_HOST']
ESL_PORT = app.config['ESL_PORT']
ESL_PASSWORD = app.config['ESL_PASSWORD']
local_file_path = app.config["LOCAL_FILE_PATH"]
remote_log_path_list = app.config['REMOTE_LOG_PATH_LIST']

redis_client = redis.StrictRedis(host=redis_host, port=redis_port, db=0, decode_responses=True)
executor = ThreadPoolExecutor(10)


@log.route("/upload", methods=["POST"])
def upload_file():
    """
    android and windows upload file
    request:
        file
        call_sip
        clean_offset: <boolean> emq中传递的偏移值与终端对应不上的时候，终端主动上传该参数为true，
    :return:
    """
    if request.method == 'POST':
        print("upload_file")
        if 'file' not in request.files:
            print('No file part')
            return redirect(request.url)
        file = request.files.get('file')
        call_sip = request.form.get('call_sip')
        clean_offset = request.form.get("clean_offset", "False")
        if clean_offset == "true":
            redis_client.hdel(call_sip, "start_line", "start_bytes")
        if file.filename == '':
            print('No selected file')
            return redirect(request.url)
        filename = "{}_log".format(call_sip)
        file_floder_path = local_file_path + "/tmp"
        if not os.path.exists(file_floder_path):
            os.makedirs(file_floder_path)
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
        update_start_sign(call_sip, filepath)
        executor.submit(update_start_sign, call_sip, filepath)
        return '{"filename":"%s"}' % filename
    return ' '


@log.route("/clean", methods=["POST"])
def clean_offset():
    """
    the function is clean redis one sip sign to 0, 0.
    emq: topic: /5475762146/clean_offset
        payload<json>:{"option":"clean_offset","url":"http://ip:port/log/clean"}
    request <form-data>:
        call_sip:<用户sip号>
    """
    if request.method.upper() == "POST":
        call_sip = request.form.get("call_sip")
        print("clean_offset：%s" % call_sip)
        redis_client.hdel(call_sip, "start_line", "start_bytes")
        resp = make_response({"state": "is_success"})
        resp.status = "200"
        return resp


def listen_ESL():
    '''
    ADD_SCHEDULE DEL_SCHEDULE CHANNEL_DESTROY CHANNEL_CREATE CHANNEL_ANSWER CHANNEL_HANGUP CUSTOM conference::maintenance
    '''
    print("listen esl start")
    start_msg_dict = dict()
    end_msg_dict = dict()
    con = ESLconnection(ESL_HOST, ESL_PORT, ESL_PASSWORD)

    if con.connected():
        con.events("json", "CHANNEL_CREATE CHANNEL_PROGRESS")
        # celery
        while 1:
            msg = con.recvEvent()
            if msg:
                print(msg.serialize("json"))
                create_channel_dict = json.loads(msg.serialize("json"))
                core_uuid = create_channel_dict.get("Core-UUID")
                event_name = create_channel_dict.get("Event-Name")
                if core_uuid not in start_msg_dict and event_name in ["CHANNEL_CREATE", "CHANNEL_PROGRESS"]:
                    start_msg_dict[core_uuid] = [create_channel_dict]
                    threading.Timer(2, put_msg, [core_uuid, start_msg_dict]).start()
                elif core_uuid not in end_msg_dict and event_name in ["CHANNEL_HANGUP"]:
                    end_msg_dict[core_uuid] = [create_channel_dict]
                    threading.Timer(2,  put_msg, [core_uuid, end_msg_dict]).start()
                elif core_uuid in start_msg_dict:
                    start_msg_dict[core_uuid].append(create_channel_dict)
                elif core_uuid in end_msg_dict:
                    end_msg_dict[core_uuid].append(create_channel_dict)


def call_func(func, *args, **kwargs):
    """
    callback
    """
    eval(func)(*args, **kwargs)


def put_msg(core_uuid, msg_dict):
    start_call_queue.put(msg_dict[core_uuid])
    del msg_dict[core_uuid]


def log_handle():
    print("log_handle-start")
    while 1:
        try:
            create_channel_dict_l = start_call_queue.get()
            call_type, build_id = get_call_type(create_channel_dict_l)
        except:
            call_type = None
            build_id = None
            logging.error("error")
        if call_type and build_id:

            write_build_id(call_type, build_id)
            caller_username, callee_username_list = get_call_username(create_channel_dict_l)
            # caller_username = create_channel_dict_l[0].get("variable_sip_from_user")  # 呼叫者id
            # callee_username = create_channel_dict_l[0].get("variable_sip_to_user")  # 被呼叫者id
            core_uuid = create_channel_dict_l[0].get("Core-UUID")
            caller_sip_uuid, callee_sip_uuid = get_sip_uuid(create_channel_dict_l)
            unique_id_list = [i.get("Unique-ID") for i in create_channel_dict_l if i.get("Event-Name") == "CHANNEL_CREATE"]

            caller(core_uuid, caller_username, call_type, caller_sip_uuid)
            for func, remote_log_path in remote_log_path_list.items():
                logging.debug("func: %s" % func)
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
                call_func(func, core_uuid, unique_id_list, filename, call_type)

            callee(core_uuid, callee_username_list, call_type, callee_sip_uuid)


if __name__ == '__main__':
    listen_ESL()
