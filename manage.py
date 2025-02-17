from flask import Flask
from threading import Thread
from flask_docs import ApiDoc
from flask_cors import CORS
from setup_log import setup_log
from setup_log import Config, ProductionConfig
from views.websocket import websocket
from views.log import log, views
from views.tasks import task
app = Flask(__name__)
CORS(app, supports_credentials=True)

app.config['SECRET_KEY'] = '123456'

app.register_blueprint(websocket, url_prefix="/websocket")
app.register_blueprint(log, url_prefix="/log")
# api docs config
app.config["API_DOC_MEMBER"] = ["log", "portal", "websocket"]

# log
setup_log(Config())
# setting
app.config.from_object("settings")
# api docs  ask  ip:port/docs/api
ApiDoc(app)

if __name__ == '__main__':
    Thread(target=task.core).start()
    Thread(target=views.listen_ESL).start()
    Thread(target=views.log_handle).start()
    app.run(host=app.config["RUN_HOST"], port=app.config["RUN_PORT"], debug=app.config["DEBUG"], threaded=True)

