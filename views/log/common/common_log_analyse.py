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

from .common_log import mongo_client, LOG_TYPE, convert_time, parse_line_common, get_log_key_list 



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
            print("get prev info", type(tmp))
            return res['offset'], res['inode'], res['key_list']
        except StopIteration:
            print("stop iter")
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
    def __init__(self, log_name, log_format_list='', private_name='general.py'):
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
           print("err, don't find dynamic work file\n", work_dynamic_module, dy_name)
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
            print("wrong LOG_TYPE, must 'plaintext' \n")
            return
              
        #print('db_name:',self.db_name, 'find:', self.mymongo.mongodb[self.mymongo.mongodb.list_collection_names(session=None)[0]].find_one({"inode" : 1051674}))

        last_offset = 0
        # 打开文件,找到相应的offset进行处理
        #with open(self.log_name, 'r', encoding='iso8859-1') as f:
        with open(self.log_name, 'rb') as f:
            file_encode = chardet.detect(f.read())['encoding']
            print(chardet.detect(f.read())['encoding'])
        fobj = open(self.log_name, encoding = file_encode)
        print("open:", self.log_name)
        fobj.seek(last_offset)
        parsed_offset = last_offset
        for line_str in fobj:
            #print("line:", line_str)
            if last_offset >= logobj.cur_size:
                fobj.close()
                return
            parsed_offset += len(line_str.encode('utf8')) #不转换的话，汉字被当成一个字符
            line_res,match_id = logobj.parse_line(line_str, self.log_format_list)            
            if not line_res or not line_res['time_local']:
                self.invalid_log += 1
                #print("invalid_log",  self.invalid_log)
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

        fobj.close()
        last_key_list=''

        # 最后可能会存在一部分已解析但未达到分钟交替的行, 需要额外逻辑进行入库
        if self.processed_num > 0:
            self._generate_bulk_docs(date)
        if self.bulk_documents and self.this_h_m_s:            
            log_key_list = get_log_key_list(self.log_format_list, last_key_list)
            try:
                self.mymongo.insert_mongo(self.bulk_documents, parsed_offset, logobj.cur_inode, date + self.this_h_m_s, log_key_list)
                print("parsedoffset:", parsed_offset)
            except Exception as e:
                print("mongo insert err!", e)
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


LOG_PATH = '/home/user/mywork2019/alarm/log_analyse_zj/common/log/part_log_test_1.log'
LOG_PATH = '/home/user/mywork2019/alarm/git/log_handle/views/log/common/log/fs_normal_audio_s.log'
LOG_PATH = '/home/user/mywork2019/alarm/git/log_handle/views/log/common/log/eUE.log'
LOG_PATH = '/home/user/mywork2019/alarm/git/log_handle/views/log/common/log/eMon.log'
LOG_PATH = '/home/user/mywork2019/alarm/git/log_handle/views/log/common/log/navita-docker.log'

#NAVITA_START = ['any_sign',' ',1,' ','any_sign','1104',[[1,'switch_channel','any_sign','']],'sofia']
#NAVITA_NORMAL_SINGLE_OVER_1 = ['any_sign',' ',5,':','','',[[1,'Dialplan','any_sign','Action'], [1,'fs_over','dispatcher_check','']],'']
#NAVITA_SINGLE_CALL_TYPE = ['any_sign',' ',5,':','','',[[1,'Dialplan','any_sign','export'], [1,'call_type','any_sign','']],'\n']
#NAVITA_SINGLE_CALLER = ['any_sign',' ',1,' ','any_sign','Processing',[[1,'caller','any_sign','']],'in']
NAVITA_END = []

EUE_START = ['','',6,' ','any_sign','MESSAGE ',[[1,'call_type','any_sign',' '], [0, 'id','any_sign',','], [0,'from','any_sign',','],[0,'to','any_sign',' '],[1,'eue_s_flag','started','']],'']
EUE_END = ['','',6,' ','any_sign','MESSAGE ',[[1,'call_type','any_sign',' '], [0, 'id','any_sign',','], [0,'from','any_sign',','],[0,'to','any_sign',' '], [1,'eue_end_flag','end','']],'']
EUE_PER_AND_DELAY= ['','',6,' ','any_sign','STAT:',[[1,'per_and_delay','any_sign',' ='],[1,'value','any_sign','']],'\n']


EMON_START = ['','',6,' ','any_sign','MESSAGE s',[[1,'emon_s_flag','any_sign',','],[0,'type','any_sign',','],[0,'from','any_sign',','],[0,'to','any_sign',' '],[1,'dir','any_sign','']],'\n']

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

