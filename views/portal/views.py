from . import portal
from flask import request


# @portal.route('/get/<body>', methods=["GET", "POST"])
# def get(body):
#     """
#     url: /portal/get
#     :return:
#     """
#     name = request.args.get("name")
#
#     if request.method == "POST":
#         args = request.form.get("args")  # 获取post请求 请求体的参数
#
#     else:
#         args = request.args.get("args")  # 获取get请求 请求url的参数 ip:port/portal/get?args=1
#
#     return 1