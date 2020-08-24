from flask import Blueprint

log = Blueprint('log', __name__)

from .views import *

import pymysql
pymysql.install_as_MySQLdb()