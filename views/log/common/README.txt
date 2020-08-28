一， log分析介绍

1, 具体操作注意事项：
分析log文件时，直接调用common_log_analyse.py中的函数main(log_name, log_format_list, private_name)

  log_name:        需要解析的log文件名称
  log_format_list：用户输入的log格式列表
  private_name：   对log匹配结果进行私有业务处理的文件。除了后缀，文件名不能带'.'。文件放在目录private下
  
  
2, 此log分析工具支持多种log格式的分析。只要log格式符合以下条件即可：
log信息包含时间戳
#Date Time Format, now only support these formats:
# 1:  yyyy-MM-dd HH:mm:ss.SSS 或 MM-dd HH:mm:ss.SSS
# 2:  yyyy-MM-dd HH:mm:ss 或 MM-dd HH:mm:ss
# 3:  HH:mm:ss.SSS
# 4:  HH:mm:ss


3, log格式列表规定：
"""
#前缀可有可无
#key和value之间用:隔开，如果没有key就没有:,key需符合re规范，不能有特殊符号（只能包含字母数字和下划线）。value不能包含:
#split 是不同key之间的分隔符（如空格，逗号等,可以是字符串),可以同时有多种形式
#当value没有key时候，可能是约定值。这时请用户为value输入呢称代替key。如果是昵称，keyIsNickname为1;如果是key本身，keyIsNickname为0。
#value可以是确定值，也可以是任意值。不能包含:(:是key和value的分割符号)

list_key = [[keyIsNickname_1, key_1, value_1, split_1],[keyIsNickname_2, key_2, value_2, split_2],[keyIsNickname_3, key_3, value_3, split_3]...]
list_model = [prefix_1,split_pre_1,time_type,split_time,prefix_2,split_pre_2,list_key,sign_end]
log_format_list =  [list_model_1,list_model_2,...]

时间戳是必须的，在数据库中对应key为 'time_local'
#根据具体时间模式，来确定time_type。目前支持1,2,3,4:
# 1:  yyyy-MM-dd HH:mm:ss.SSS 或 MM-dd HH:mm:ss.SSS
# 2:  yyyy-MM-dd HH:mm:ss 或 MM-dd HH:mm:ss
# 3:  HH:mm:ss.SSS
# 4:  HH:mm:ss
"""

4, 根据业务要求，可以对log分析结果进行二次整理
请参考通用业务处理文件./private/general.py，通用处理后，数据都是以字符串类型存入数据库的。
需要进行二次整理的，处理文件需要放在./private/目录下，文件名称除了后缀'.py'，文件名中不能带'.'和空格
分析log文件时，调用common_log_analyse.py中的函数main(log_name, log_format_list, private_name)，其中参数private_name就是用户所加的处理文件名称

---------------------------------------------------------------------
二，分析结果查询介绍

在分析log时候，会储存用户输入的log格式列表(log_format_list)中的所有key(相同key只存一次)。查询时，根据这些key进行联合查询

具体操作注意事项：
1)查询结果时，直接调用common_log_show.py中的函数inquire_key_list(log_name)

  log_name:        已经解析的log文件
  
把得到的key列表呈现给用户，然后由用户进行选择组合查询条件  

2)收集用户查询条件，调用common_log_show.py中的函数request_show(log_name, list_filt, and_or)，返回符合条件的列表
log_name: log文件名称
list_filt：查询条件列表[[key,value,op],[key,value,op],[key,value,op]...]
and_or：1代表and，0代表or。这个代表过滤表中每项的关系

注：log通用处理结果都是以字符串形式存入数据库的，而字符和数字比较方式不同，用户要清楚需要比较值的类型。如果值是数字，肯定是log分析时，进行了二次处理的。
  