LOG_FORMAT_LIST = [EUE_START, EUE_END, EUE_PER_AND_DELAY, EMON_START,EMON_END,EMON_PER,EMON_OUT_DELAY,EMON_IN_DELAY,ERROR_AUTH_1, ERROR_AUTH_2,ERROR_AUTH_3,ERROR_AUTH_4,ERROR_REF_5,ERROR_REF_6,ERROR_FAT_7,ERROR_WR_8,ERROR_INV_9,ERROR_ERR_10,ERROR_ERR_11,ERROR_ERR_12,ERROR_TT_13,ERROR_FAL_14]


ERROR_VALUE = dict()
err_keys = ['needauth','authfailed','requirepass','auth','refuse','reject','fault','wrong','invalid','err','error','timeout','fail']

def analyse_main(analyse_result,log_name=LOG_PATH, log_format_list=LOG_FORMAT_LIST, private_name='general.py'):
    print("enter analyse main()")
    if log_name is None  or analyse_result is None:
        analyse_result["analyse_error"] = "file name or key args none."
        #print(analyse_result["error"])
        return analyse_result
    processor = Processor(log_name,log_format_list, private_name)
    processor.go_process()

    global ERROR_VALUE
    if ERROR_VALUE:
        ERROR_VALUE.clear()
    ERROR_VALUE = {key:[] for key in err_keys}
    
    log_callid = caller = callee = call_t = None
    in_delay = out_delay = income_percent = outgo_percent = total_percent = ''
    db_client = processor.mymongo.mongodb['main']
    cursor = db_client.find()
    li = list(cursor)
    ex_flag = 0
    print("list:-------",li)
    if analyse_result['caller']['call_id'] is not None: 
        caller_uuid = analyse_result['caller']['call_id']
    if analyse_result['callee']['call_id'] is not None:
        callee_uuid = analyse_result['callee']['call_id']
    for i in li:
        if 'emon_e_flag' in i.keys() or  'emon_s_flag' in i.keys():
            ex_flag = ex_flag + 1
            caller = i['from'][1:len(i['from'])-1]
            callee = i['to'][1:len(i['to'])-1]
            call_t = i['type'][1:len(i['type'])-1]
            log_callid = i['callid'][1:len(i['callid'])-1]
            print("emon:",  ex_flag, caller, callee, call_t, log_callid)
        if 'eue_s_flag' in i.keys() or 'eue_e_flag' in i.keys():
            ex_flag = ex_flag + 1
            caller = i['from'][1:len(i['from'])-1]
            callee = i['to'][1:len(i['to'])-1]
            call_t = i['call_type']
            log_callid = i['id'][1:len(i['id'])-1]
            print("eue:",  ex_flag, caller, callee, call_t, log_callid)

        if 'out_setup_time' in i.keys():
            out_delay = i['setup_time']
            print("emon out delay:", emon_delay)
        if 'in_setup_time' in i.keys():
            in_delay = i['setup_time']
            print("emon in delay:", emon_delay)

        if 'emon_per' in i.keys():
            if i['emon_per'] == 'Incoming Confirmed ':
                income_percent = i['emon_per_value']
            if i['emon_per'] == 'Invite Confirmed ':
                outgo_percent = i['emon_per_value']
            if i['emon_per'] == 'Total Confirmed ':
                total_percent = i['emon_per_value']
        if 'per_and_delay' in i.keys():
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
        if caller and  callee and call_t:
            return 0

    #print("ERROR_VALUE: ", ERROR_VALUE)
    print("per :", income_percent, outgo_percent, total_percent, out_delay, in_delay)
    if log_callid == caller_uuid  and emon_flag == 2:
         analyse_result[caller]['call_type'][0] = call_t
         analyse_result[caller]['call_type'][1] = caller
         analyse_result[caller]['call_type'][2] = callee
         analyse_result[caller]['err_msg'] = ERROR_VALUE
         analyse_result[caller]['delay_time'] = out_delay
         return 0

    if log_callid == callee_uuid  and emon_flag == 2:
         analyse_result[callee]['call_type'][0] = call_t
         analyse_result[callee]['call_type'][1] = caller
         analyse_result[callee]['call_type'][2] = callee
         analyse_result[callee]['err_msg'] = ERROR_VALUE
         analyse_result[callee]['delay_time'] = in_delay
         return 0
    return 0
  

#FLAG_DICT = { "navita":{"log_valid":"1","call_type":"[type,caller,calleder]", "state":"0", "err_msg":"None","build_id":"<audiogroup*1111*>","delay_time":""}, "dis":{ "log_valid":"1", "dis_start":"no"}}

