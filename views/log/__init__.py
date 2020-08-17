from flask import Blueprint

log = Blueprint('log', __name__)

from .views import *