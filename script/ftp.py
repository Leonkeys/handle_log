from ftplib import FTP


def upload(filepath, targetdir, ftpserver, user, password):
    """

    :param filepath: 要上传的文件的绝对路径
    :param targetdir:ftp服务器文件存储路径
    :param ftpserver:ftp 服务器连接信息  ip port
    :param user:   ftp 用户名
    :param password: ftp密码
    :return:
    """
    filename = filepath.split("/")[-1]
    ftp = FTP(ftpserver)  # connect obj
    try:
        ftp.login(user, password)
    except:
        raise Exception("用户名或密码有误。")
    fp = open(filepath, "rb")
    buf_size = 1024
    ftp.storbinary("STOR {}".format(targetdir + "/" + filename), fp, buf_size)
    ftp.close()


def download(local_path, remote_path, ftpserver, user, password):
    """
    :param filepath: 要xiazai的文件的绝对路径
    :param targetdir: ftp服务器文件存储路径
    :param ftpserver: ftp 服务器连接信息  ip port
    :param user:   ftp 用户名
    :param password: ftp密码
    :return:
    """
    ftp = FTP(ftpserver)
    try:
        ftp.login(user, password)
    except:
        raise Exception("用户名或密码有误。")
    buf_size = 1024
    if isinstance(remote_path, list):
        for remote_file in remote_path:
            filename = remote_file.split("/")[-1]
            fp = open(local_path + "/" + filename, "wb")
            ftp.retrbinary("RETR {}".format(remote_path), fp.write, buf_size)
    else:
        filename = remote_path.split("/")[-1]
        fp = open(local_path + "/" + filename, "wb")
        ftp.retrbinary("RETR {}".format(remote_path), fp.write, buf_size)

    ftp.close()


# upload("/home/nufront/桌面/requirements.txt", "/home/ftpuser1", "192.168.22.165", "ftpuser1", "123456")
# download("/home/nufront/桌面/ffffff", "/home/ftpuser1/requirements.txt", "192.168.22.165", "ftpuser1", "123456")
