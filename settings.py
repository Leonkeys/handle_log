# setting


HOST = "0.0.0.0"

PORT = "8004"

DEBUG = True


SERVER_IP = "192.168.22.40"

USER = "root"
PASSWORD = "nutrunck@@"

LOG_PATH_LIST = {
    "freeswitch": "/home/Trunck/navita/log/freeswitch.log",
    # "dispatcher": "/home/navita/log/dispatcher.log",
    # "mqtt": "mqtt.log"
}

LOCAL_FILE_PATH = "/home/nufront/桌面/local_log"

TEMPLATE_CONF_FILE_PATH = "/home/nufront/桌面/config/template/"
CONF_FILE_PATH = "/home/nufront/桌面/config/"
# sqlalchemy config
DB_CONNECT = "mysql+pymysql://root:123456@192.168.22.165:3306/log_handle?charset=utf8"
SQLALCHEMY_DATABASE_URI = DB_CONNECT
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ECHO = True
