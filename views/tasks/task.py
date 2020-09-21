import json
import redis
from settings import MQTT_HOST, MQTT_PORT, MQTT_PASSWORD, MQTT_USERNAME, REDIS_HOST, REDIS_PORT
from paho.mqtt import client as mqtt_client
from apscheduler.schedulers.background import BackgroundScheduler
job_list = [
    # {
        # "func": "clean_line",
        # "trigger": "interval",
        # "seconds": 20
    # }
]


def clean_line():
    client = mqtt_client.Client()
    client.connect(host=MQTT_HOST, port=MQTT_PORT, keepalive=600)
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    payload = {
        "option": "upload",
    }
    payload_str = json.dumps(payload)
    client.publish("/5476752146/upload", payload_str, 1)
    redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
    redis_client.flushdb()
    redis_client.close()


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


if __name__ == '__main__':
    clean_line()

    # Thread(target=core).start()