from logging.handlers import RotatingFileHandler
import logging
import os


# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = "/home/nufront"


class Config(object):

    # log level
    LOG_LEVEL = logging.DEBUG


class ProductionConfig(object):

    LOG_LEVEL = logging.ERROR


# def setup_log(config):
#     # set log level
#     logging.basicConfig(level=config.LOG_LEVEL)
#     logger = logging.getLogger("log")
#     # create log && set log save path && any log file max size && number of log file
#     if not os.path.exists(os.path.join(BASE_DIR, "logs")):
#         os.makedirs(os.path.join(BASE_DIR, "logs/"))
#     file_log_handler = RotatingFileHandler(os.path.join(BASE_DIR, "logs/log"), maxBytes=1024 * 1024 * 100, backupCount=10)
#
#     # create log format && log level && log file name && lenes && log info
#     formatter = logging.Formatter("%(levelname)s %(filename)s: %(lineno)d %(message)s")
#
#     # save
#     file_log_handler.setFormatter(formatter)
#     logging.getLogger().addHandler(file_log_handler)


def setup_log(config):
    # TODO  rewrite logging
    logger = logging.getLogger()
    logger.setLevel(config.LOG_LEVEL)

    if not os.path.exists(os.path.join(BASE_DIR, "logs")):
        os.makedirs(os.path.join(BASE_DIR, "logs"))
    handler = logging.FileHandler(os.path.join(BASE_DIR, "logs/webserver.log"))
    handler.setLevel(config.LOG_LEVEL)

    console = logging.StreamHandler()
    console.setLevel(config.LOG_LEVEL)

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    handler.setFormatter(formatter)
    console.setFormatter(formatter)
    logger.addHandler(handler)
    logger.addHandler(console)
