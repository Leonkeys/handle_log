# setting


HOST = "0.0.0.0"

PORT = "8004"

DEBUG = True

ALLOWED_EXTENSIONS = set(['log'])

UPLOAD_FOLDER = "/tmp/"

server_ip = "192.168.22.90"
# navita_log_path = "/home/freeswitch/log"
user = "root"
password = "nutrunck@@"
# freeswitch_log = "freeswitch.log"
# dispatcher_log = "dispatcher.log"
log_path_list = {
    "freeswitch": "freeswitch.log",
    "dispatcher": "dispatcher.log",
    "mqtt": "mqtt.log",
    "api": "api.log"
}


local_path = "/home/nufront/桌面/log/"
# 2020-08-18 18:54:43.087537
# sshpass -p "nutrunck@@" rsync  root@192.168.22.90:/home/navita/log/freeswitch.log ./   带密码增量远程拷贝

conf_file_path = "/home/nufront/桌面/config"