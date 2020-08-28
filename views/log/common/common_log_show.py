import logging
import pymongo
from os import stat, path, getcwd
from common_log import mongo_client, LOG_TYPE, convert_time, parse_line_common, get_log_key_list

# ----日志文件名
LOG_NAME = 'test1.log'
LOG_NAME = 'android.log'

def inquire_key_list(log_name):
        """ 获取log文件的关键字list """
        base_name = path.basename(log_name)
        db_name = base_name.replace('.', '_')
        mongo_col = mongo_client[db_name]['registry']
        tmp = mongo_col.find({}, {'key_list': 1})
        try:
            res = tmp.next()
            return res['key_list']
        except StopIteration:
            return  []
        except Exception as err:
            logger.error("get error, will exit: {}".format(repr(err)))
            raise
        finally:
            mongo_client.close()

print(inquire_key_list(LOG_NAME))
print("\n\n")

'''
查询条件设定：（'$and'列表中的条件为并且关系，'$or'列表为或关系）
match = {'$or':[{'$and':[{'time_local':{'$gt':'0210174331.241'}}, {'time_local':{'$lt':'0210174431.241'}}, {'free':{'$lt':'0'}}]}]}
match = {"$or":[{"sfn":{$gt:"1"},"switchType":"2"}， {与别的字典 or，内部字典为 and}]}
find(match)
'''
'''
#list_and 列表中所有项的关系为并且关系。[[key,value,op],[key,value,op],[key,value,op]...]
#op为运算符（大于/小于/等于/不等于）。log通用处理结果都是以字符串形式存入数据库的，而字符和数字比较方式不同，用户要清楚需要比较值的类型
>  :$gt -------- greater than  >
>= :$gte --------- gt equal  >=
<  :$lt -------- less than  <
<= :$lte --------- lt equal  <=
!= :$ne ----------- not equal  !=
=  :$eq  --------  equal  =
'''
def generate_and_match(list_and):
    if not isinstance(list_and,list):
       return
    len_list = len(list_and)
    if len_list == 0:
       return
    dict_and = {'$and':[{}]}
    for i in range(len_list):
        if list_and[i][2] == '>':
            dict_tmp = {}
            dict_value = {}
            dict_value['$gt'] = list_and[i][1]
            dict_tmp[list_and[i][0]] = dict_value
            dict_and['$and'].append(dict_tmp)
        elif list_and[i][2] == '>=':
            dict_tmp = {}
            dict_value = {}
            dict_value['$gte'] = list_and[i][1]
            dict_tmp[list_and[i][0]] = dict_value
            dict_and['$and'].append(dict_tmp)
        elif list_and[i][2] == '<':
            dict_tmp = {}
            dict_value = {}
            dict_value['$lt'] = list_and[i][1]
            dict_tmp[list_and[i][0]] = dict_value
            dict_and['$and'].append(dict_tmp)
        elif list_and[i][2] == '<=':
            dict_tmp = {}
            dict_value = {}
            dict_value['$lte'] = list_and[i][1]
            dict_tmp[list_and[i][0]] = dict_value
            dict_and['$and'].append(dict_tmp)
        elif list_and[i][2] == '!=':
            dict_tmp = {}
            dict_value = {}
            dict_value['$ne'] = list_and[i][1]
            dict_tmp[list_and[i][0]] = dict_value
            dict_and['$and'].append(dict_tmp)
        elif list_and[i][2] == '=':
            dict_tmp = {}
            dict_tmp[list_and[i][0]] = list_and[i][1]
            dict_and['$and'].append(dict_tmp)            
            
    return dict_and

'''
#list_or 列表中所有项的关系为或关系。[[key,value,op],[key,value,op],[key,value,op]...]
#generate_or_match返回值需要检查，{'$or':[]}中列表不能为空
'''
def generate_or_match(list_or):
    if not isinstance(list_or,list):
       return
    len_list = len(list_or)
    if len_list == 0:
       return
    dict_or = {'$or':[]}
    for i in range(len_list):
        if list_or[i][2] == '>':
            dict_tmp = {}
            dict_value = {}
            dict_value['$gt'] = list_or[i][1]
            dict_tmp[list_or[i][0]] = dict_value
            dict_or['$or'].append(dict_tmp)
        elif list_or[i][2] == '>=':
            dict_tmp = {}
            dict_value = {}
            dict_value['$gte'] = list_or[i][1]
            dict_tmp[list_or[i][0]] = dict_value
            dict_or['$or'].append(dict_tmp)
        elif list_or[i][2] == '<':
            dict_tmp = {}
            dict_value = {}
            dict_value['$lt'] = list_or[i][1]
            dict_tmp[list_or[i][0]] = dict_value
            dict_or['$or'].append(dict_tmp)
        elif list_or[i][2] == '<=':
            dict_tmp = {}
            dict_value = {}
            dict_value['$lte'] = list_or[i][1]
            dict_tmp[list_or[i][0]] = dict_value
            dict_or['$or'].append(dict_tmp)
        elif list_or[i][2] == '!=':
            dict_tmp = {}
            dict_value = {}
            dict_value['$ne'] = list_or[i][1]
            dict_tmp[list_or[i][0]] = dict_value
            dict_or['$or'].append(dict_tmp)
        elif list_or[i][2] == '=':
            dict_tmp = {}
            dict_tmp[list_or[i][0]] = list_or[i][1]
            dict_or['$or'].append(dict_tmp)            
            
    if len(dict_or['$or']) == 0:
       dict_or = {}
    return dict_or


            
def get_result_list(log_name, match):
        """ 获取查询list """
        base_name = path.basename(log_name)
        db_name = base_name.replace('.', '_')
        mongo_col = mongo_client[db_name]['main']
        tmp = mongo_col.find(match).sort('_id')
        #print(tmp)
        try:
            #res = tmp.next()
            #print(res)
            return list(tmp)
        except StopIteration:
            return  []
        except Exception as err:
            #logger.error("get error, will exit: {}".format(repr(err)))
            raise
        finally:
            mongo_client.close()


def request_show(log_name, list_filt, and_or):
    match = {}
    if and_or == 1:
       match = generate_and_match(list_filt)
    else:
       match = generate_or_match(list_filt)
    if not match:
       match = {}
    return get_result_list(log_name, match)



match = {'$or':[{'$and':[{},{'time_local':{'$gt':'0210174331.241'}}, {'time_local':{'$lt':'0210174431.241'}}]}]}
match = {}
result = get_result_list(LOG_NAME, match)
rs_len = len(result)
#print(result)
print("the result is: " + str(rs_len))

list_and = [['time_local','0210174331.241','<'],['time_local','0210174431.241','>']]
#match = generate_and_match(list_and)
#print(match)
result = request_show(LOG_NAME, list_and,0)
rs_len = len(result)
#print(result)
print("the result is: " + str(rs_len))
