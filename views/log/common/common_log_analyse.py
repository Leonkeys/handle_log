#!/bin/env python3
# -*- coding:utf-8 -*-
# Collect hwnsa log, process it and insert the result into mongodb.

from datetime import datetime
import time
import re
import importlib
import logging
import fcntl
import json
from socket import gethostname
from multiprocessing import Pool
from random import choice
from os import stat, path, getcwd
from sys import exit, argv as sys_argv
from subprocess import run, PIPE
import glob
import pymongo
import chardet
import threading
import paramiko
import codecs

from .common_log import mongo_client, LOG_TYPE, convert_time, parse_line_common, get_log_key_list 

R = threading.Lock()

# 文档中_id字段中需要的随机字符串
random_char = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'

server = gethostname()  # 主机名

class MyMongo(object):
    def __init__(self, db_name):
        """获得Database(MongoClient）对象
        db_name: mongodb的库名(不同站点对应不同的库名)"""
        self.db_name = db_name
        self.mongodb = mongo_client[db_name]

    def insert_mongo(self, bulk_doc, offset, inode, timestamp, key_list):
        """插入mongodb
        bulk_doc: 由每分钟文档组成的批量插入的数组
        offset: 当前已入库的offset
        inode: 当前处理的文件的inode
        """
        # timestamp = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))
        ##print('db_name:', self.db_name, 'cur_offset:', offset, 'cur_inode:', inode)
        try:
            self.mongodb['main'].insert_many(bulk_doc)  # 插入数据
            self.mongodb['registry'].update({'server': server},
                                            {'$set': {'offset': offset, 'inode': inode, 'timestamp': timestamp, 'key_list': key_list}}, upsert=True)
        except Exception as err:
            logging.error('{} insert data error: {}'.format(self.db_name, repr(err)))
            raise
        finally:
            mongo_client.close()

    def get_prev_info(self):
        """取得本server本日志这一天已入库的offset"""
        ##print('db_name:', self.db_name, 'server:', server)
        tmp = self.mongodb['registry'].find({'server': server}, {'server': 1, 'inode': 1, 'offset': 1, 'key_list': 1})
        try:
            res = tmp.next()
            return res['offset'], res['inode'], res['key_list']
        except StopIteration:
            return 0, 0, []
        except Exception as err:
            logging.error("get offset of {} at {} error, will exit: {}".format(self.db_name, server, repr(err)))
            raise
        finally:
            mongo_client.close()

    # def del_old_data(self, date, h_m):
    #     """删除N天前的数据, 默认为LIMIT
    #     date: 日期, 格式20180315
    #     h_m: 当前hour and minute(到23:59时执行清理操作)"""
    #     if h_m != '2359':
    #         return
    #     min_date = get_delta_date(date, LIMIT)
    #     try:
    #         self.mongodb['main'].remove({'_id': {'$lt': min_date}})
    #         self.mongodb['registry'].remove({'timestamp': {'$lt': min_date}})
    #     except Exception as err:
    #         logging.error("{} delete documents before {} days ago error: {}".format(self.db_name, LIMIT, repr(err)))

    def del_all_data(self):
        try:
            self.mongodb['main'].remove()
            self.mongodb['registry'].remove()
        except Exception as err:
            logging.error("{} delete documents error: {}".format(self.db_name, repr(err)))


class LogBase(object):
    def __init__(self, log_name):
        """根据文件名或者inode获取文件信息"""
        self.log_name = log_name
        fstat = stat(log_name)
        self.cur_size = fstat.st_size
        self.cur_timestamp = fstat.st_mtime
        self.cur_inode = fstat.st_ino


class LogPlainText(LogBase):
    def parse_line(self, line_str, log_format_list):
        """
        处理每一行记录
        line_str: 该行日志的原始形式
        """
        parse,match_id = parse_line_common(line_str, log_format_list)
        if not parse or not parse['time_local']:
            return 0,0
        else:
            parse["time_local"] = convert_time(parse["time_local"])
            return parse,match_id



