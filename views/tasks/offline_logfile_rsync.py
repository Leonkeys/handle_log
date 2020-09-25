import paramiko
import subprocess
import os, sys, stat
import logging
import time
#from settings import  SERVER_IP

logging.basicConfig(level=logging.DEBUG,
        format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        filename='./rsync_remote_file.log',
        filemode='a')
logging.info("###################################################################")

hostname = '192.168.22.90'
#hostname = SERVER_IP
print("offline host: ", hostname)
username = 'root'
password = 'nuard@@'
port = 22
locate_lists = ['/tmp/locate.src', '/tmp/locate.dst', '/tmp/locate.diff']
dict_path = {'locate_lists': locate_lists, 'dst_db': '/tmp/locate.db',
        'src_db': '/tmp/locate.db', 'remote_path': '/home/Trunck/',
        'local_ftp_path': '/home/ftpuser/', 'passwd_file': '/etc/rsyncd.pwd'}

ftp_path = {
        'ftp_dis_path' : dict_path['local_ftp_path'] + 'dis',
        'ftp_navita_path' :  dict_path['local_ftp_path'] + 'navita',
        'ftp_navita_stream_path' : dict_path['local_ftp_path'] + 'navita_stream',
        'ftp_ruleEngine_path' : dict_path['local_ftp_path'] + 'ruleEngine',
        'ftp_apache_path' : dict_path['local_ftp_path'] + 'apache',
        'ftp_mqtt_path' : dict_path['local_ftp_path'] + 'mqtt',
        'ftp_mysql_path' : dict_path['local_ftp_path'] + 'mysql',
        'ftp_edc_path' : dict_path['local_ftp_path'] + 'eDC',
        'ftp_eue_path' : dict_path['local_ftp_path'] + 'eUE',
        'ftp_emon_path' : dict_path['local_ftp_path'] + 'eMon',
        'ftp_api_path' : dict_path['local_ftp_path'] + 'api_service',
        'ftp_fdfs_path' : dict_path['local_ftp_path'] + 'fdfs',
        'ftp_softphone_path' : dict_path['local_ftp_path'] + 'softphone',
        }

def create_ftp_path():
    if not os.path.exists(dict_path['local_ftp_path']):
        os.mkdir(dict_path['local_ftp_path'])
    with open(dict_path['passwd_file'], mode='w', encoding='utf-8') as f:
        f.write(password)
    os.chmod(dict_path['passwd_file'], stat.S_IRUSR|stat.S_IWUSR)
    for path in ftp_path.values():
        if not os.path.exists(path):
            os.mkdir(path)



def del_locate_file():
    for l in dict_path['locate_lists']:
        if os.path.exists(l):
            logging.info('sudo rm %s' % l)
            subprocess.getstatusoutput('sudo rm %s' % l)

def get_dst_list():
    s = paramiko.SSHClient()
    s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    s.connect(hostname=hostname, port=port, username=username, password=password)
    cmd_create = "sudo updatedb -U %s -o %s && sudo locate -d %s --regex '(\.log$|.zip$|.gz$|MQTT)' >%s" % (dict_path['remote_path'], dict_path['dst_db'], dict_path['dst_db'], dict_path['locate_lists'][1])
    cmd_delete = 'sudo rm ' + dict_path['locate_lists'][1]
    stdin, stdout, stderr = s.exec_command(cmd_create)
    status = stdout.channel.recv_exit_status()
    #print("create cmd status:", status)
    error = (stderr.read().decode('utf-8'))
    logging.info("create cmd:%s status: %s", cmd_create, status)
    if(status == 1):
        print("create cmd error:", error)
        logging.error("create cmd error: %s", error)
        return ""

    cmd_get_mqtt_path = "cat `sudo locate -d %s --regex 'TruncMQTT_log_dir'`"%(dict_path['dst_db'])
    stdin, stdout, stderr = s.exec_command(cmd_get_mqtt_path)
    error = (stderr.read().decode('utf-8'))
    mqtt_path = stdout.read().decode('utf-8')
    status = stdout.channel.recv_exit_status()
    if(status == 1):
        logging.error("create cmd error: %s", error)
        return ""
    logging.info("get remote mqtt log_path cmd:%s status: %s", cmd_get_mqtt_path, status)
    #print("get cmd status:", status)
    
    try:
      t = paramiko.Transport((hostname, port))
      t.connect(username=username, password=password)
      sftp = paramiko.SFTPClient.from_transport(t)
      sftp.get(dict_path['locate_lists'][1], dict_path['locate_lists'][1])
      t.close()
    except Exception as e:
      logging.error("paramiko exception:", e)
      print("paramiko exception:", e)
      stdin, stdout, stderr = s.exec_command(cmd_delete)
      status = stdout.channel.recv_exit_status()
      logging.info("delete cmd status: %s", status)
      s.close()
    return mqtt_path

