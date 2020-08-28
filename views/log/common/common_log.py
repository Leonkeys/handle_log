import re
import pymongo
import datetime

"""
#前缀可有可无
#key和value之间用:隔开，如果没有key就没有:,key需符合re规范，不能有特殊符号（只能包含字母数字和下划线）。value不能包含:
#split 是不同key之间的分隔符（如空格，逗号等,可以是字符串),可以同时有多种形式
#当value没有key时候，可能是约定值。这时请用户为value输入呢称代替key
#value可以是确定值，也可以是任意值。不能包含:(:是key和value的分割符号)

list_key = [[keyIsNickname_1, key_1, value_1, split_1],[keyIsNickname_2, key_2, value_2, split_2],[keyIsNickname_3, key_3, value_3, split_3]...]
list_model = [prefix_1,split_pre_1,time_type,split_time,prefix_2,split_pre_2,list_key,sign_end]
log_format_list =  [list_model_1,list_model_2,...]

#Date Time Format, now only support these formats:
# 1:  yyyy-MM-dd HH:mm:ss.SSS 或 MM-dd HH:mm:ss.SSS
# 2:  yyyy-MM-dd HH:mm:ss 或 MM-dd HH:mm:ss
# 3:  HH:mm:ss.SSS
# 4:  HH:mm:ss
"""
"""
android log:
2017-11-05 09:48:34.768 I/audio_hw_primary( 1405): out_set_parameters(): kvpairs = routing=0
LOG_FORMAT = ['','',1,' ','','',[[1,'module','any_sign',':'],[0,'out_set_parameters()','any_sign','']],'']

hwnsa log:
2018-09-16 10:11:04:hwnsa:tgt cap,recv TRF_REQ,negotiate switchType:2,sfn:500
LOG_FORMAT = ['','',2,':','','',[[0,'hwnsa','any_sign',','],[1,'recv','any_sign',','],[1,'switch','any_sign',','],[0,'sfn','any_sign','']],'']
"""

#list_log_format = ['','',1,' ','','',[[1,'module','any_sign',':'],[0,'out_set_parameters()','any_sign','']],'']

LOG_TYPE = 'plaintext'
MONGO_HOST = "localhost"
MONGO_PORT = 27017
mongo_client = pymongo.MongoClient(MONGO_HOST, MONGO_PORT, connect=False)

any_sign = 'any_sign'

def convert_time(t_value):
    """将2018-09-16 10:10:56格式的时间转换为20180916101056格式"""
    if ' ' in t_value:
       _time_local = t_value.split()
       _date = _time_local[0].split('-')
       _time = _time_local[1].split(':')
       return ''.join(_date), _time[0], _time[1], _time[2]
    else: #"""将10:10:56格式的时间转换为101056格式"""
       _time = t_value.split(':')
       return '0', _time[0], _time[1], _time[2]

def get_regular(list_log_format):
  if not isinstance(list_log_format,list):
     return
  regular = ''
  if len(list_log_format) != 8:
     return regular
     
  prefix_1 = list_log_format[0]      #前缀 1
  split_pre_1 = list_log_format[1]
  time_type = list_log_format[2]     #时间格式
  split_time = list_log_format[3]
  prefix_2 = list_log_format[4]      #前缀 2
  split_pre_2 = list_log_format[5]
  list_key = list_log_format[6]      #关键信息列表
  sign_end = list_log_format[7]      #结尾符号
   
  
  if prefix_1 == any_sign:
    #print("prefix_1 is any \n")
    regular += '(?P<prefix_1>.*)\s*'+split_pre_1
  elif prefix_1:
    #print("prefix_1 is "+prefix_1+'\n')
    regular += '(?P<prefix_1>'+prefix_1+')\s*'+split_pre_1
  else:
    #print("prefix_1 is null \n")
    regular += ''

  if time_type == 1:
    #print("time is 1 \n")
    regular += '\s*(?P<time_local>[^ ]+\s+\d+:\d+:\d+.\d+)\s*'+split_time
  elif time_type == 2:
    #print("time is 2 \n")
    regular += '\s*(?P<time_local>[^ ]+\s+\d+:\d+:\d+)\s*'+split_time
  elif time_type == 3:
    #print("time is 3 \n")
    regular += '\s*(?P<time_local>\d+:\d+:\d+.\d+)\s*'+split_time
  elif time_type == 4:
    #print("time is 4 \n")
    regular += '\s*(?P<time_local>\d+:\d+:\d+)\s*'+split_time
  elif time_type == 5:
    regular += '\s*(?P<time_local>\w{8})\s*'+split_time
  else:
    #print("time is missing..." + regular)
    regular = ''
    return regular

  if prefix_2 == any_sign:
    regular += '\s*'+'(?P<prefix_2>.*)\s*'+split_pre_2
  elif prefix_2:
    regular += '\s*'+'(?P<prefix_2>'+prefix_2+')\s*'+split_pre_2 
  
  #return regular
  #list_key=[loading...]
  len_key = len(list_key)
  if not len_key:
	  return regular
  list_key[len_key-1][3] = sign_end
  for i in range(len_key):
    if list_key[i][0]:
        if list_key[i][2] == any_sign:
           regular += '\s*'+'(?P<'+list_key[i][1]+'>[^:]*)\s*'+list_key[i][3]
        else:
           regular += '\s*'+'(?P<'+list_key[i][1]+'>'+list_key[i][2]+')\s*'+list_key[i][3]
    else:
        if list_key[i][2] == any_sign:
           regular += '\s*'+list_key[i][1]+'\s*'+':'+'\s*'+'(?P<'+list_key[i][1]+'>.*)\s*'+list_key[i][3]
        else:
            regular += '\s*'+list_key[i][1]+'\s*'+':'+'\s*'+'(?P<'+list_key[i][1]+'>'+list_key[i][2]+')\s*'+list_key[i][3]

  return regular