class Processor(object):
    def __init__(self, mod_type, log_name, log_offset,log_format_list='', private_name='general.py'):
        """log_name: 日志文件名"""
        self.log_name = log_name
        self.log_format_list = log_format_list
        self.private_name = private_name
        self.base_name = path.basename(log_name)
        self.db_name = self.base_name.replace('.', '_')  # mongodb中的库名(将域名中的.替换为_)
        self.mymongo = MyMongo(self.db_name)
        self.processed_num = 0
        # self.main_stage: 处理过程中, 用于保存一分钟内的各项原始数据
        self.main_stage = []
        self.bulk_documents = []  # 作为每分钟文档的容器, 累积BATCH_INSERT个文档时, 进行一次批量插入
        self.this_h_m_s = ''  # 当前处理的一秒钟, 格式: 010101(1时1分1秒)
        self.invalid_log = 0  # 目前解析不了的log
        self.offset_bytes = log_offset
        self.log_type = mod_type

    def _append_line_to_main_stage(self, line_res, match_id):
        work_dynamic_module = ''
        if not self.private_name:
           work_dynamic_module = 'private.general'
        else:
           dy_name = path.basename(self.private_name)
           work_dynamic_module = 'views.log.common.private.'+ dy_name[:-3]
        try:  
           work_dynamic = importlib.import_module(work_dynamic_module)
        except Exception:
           logging.error("Don't find dynamic work file {} {}".format(work_dynamic_module, dy_name))
           return  
        num_str = str(self.processed_num)
        if self.processed_num > 999:
           num_str = str(999) + num_str
        elif self.processed_num > 99:
           num_str = str(99) + num_str
        elif self.processed_num > 9:
           num_str = str(9) + num_str
        num_str = num_str + choice(random_char)
        
        self.main_stage = work_dynamic.process_main_stage(self.main_stage,num_str,line_res, match_id, self.log_format_list)

    def _generate_bulk_docs(self, date):
        self.bulk_documents.extend(self.main_stage)

    def _reset_every_minute(self):
        self.processed_num = self.invalid_log = 0
        self.main_stage = []

    def go_process(self):
        """开始处理日志文件"""
        if LOG_TYPE == 'plaintext':
            logobj = LogPlainText(self.log_name)
        else:
            logging.error("wrong LOG_TYPE, must 'plaintext' ")
            return
              
        #print('db_name:',self.db_name, 'find:', self.mymongo.mongodb[self.mymongo.mongodb.list_collection_names(session=None)[0]].find_one({"inode" : 1051674}))
        if self.offset_bytes is not None and isinstance(self.offset_bytes, int):
            last_offset = self.offset_bytes
        else:
            last_offset = 0
        # 打开文件,找到相应的offset进行处理
        #with open(self.log_name, 'rb') as f:
        #    file_encode = chardet.detect(f.read())['encoding']
        #print("file_encode:", file_encode)
        mqtt_line = ''
        with codecs.open(self.log_name) as fobj:
            logging.debug("open:{}".format(self.log_name))
            fobj.seek(last_offset)
            parsed_offset = last_offset
            for line_str in fobj:
                #logging.debug("line: {}".format(line_str))
                if self.log_type == 'mqtt':
                    if len(line_str.split()) > 2 and  line_str.split()[2] == '[debug]':
                        continue
                    if line_str.strip().replace(' ', '') == '...':
                        continue
                    if line_str.strip().split(',')[-1].split('>>'):
                        continue
                    mqtt_line = line_str.split(',')
                    if ''.join(mqtt_line).strip().isdecimal() or line_str.replace(' ', '') == '\n':
                        continue
                if last_offset >= logobj.cur_size:
                    return
                parsed_offset += len(line_str.encode('utf8')) #不转换的话，汉字被当成一个字符
                line_res,match_id = logobj.parse_line(line_str, self.log_format_list)
                if not line_res or not line_res['time_local']:
                    self.invalid_log += 1
                    continue
                date, hour, minute, second = line_res['time_local']
                if date == '0':
                    line_res['time_local'] = str(hour + minute + second)
                else:
                    line_res['time_local'] = str(date + hour + minute + second)
                    # 分钟粒度交替时: 通一分钟内的log计数，为后续查询显示顺序做准备
                if self.this_h_m_s != hour + minute + second:
                    self.processed_num = 0
                self.processed_num += 1
                self.this_h_m_s = hour + minute + second
                self._append_line_to_main_stage(line_res,match_id)  # 对每一行的解析结果进行处理
        last_key_list=''

        # 最后可能会存在一部分已解析但未达到分钟交替的行, 需要额外逻辑进行入库
        if self.processed_num > 0:
            self._generate_bulk_docs(date)
        if self.bulk_documents and self.this_h_m_s:            
            log_key_list = get_log_key_list(self.log_format_list, last_key_list)
            try:
                self.mymongo.insert_mongo(self.bulk_documents, parsed_offset, logobj.cur_inode, date + self.this_h_m_s, log_key_list)
                logging.debug("Log file parsedoffset: {}".format(parsed_offset))
            except Exception as e:
                logging.error("mongo insert err: {}".format(e))
                return

    def db_key_list(self):
        try:
            # 对于一个日志文件名, 上一次处理到的offset和inode
            last_offset, last_inode, last_key_list = self.mymongo.get_prev_info()
            return last_key_list
        except Exception:
            return []
    
    def db_delete(self):
        self.mymongo.del_all_data()


