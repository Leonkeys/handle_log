from apscheduler.schedulers.background import BackgroundScheduler
from views.tasks.offline_logfile_rsync import rsync_remote_log

job_list = [
    {
        "func": "clean_line",
        "trigger": "interval",
        "seconds": 20
    },

    {
        "func": "rsync_remote_log",
        "trigger": "interval",
        "seconds": 22
    }

]


def clean_line():
    # TODO 定时备份和临时文件日志清除日志
    pass


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