def get_log_pattern_list(log_format_list):
  log_pattern_list = []
  for i in range(len(log_format_list)):
     log_pattern_list.append(get_regular(log_format_list[i]))
  return log_pattern_list


def parse_line_common(line_str, log_format_list):
   if not isinstance(log_format_list,list):
      return
   parse = ''
   log_pattern_list = get_log_pattern_list(log_format_list)
   #print(log_pattern_list)
   #print("\n")
   for i in range(len(log_pattern_list)):
      log_pattern_obj = re.compile(log_pattern_list[i])
      parse = log_pattern_obj.match(line_str)
      if not parse or not log_pattern_list[i]:
         #print("fail match this time " + str(i)+ "\n")
         continue
      else:
         #print("success to match "+ str(i) +"\n")
         #print(pase)
         #print(pase.group())
         #print(parse.group(1))
         #print("time_local", parse["time_local"], parse.groupdict())
         x=parse.groupdict()
         if x["time_local"] == 'Dialplan':
             x["time_local"] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
         print(parse.groups())
         return x,i+1
   return 0,0
   
def parse_line_test(line_str, log_format_list):
        """
        处理每一行记录
        line_str: 该行日志的原始形式
        """
        parse,match_id = parse_line_common(line_str, log_format_list)
        if parse and parse['time_local']:
          tmp_time = parse["time_local"]
          if tmp_time:
             parse["time_local"] = convert_time(tmp_time)
        return parse,match_id


def get_key(list_log_format, log_key_list=[]):
	
  if len(list_log_format) != 8:
     return log_key_list
     
  prefix_1 = list_log_format[0]      #前缀 1
  split_pre_1 = list_log_format[1]
  time_type = list_log_format[2]     #时间格式
  split_time = list_log_format[3]
  prefix_2 = list_log_format[4]      #前缀 2
  split_pre_2 = list_log_format[5]
  list_key = list_log_format[6]      #关键信息列表
  sign_end = list_log_format[7]      #结尾符号
   
  
  if prefix_1:
     if "prefix_1" not in log_key_list:
        log_key_list.append("prefix_1")


  if time_type in [1, 2, 3, 4]:
     if "time_local" not in log_key_list:
        log_key_list.append("time_local")
  else:
    #print("time is missing...\n")
    return log_key_list

  if prefix_2:
     if "prefix_2" not in log_key_list:
        log_key_list.append("prefix_2") 
  
  #list_key=[loading...]
  len_key = len(list_key)
  if not len_key:
	  return log_key_list
  list_key[len_key-1][3] = sign_end
  for i in range(len_key):
     if list_key[i][1] not in log_key_list:
        log_key_list.append(list_key[i][1])

  return log_key_list


def get_log_key_list(log_format_list, log_key_list=[]):
  if not log_key_list:
     log_key_list = []
  for i in range(len(log_format_list)):
     log_key_list = get_key(log_format_list[i], log_key_list)
  return log_key_list
  
    
"""        
line_str = '11-05 09:48:34.768 I/audio_hw_primary( 1405): out_set_parameters: kvpairs = routing=0'
LOG_FORMAT_1 = ['','',1,' ','','',[[1,'module','any_sign',':'],[0,'out_set_parameters','any_sign','']],'']
line_str = '2018-09-16 10:11:04:hwnsa:tgt cap,recv TRF_REQ,negotiate switchType:2,sfn:500'
LOG_FORMAT_2 = ['','',5,':','','',[[0,'hwnsa','any_sign',','],[1,'recv','any_sign',',negotiate'],[0,'switchType','any_sign',','],[0,'sfn','any_sign','']],'']
line_str = '02-10 18:28:43.011 D/dalvikvm( 2529): GC_CONCURRENT freed 1924K, 37% free 5802K/9152K, paused 4ms+7ms, total 57ms'
LOG_FORMAT_3 = ['','',1,' ','any_sign',':',[[1,'free','any_sign',','],[1,'free_1','any_sign',','],[1,'paused','any_sign',','],[1,'tatal','any_sign','']],'']

LOG_FORMAT_LIST = [LOG_FORMAT_1,LOG_FORMAT_2,LOG_FORMAT_3]
pase = parse_line_test(line_str, LOG_FORMAT_LIST)
if pase:
	print(pase)
	print("success parse\n")
else:
	print("fail parse\n")
"""