#local dir
def get_src_list():
    cmd = "sudo updatedb -U %s -o %s && sudo locate -d %s --regex 'log' >>%s" % (
            dict_path['local_ftp_path'], dict_path['src_db'], dict_path['src_db'], dict_path['locate_lists'][0])
    subprocess.getstatusoutput(cmd)

def cmp_diff():
    src = open(dict_path['locate_lists'][0], 'r')
    dst = open(dict_path['locate_lists'][1], 'r')
    diff = open(dict_path['locate_lists'][2], 'a')
    x = src.readlines()
    y = dst.readlines()
    src.close()
    dst.close()
    for i in y:
        j = dict_path['remote_path'] + i[13:]
        if j not in x:
            diff.writelines(j)
    diff.close()

def rsync_direct():
    dict_device = {"nuf_edc/": ftp_path['ftp_edc_path'], "nuf_eue/":ftp_path['ftp_eue_path'], "nuf_emon/":ftp_path['ftp_emon_path'],"nuf_api/":ftp_path['ftp_api_path'],"nuf_fdfs/":ftp_path['ftp_fdfs_path'],"nuf_softphone/":ftp_path['ftp_softphone_path']}
    for key,values in dict_device.items():
        cmd = 'sudo rsync -aRvz  root@%s::%s --password-file=%s %s' % (
                hostname, key, dict_path['passwd_file'], values)
        logging.info(cmd)
        subprocess.getstatusoutput(cmd)


def rsync_file(mqtt_path):
    f = open(dict_path['locate_lists'][2], 'r')
    for line in f.readlines():
        cmd = ''
        if 'navita.log' in line:
            cmd = 'sudo rsync -aRvz  root@%s::%s --password-file=%s %s' % (
                    hostname, "nuf_navita/" + line.strip('\n')[-10:], dict_path['passwd_file'], ftp_path['ftp_navita_path'])
        if 'dispatcher.log' in line:
            cmd = 'sudo rsync -aRvz  root@%s::%s --password-file=%s %s' % (
                    hostname, "nuf_navita/" + line.strip('\n')[-14:], dict_path['passwd_file'], ftp_path['ftp_dis_path'])
        if 'eDC' in line:
            cmd = 'sudo rsync -aRvz  root@%s::%s --password-file=%s %s' % (
                    hostname, "nuf_edc/", dict_path['passwd_file'], ftp_path['ftp_edc_path'])
        if 'eUE' in line:
            cmd = 'sudo rsync -aRvz  root@%s::%s --password-file=%s %s' % (
                    hostname, "nuf_eue/", dict_path['passwd_file'], ftp_path['ftp_eue_path'])
        if 'eMon' in line:
            cmd = 'sudo rsync -aRvz  root@%s::%s --password-file=%s %s' % (
                    hostname, "nuf_emon/", dict_path['passwd_file'], ftp_path['ftp_emon_path'])
        if 'apiServer' in line:
            cmd = 'sudo rsync -aRvz  root@%s::%s --password-file=%s %s' % (
                    hostname, "nuf_api/", dict_path['passwd_file'], ftp_path['ftp_api_path'])
    
        if 'TruncMQTT_log_dir' in line:
            cmd = 'sudo rsync -aRvz  root@%s::%s --password-file=%s %s' % (
                    hostname, "nuf_mqtt/" + mqtt_path.strip('\n')[21:] + '/', dict_path['passwd_file'], ftp_path['ftp_mqtt_path'])
        if 'apache2' in line:
            cmd = 'sudo rsync -aRvz  root@%s::%s --password-file=%s %s' % (
                    hostname, "nuf_apache/", dict_path['passwd_file'], ftp_path['ftp_apache_path'])
        if 'fdfs' in line:
            cmd = 'sudo rsync -aRvz  root@%s::%s --password-file=%s %s' % (
                    hostname, "nuf_fdfs/", dict_path['passwd_file'], ftp_path['ftp_fdfs_path'])
        if 'softphone' in line:
            cmd = 'sudo rsync -aRvz  root@%s::%s --password-file=%s %s' % (
                    hostname, "nuf_softphone/", dict_path['passwd_file'], ftp_path['ftp_softphone_path'])
        logging.info(cmd)
        subprocess.getstatusoutput(cmd)
        #todo: navita_stream  ruleengine

    f.close()

def rsync_remote_log():
#if __name__ ==  '__main__':
    print("rsync start: ", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
    start_time = time.time()
    create_ftp_path()
    del_locate_file()
    mqtt_path = get_dst_list()
    get_src_list()
    cmp_diff()
    rsync_file(mqtt_path)
    rsync_direct()
    del_locate_file()
    end_time = time.time()
    print("rsync success: ", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()), end_time - start_time)
    logging.info("rsync success: %s   delay_time: %s", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()), end_time - start_time)
