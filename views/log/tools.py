from settings import local_path
from settings import ALLOWED_EXTENSIONS


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def freeswitch(channel_call_uuid, filename):
    """
    截取当前通话相关的日志&&freeswitch日志分析
    """
    local_file = local_path + "/" + filename
    new_file_list = []
    with open(local_file, "rb") as old_local_file:
        line = old_local_file.readline()
        if line and channel_call_uuid in line:
            new_file_list.append(line)
    # TODO freeswitch日志分析

    return 1


def dispatcher():
    """
    dispatcher日志分析
    """
    pass


def mqtt():
    """
    mqtt日志分析
    """
    pass


def api():
    """
    api日志分析
    """
    pass


def write_node(func):
    """
    写和前端交互的文本
    """