LOG_PATH = '/home/user/mywork2019/alarm/git/log_handle/views/log/common/log/navita-docker.log'
LOG_PATH = '/home/user/mywork2019/alarm/git/log_handle/views/log/common/log/3050_log_3'
LOG_PATH = '/home/user/mywork2019/alarm/git/log_handle/views/log/common/log/3500-emon.log'
LOG_PATH = ''

#NAVITA_START = ['any_sign',' ',1,' ','any_sign','1104',[[1,'switch_channel','any_sign','']],'sofia']
#NAVITA_NORMAL_SINGLE_OVER_1 = ['any_sign',' ',5,':','','',[[1,'Dialplan','any_sign','Action'], [1,'fs_over','dispatcher_check','']],'']
#NAVITA_SINGLE_CALL_TYPE = ['any_sign',' ',5,':','','',[[1,'Dialplan','any_sign','export'], [1,'call_type','any_sign','']],'\n']
#NAVITA_SINGLE_CALLER = ['any_sign',' ',1,' ','any_sign','Processing',[[1,'caller','any_sign','']],'in']
NAVITA_END = []

EUE_START = ['','',6,' ','any_sign','MESSAGE ',[[1,'call_type','any_sign',' '], [0, 'id','any_sign',','], [0,'from','any_sign',','],[0,'to','any_sign',' '],[1,'eue_s_flag','started','']],'']
EUE_END = ['','',6,' ','any_sign','MESSAGE ',[[1,'call_type','any_sign',' '], [0, 'id','any_sign',','], [0,'from','any_sign',','],[0,'to','any_sign',' '], [1,'eue_end_flag','end','']],'']
EUE_PER_AND_DELAY= ['','',6,' ','any_sign','STAT:',[[1,'per_and_delay','any_sign',' ='],[1,'value','any_sign','']],'\n']


EMON_START = ['','',6,' ','any_sign','MESSAGE s',[[1,'emon_s_flag','any_sign',','],[0,'type','any_sign',','],[0,'from','any_sign',','],[0,'to','any_sign',','],[1,'noting','any_sign',':'],[1,'callid','any_sign',' '],[1,'dir','any_sign','']],'\n']

