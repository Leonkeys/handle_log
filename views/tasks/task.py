import json
import redis
from settings import MQTT_HOST, MQTT_PORT, MQTT_PASSWORD, MQTT_USERNAME, REDIS_HOST, REDIS_PORT, HOST,PORT
from paho.mqtt import client as mqtt_client
from apscheduler.schedulers.background import BackgroundScheduler
from views.tasks.offline_logfile_rsync import rsync_remote_log

job_list = [
    # {
    #     "func": "clean_line",
    #     "trigger": "interval",
    #     "seconds": 20
    # },

    # {
    #     "func": "rsync_remote_log",
    #     "trigger": "interval",
    #     "seconds": 22
    # }
]


def clean_line():
    client = mqtt_client.Client()
    client.connect(host=MQTT_HOST, port=MQTT_PORT, keepalive=600)
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    payload = {
        "option": "clean_offset",
        "url": "http://{}:{}/log/clean".format(HOST, PORT)
    }
    payload_str = json.dumps(payload)
    print("task public topic: clean_offset, payload:{}".format(payload_str))
    client.publish("/5476752146/clean_offset", payload_str, 1)


def add_job(scheduler):

    for job in job_list:
        delay_func = job.pop("func")
        scheduler.add_job(eval(delay_func), **job)


def core():
    print("delay task start ")
    scheduler = BackgroundScheduler()
    add_job(scheduler)
    print("started delay task", scheduler.get_jobs())
    scheduler.start()


# if __name__ == '__main__':
    # Thread(target=core).start()