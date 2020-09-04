# setting

# run setting
HOST = "0.0.0.0"
PORT = "8004"
DEBUG = True


# server
SERVER_IP = "192.168.22.40"
USER = "root"
PASSWORD = "nutrunck@@"


# ESL
ESL_HOST = "192.168.22.40"
ESL_PORT = "8021"
ESL_PASSWORD = "ClueCon"


# log path
REMOTE_LOG_PATH_LIST = {
    "freeswitch": "/home/Trunck/navita/log/freeswitch.log",
    # "dispatcher": "/home/Trunck/navita/log/dispatcher.log",
}
LOCAL_FILE_PATH = "/home/nufront/桌面/local_log"
CALLER_LOG_PATH = "/home/nufront/桌面/local_log/caller/"
CALLEE_LOG_PATH = "/home/nufront/桌面/local_log/callee/"
SHOW_LOG_PATH = "/home/nufront/桌面/log/"

# config file
# TEMPLATE_CONF_FILE_PATH = "/home/nufront/桌面/conf/template/"
# CONF_FILE_PATH = "/home/nufront/桌面/conf/"

TEMPLATE_CONF_FILE_PATH = "/home/nufront/桌面/html/TRUNCKLOG/countdown_files/conf/template/"
CONF_FILE_PATH = "/home/nufront/桌面/html/TRUNCKLOG/countdown_files/conf/"
# TEMPLATE_CONF_FI# LE_PATH = "./static/countdown_files/conf/template/"
# CONF_FILE_PATH = "./static/countdown_files/conf/"


# sqlalchemy config
DB_CONNECT = "mysql+pymysql://root:123456@192.168.22.165:3306/log_handle?charset=utf8"
SQLALCHEMY_DATABASE_URI = DB_CONNECT
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ECHO = True