EMON_END = ['','',6,' ','any_sign','MESSAGE ',[[1,'emon_e_flag','any_sign',','],[0,'type','any_sign',','],[0,'from','any_sign',','],[0,'to','any_sign',','],[1,'nothing','any_sign',':'], [1,'callid','any_sign','']],'\n']

#2020-09-17 15:53:15:342 [libsip] MESSAGE Total Confirmed Percent = 93.333336
EMON_PER = ['','',6,' ','any_sign','MESSAGE ',[[1,'emon_per','any_sign','Percent ='], [1,'emon_per_value','any_sign','']],'\n']
#2020-09-16 17:38:33:097 [libsip] MESSAGE Outgoing Set-up Time 195
#2020-09-27 14:59:26:321 [libsip] MESSAGE Incoming Set-up Time 28
EMON_OUT_DELAY = ['','',6,' ','any_sign','Outgoing Set-up Time',[[1,'out_setup_time','any_sign','']],'\n']
EMON_IN_DELAY = ['','',6,' ','any_sign','Incoming Set-up Time',[[1,'in_setup_time','any_sign','']],'\n']

ERROR_AUTH_1 = ['any_sign',' ',7, ' ','any_sign',' ',[[3,'"need auth"','any_sign','']],'\n']
ERROR_AUTH_2 = ['any_sign',' ',7, ' ','any_sign',' ',[[3,'"auth failed"','any_sign','']],'\n']
ERROR_AUTH_3 = ['any_sign',' ',7, ' ','any_sign',' ',[[3,'"require pass"','any_sign','']],'\n']
ERROR_AUTH_4 = ['any_sign',' ',7, ' ','any_sign',' ',[[3,'auth','any_sign','']],'\n']
ERROR_REF_5 = ['any_sign',' ',7, ' ','any_sign',' ',[[3,'refuse','any_sign','']],'\n']
ERROR_REF_6 = ['any_sign',' ',7, ' ','any_sign',' ',[[3,'reject','any_sign','']],'\n']
ERROR_FAT_7 = ['any_sign',' ',7, ' ','any_sign',' ',[[3,'fault','any_sign','']],'\n']
ERROR_WR_8 = ['any_sign',' ',7, ' ','any_sign',' ',[[3,'wrong','any_sign','']],'\n']
ERROR_INV_9 = ['any_sign',' ',7, ' ','any_sign',' ',[[3,'invalid','any_sign','']],'\n']
ERROR_ERR_10 = ['any_sign',' ',7, ' ','any_sign',' ',[[3,'err','any_sign','']],'\n']
ERROR_ERR_11 = ['','',1, ' ','','\[',[[3,'err','any_sign','']],'\n']
ERROR_ERR_12 = ['any_sign',' ',7, ' ','any_sign',' ',[[3,'error','any_sign','']],'\n']
ERROR_TT_13 = ['any_sign',' ',7, ' ','any_sign',' ',[[3,'timeout','any_sign','']],'\n']
ERROR_FAL_14 = ['any_sign',' ',7, ' ','any_sign',' ',[[3,'fail','any_sign','']],'\n']
ERROR_CRIT_15 = ['any_sign',' ',7, ' ','any_sign',' ',[[3,'crit','any_sign','']],'\n']
ERROR_ALERT_16 = ['any_sign',' ',7, ' ','any_sign',' ',[[3,'alert','any_sign','']],'\n']

LOG_FORMAT_LIST = [EUE_START, EUE_END, EUE_PER_AND_DELAY, EMON_START,EMON_END,EMON_PER,EMON_OUT_DELAY,EMON_IN_DELAY,ERROR_AUTH_1, ERROR_AUTH_2,ERROR_AUTH_3,ERROR_AUTH_4,ERROR_REF_5,ERROR_REF_6,ERROR_FAT_7,ERROR_WR_8,ERROR_INV_9,ERROR_ERR_10,ERROR_ERR_11,ERROR_ERR_12,ERROR_TT_13,ERROR_FAL_14, ERROR_CRIT_15,ERROR_ALERT_16]


