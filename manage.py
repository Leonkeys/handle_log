from flask import Flask
from threading import Thread
from flask_docs import ApiDoc
from flask_cors import CORS
from views.websocket import websocket
from views.log import log, views
from views.tasks import task
app = Flask(__name__, template_folder="templates", static_folder="static/countdown_files")

# 解决跨域
CORS(app, supports_credentials=True)

app.register_blueprint(websocket, url_prefix="/websocket")
app.register_blueprint(log, url_prefix="/log")
# api docs config
app.config["API_DOC_MEMBER"] = ["log", "portal", "websocket"]


# setting
app.config.from_object("settings")
# api docs  ask  ip:port/docs/api
ApiDoc(app)

if __name__ == '__main__':
    Thread(target=task.core).start()
    Thread(target=views.listen_ESL).start()
    Thread(target=views.log_handle).start()
    app.run(host=app.config["HOST"], port=app.config["PORT"], debug=False, threaded=True)

