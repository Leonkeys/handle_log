from flask import Blueprint

websocket = Blueprint('websocket', __name__)

from .views import *