"""
process_main_stage: 根据具体业务要求，实现该函数
注：如果有需求，可根据具体业务逻辑，对log的匹配结果进行二次整理，然后存入main_stage
general method 根据line_res的时间值生成id，一同存入main_stage,最后返回main_stage
默认各项值以字符串形式存入main_stage，如果需要改变存储属性，需要在存入main_stage时，进行转换

main_stage: [list] 已存在的结果列表，新处理的结果，需要添加进去
line_num_str: 字符串，同一时间可能有多条log信息，这个串就是这些log的编号
line_res:   {dict} 根据用户输入的格式，匹配每行log后生成的结果（字典形式），处理后添加到main_stage中
match_id: 表示line_res是哪条log模式，1：表示第一条，2：表示第二条，...
log_format_list: [[log mode],[log mode]...]这个是用户输入的log模式列表
"""
from random import choice


def process_main_stage(main_stage, line_num_str, line_res, match_id, log_format_list):
    #print("in general process, match_id: " + str(match_id))
    dic_i = {'_id': str(line_res['time_local']) + '-' + line_num_str}
    for key in line_res:
        if line_res[key]:
           dic_i[key] = line_res[key]
    main_stage.insert(0,dic_i)
    return main_stage


## 具体log格式分析
"""
log 格式导入：
list_key = [[keyIsNickname_1, key_1, value_1, split_1],[keyIsNickname_2, key_2, value_2, split_2],[keyIsNickname_3, key_3, value_3, split_3]...]
list_model = [prefix_1,split_pre_1,time_type,split_time,prefix_2,split_pre_2,list_key,sign_end]
log_format_list = [list_model_1,list_model_2,...]
"""