ERROR_VALUE = dict()
err_keys = ['needauth','authfailed','requirepass','auth','refuse','reject','fault','wrong','invalid','err','error','timeout','fail','crit','alert']


"""
log_name:        需要解析的log文件
log_format_list：用户输入的log格式列表
offset_bytes:    日志文件的读取位置
private_name：   对log匹配结果进行私有业务处理的文件。除了后缀，文件名不能带'.'
"""
#mod_type:[caller,callee,nav,dis,api,mqtt]
def analyse_main(mod_type,uuid=None, log_name=LOG_PATH, offset_bytes=None, log_format_list=LOG_FORMAT_LIST, private_name='general.py'):
    logging.debug("enter analyse main, mod:{} uuid:{}".format(mod_type, uuid))
    analyse_result = {'log_valid':None,'state':None,'err_msg':None,'delay_time':None,'analyse_prog_err':None}
    R.acquire()
    if log_name == '' or mod_type == '':
        analyse_result["analyse_prog_err"] = "file name or module name none."
        logging.error("analyse prog err:{}".format(analyse_result['analyse_prog_err']))
        return analyse_result
    start_t = time.time()
    processor = Processor(mod_type, log_name, offset_bytes, log_format_list, private_name)
    processor.go_process()

    global ERROR_VALUE
    if ERROR_VALUE:
        ERROR_VALUE.clear()
    ERROR_VALUE = {key:[] for key in err_keys}
    
    log_callid = caller = callee = call_t = None
    in_delay = out_delay = income_percent = outgo_percent = total_percent = ''
    from_s = to_s = from_sip = to_sip = ''
    db_client = processor.mymongo.mongodb['main']
    cursor = db_client.find()
    li = list(cursor)
    eue_flag = 0
    emon_flag = 0
    num_err = 0
    #logging.debug("regular exp match result: {}".format(li))

    for i in li:
        if 'emon_s_flag' in i.keys() or  ('emon_e_flag'in i.keys() and i['emon_e_flag'] == 'end'):
            log_callid = i['callid'][1:len(i['callid'])-1]
            if (emon_flag < 2) and log_callid == uuid:
                emon_flag = emon_flag + 1
            else:
                continue

        if 'eue_s_flag' in i.keys() or 'eue_end_flag' in i.keys():
            log_callid = i['id'][1:len(i['id'])-1]
            if (eue_flag < 2) and (log_callid == uuid):
                eue_flag = eue_flag + 1
            else:
                continue

        if 'out_setup_time' in i.keys():
            if out_delay == '':
                out_delay = i['out_setup_time']
            else:
                continue
        if 'in_setup_time' in i.keys():
            if in_delay == '':
                in_delay = i['in_setup_time']
            else:
                continue

        if 'emon_per' in i.keys():
            if income_percent and outgo_percent and total_percent:
                continue
            else:
                if i['emon_per'] == 'Incoming Confirmed ':
                    income_percent = i['emon_per_value']
                if i['emon_per'] == 'Invite Confirmed ':
                    outgo_percent = i['emon_per_value']
                if i['emon_per'] == 'Total Confirmed ':
                    total_percent = i['emon_per_value']
        if 'per_and_delay' in i.keys():
            if in_delay and out_delay and income_percent and outgo_percent and total_percent:
                continue
            else:
                if i['per_and_delay'] == 'Incoming Set-up Time(Avg)':
                    in_delay = i['value']
                if i['per_and_delay'] == 'Invite Set-up Time(Avg)':
                    out_delay = i['value']
                if i['per_and_delay'] == 'Incoming Confirmed Percent':
                    income_percent = i['value'] + '%'
                if i['per_and_delay'] == 'Invite Confirmed Percent':
                    outgo_percent = i['value'] + '%'
                if i['per_and_delay'] == 'Total Confirmed Percent':
                    total_percent = i['value'] + '%'
        for errkey in err_keys:
            if errkey in i.keys():
                ERROR_VALUE[errkey].append(i[errkey])
            else:
                continue

    #logging.debug("ERROR_VALUE: {}".format(ERROR_VALUE))
    end_t = time.time()
    remote_docker_stat()

    for k in ERROR_VALUE:
        if ERROR_VALUE[k] == []:
            num_err += 1
    #logging.debug("null error_list count :{}".format(num_err))

    if mod_type == 'caller' or mod_type == 'callee':
        logging.debug("percent :income:{},out:{},total:{},outdelay:{},indelay:{}".format(income_percent, outgo_percent, total_percent, out_delay, in_delay))
        if emon_flag == 2 or eue_flag == 2:
            analyse_result['log_valid'] = '1'
            if num_err == len(ERROR_VALUE):
                analyse_result['state'] = '1' #succ
            else:
                analyse_result['state'] = '2' #fail
            if mod_type == 'caller':
                analyse_result['delay_time'] = out_delay
            else:
                analyse_result['delay_time'] = in_delay
        else:
            analyse_result['log_valid'] = '2'
            analyse_result['state'] = '2' #fail
        analyse_result['err_msg'] = ERROR_VALUE
    elif mod_type == 'nav' or mod_type == 'dis': #todo nav dis api mqtt
        analyse_result['log_valid'] = '1'
        if num_err == len(ERROR_VALUE) and docker_srv_name[0] not in docker_err.keys() and docker_srv_name[1] not in docker_err.keys() and docker_srv_name[5] not in docker_err.keys() and docker_srv_name[6] not in docker_err.keys():
            analyse_result['state'] = '1' #succ
        else:
            analyse_result['state'] = '2' #fail
        docker_err.pop(docker_srv_name[2]) if docker_srv_name[2] in docker_err.keys() else ''
        docker_err.pop(docker_srv_name[3]) if docker_srv_name[3] in docker_err.keys() else ''
        docker_err.pop(docker_srv_name[4]) if docker_srv_name[4] in docker_err.keys() else ''
        docker_err.pop(docker_srv_name[7]) if docker_srv_name[7] in docker_err.keys() else ''
        analyse_result['err_msg'] = dict(ERROR_VALUE, **docker_err)
    elif mod_type == 'api':
        analyse_result['log_valid'] = '1'
        if num_err == len(ERROR_VALUE) and docker_srv_name[3] not in docker_err.keys() and docker_srv_name[4] not in docker_err.keys() and docker_srv_name[7] not in docker_err.keys():
            analyse_result['state'] = '1'
        else:
            analyse_result['state'] = '2'
        docker_err.pop(docker_srv_name[0]) if docker_srv_name[0] in docker_err.keys() else ''
        docker_err.pop(docker_srv_name[1]) if docker_srv_name[1] in docker_err.keys() else ''
        docker_err.pop(docker_srv_name[2]) if docker_srv_name[2] in docker_err.keys() else ''
        docker_err.pop(docker_srv_name[5]) if docker_srv_name[5] in docker_err.keys() else ''
        docker_err.pop(docker_srv_name[6]) if docker_srv_name[6] in docker_err.keys() else ''
        analyse_result['err_msg'] = dict(ERROR_VALUE, **docker_err)

    elif mod_type == 'mqtt':
        analyse_result['log_valid'] = '1'
        if num_err == len(ERROR_VALUE) and docker_srv_name[2] not in docker_err.keys():
            analyse_result['state'] = '1'
        else:
            analyse_result['state'] = '2'
        docker_err.pop(docker_srv_name[0]) if docker_srv_name[0] in docker_err.keys() else ''
        docker_err.pop(docker_srv_name[1]) if docker_srv_name[1] in docker_err.keys() else ''
        docker_err.pop(docker_srv_name[3]) if docker_srv_name[3] in docker_err.keys() else ''
        docker_err.pop(docker_srv_name[4]) if docker_srv_name[4] in docker_err.keys() else ''
        docker_err.pop(docker_srv_name[5]) if docker_srv_name[5] in docker_err.keys() else ''
        docker_err.pop(docker_srv_name[6]) if docker_srv_name[6] in docker_err.keys() else ''
        docker_err.pop(docker_srv_name[7]) if docker_srv_name[7] in docker_err.keys() else ''
        analyse_result['err_msg'] = dict(ERROR_VALUE, **docker_err)
    else:
        logging.error("mode type error!")


    R.release()
    logging.debug("exit analyse main, current mod:{}".format(mod_type))
    #logging.debug("analyse main, return: {}".format(analyse_result))
    return analyse_result