def time_to_ms(ori_time):
    stime = ori_time.split(".")
    s_time = stime[0][0:4] + '-' + stime[0][4:6] + '-' + stime[0][6:8] + ' ' + stime[0][8:10] + ':' + stime[0][10:12] + ':' + stime[0][12:14] + '.' + stime[1] 
    time_obj_s = datetime.strptime(s_time, "%Y-%m-%d %H:%M:%S.%f")
    #print("s_time", s_time, time_obj_s.microsecond)
    #stime_s unit: milliseconds 
    stime_s = int(time.mktime(time_obj_s.timetuple()) * 1000.0 + time_obj_s.microsecond / 1000.0)
    #print("stime_s", stime_s, "ori time", ori_time)
    return stime_s


"""
log_name:        需要解析的log文件
log_format_list：用户输入的log格式列表
private_name：   对log匹配结果进行私有业务处理的文件。除了后缀，文件名不能带'.'
"""
def analyse_main_1(analyse_result,log_name=LOG_PATH, log_format_list=LOG_FORMAT_LIST, private_name='general.py'):
    print("enter analyse main()")
    if log_name is None  or analyse_result is None:
        analyse_result["analyse_error"] = "file name or key args none."
        #print(analyse_result["error"])
        return analyse_result
    
    processor = Processor(log_name,log_format_list, private_name)
    processor.go_process()
    ret_dict = processor.mymongo.mongodb['main'].find_one({"switch_channel":"New Channel "})
    fs_start_time = ret_dict["time_local"]
    if ret_dict is not None:
        li=list(processor.mymongo.mongodb['main'].find())
        for i_dict  in  li:
            #print(i_dict)
            if "call_type" in i_dict.keys():
                analyse_result["navita"]["call_type"][0] = "singlecall"

            if "caller" in i_dict.keys():
                caller = i_dict["caller"]
                analyse_result["navita"]["call_type"][1] = caller[6:10]
                analyse_result["navita"]["call_type"][2] = caller[13:17]
                fs_over_time = i_dict["time_local"]
            if "fs_over" in i_dict.keys():
                analyse_result["navita"]["state"] = "1"
        fs_delay = time_to_ms(fs_over_time) - time_to_ms(fs_start_time)
        analyse_result["navita"]["delay_time"] = str(fs_delay)

    else:
        analyse_result["navita"]["log_valid"] = "0" 
        return

    #print(analyse_result)
    #log_key = processor.db_key_list()
    #print(log_key)
    #return analyse_result


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


# ----日志相关
#LOG_PATH = '/home/jun/test/log_analy/code/geany_python_test/test1.log'
#LOG_PATH = '/home/ftpuser/ftp/dis/dispatcher.log'
#LOG_PATH = '/home/user/mywork2019/alarm/log_analyse_zj/common/log/part_log_test_1.log'
#LOG_PATH = '/home/ftpuser/ftp/navita/testcgl.log'

# 要排除的站点
#EXCLUDE = ['log1.txt', 'log.txt']
#line_str1 = '11-05 09:48:34.768 I/audio_hw_primary( 1405): out_set_parameters: kvpairs = routing=0'
#LOG_FORMAT_1 = ['','',1,' ','','',[[1,'module','any_sign',':'],[0,'out_set_parameters','any_sign','']],'']
#line_str = '2018-09-16 10:11:04:hwnsa:tgt cap,recv TRF_REQ,negotiate switchType:2,sfn:500'
#LOG_FORMAT_2 = ['','',2,':','','',[[0,'hwnsa','any_sign',','],[1,'recv','any_sign',',negotiate'],[0,'switchType','any_sign',','],[0,'sfn','any_sign','']],'']
#02-10 18:28:43.011 D/dalvikvm( 2529): GC_CONCURRENT freed 1924K, 37% free 5802K/9152K, paused 4ms+7ms, total 57ms
#LOG_FORMAT_3 = ['','',1,' ','any_sign',':',[[1,'free','any_sign',','],[1,'free_1','any_sign',','],[1,'paused','any_sign',','],[1,'tatal','any_sign','']],'']
#LOG_FORMAT_LIST = [LOG_FORMAT_3]


#if __name__ == "__main__":
#    db_delete(LOG_PATH)
#    if len(sys_argv) > 1 and sys_argv[1] == '-r':
#        db_delete(LOG_PATH)
#    else:
#        analyse_main(LOG_PATH, LOG_FORMAT_LIST, "general.py")
#        li = inquire_key_list(LOG_PATH)
#        print(li)
