from flask import Flask
from flask_docs import ApiDoc
from views.portal import portal
from views.websocket import websocket
from views.log import log
app = Flask(__name__)

app.register_blueprint(portal, url_prefix="/portal")
app.register_blueprint(websocket, url_prefix="/websocket")
app.register_blueprint(log, url_prefix="/log")
# api docs config
app.config["API_DOC_MEMBER"] = ["log", "portal", "websocket"]


# setting
app.config.from_object("settings")
# api docs  ask  ip:port/docs/api
ApiDoc(app)

if __name__ == '__main__':
    app.run(host=app.config["HOST"], port=app.config["PORT"], debug=app.config["DEBUG"])