def time_to_ms(ori_time):
    stime = ori_time.split(".")
    s_time = stime[0][0:4] + '-' + stime[0][4:6] + '-' + stime[0][6:8] + ' ' + stime[0][8:10] + ':' + stime[0][10:12] + ':' + stime[0][12:14] + '.' + stime[1] 
    time_obj_s = datetime.strptime(s_time, "%Y-%m-%d %H:%M:%S.%f")
    #print("s_time", s_time, time_obj_s.microsecond)
    #stime_s unit: milliseconds 
    stime_s = int(time.mktime(time_obj_s.timetuple()) * 1000.0 + time_obj_s.microsecond / 1000.0)
    #print("stime_s", stime_s, "ori time", ori_time)
    return stime_s


docker_srv_name =  ['navita', 'navita_stream', 'TruncMQTT', 'EUHTRUNCK', 'url_map', 'storage-group1', 'tracker', 'mysql']
docker_err = dict()

hostname = '192.168.22.90'
username = 'root'
password = 'nuard@@'
port = 22
docker_err = dict()

def remote_docker_stat():
    logging.debug("enter remote_docker_stat func()")
    err_ret = ret = None
    s = paramiko.SSHClient()
    s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    s.connect(hostname=hostname, port=port, username=username, password=password)
    cmd_get_docker_name = "sudo docker ps | awk '{print $NF}'"
    stdin,stdout,stderr = s.exec_command(cmd_get_docker_name)
    err_ret = stderr.read().decode('utf-8')
    status = stdout.channel.recv_exit_status()
    if(status == 1):
        logging.error("cmd awk return nothing, cmd error is :{}".format(err_ret))
    else:
        ret = stdout.read().decode('utf-8')
        li = ret.strip('\nNAMES').split('\n')
    logging.debug("cmd_get_docker_name result:{}".format(li))
    for i in li:
        cmd_get_docker_err = 'sudo docker logs  --tail 1000 %s 2>&1 | grep \' error \'' % i
        stdin,stdout,stderr = s.exec_command(cmd_get_docker_err)
        err_ret = stderr.read().decode('utf-8')
        status = stdout.channel.recv_exit_status()
        if(status == 1):
            logging.error("cmd grep return nothing, cmd error is: {}".format(err_ret))
        else:
            ret = stdout.read().decode('utf-8')
            logging.debug("cmd_get_docker_err  result:{}".format(ret))
            docker_err[i] = ret
    logging.debug("exit remote_docker_stat func()")



# def inquire_key_list(log_name):
#     processor = Processor(log_name)
#     return processor.db_key_list()
#
# def db_delete(log_name):
#     processor = Processor(log_name)
#     processor.db_delete()
#
#
# def todo_log():
#     """通过配置文件取得要处理的日志文件"""
#     all_find = glob.glob(LOG_PATH)
#     return [one for one in all_find if path.basename(one) not in EXCLUDE]


#if __name__ == "__main__":
#    db_delete(LOG_PATH)
#    if len(sys_argv) > 1 and sys_argv[1] == '-r':
#        db_delete(LOG_PATH)
#    else:
#        analyse_main('caller', 'CpER0ExQDF',LOG_PATH, LOG_FORMAT_LIST, "general.py")
#        li = inquire_key_list(LOG_PATH)
#        print(li)
