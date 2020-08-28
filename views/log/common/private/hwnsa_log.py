"""
process_main_stage: 根据具体业务要求，实现该函数
注：如果有需求，可根据具体业务逻辑，对log的匹配结果进行二次整理，然后存入main_stage
hwnsa method, 同一个包可能有多条信息，需要根据sfn字段进行合并，并计算每个包的处理时间

main_stage: [list] 已存在的结果列表，新处理的结果，需要添加进去
line_num_str: 字符串，同一时间可能有多条log信息，这个串就是这些log的编号
line_res:   {dict} 根据用户输入的格式，匹配每行log后生成的结果（字典形式），处理后添加到main_stage中
match_id: 表示line_res是哪条log模式，1：表示第一条，2：表示第二条，...
log_format_list: [[log mode],[log mode]...]这个是用户输入的log模式列表
"""
from random import choice

#不同log信息中，如果sfn值相同，合并成一条log记录，并记录相同sfn的信息处理时间
def process_main_stage(main_stage, line_num_str, line_res, match_id, log_format_list):
        if not line_res['sfn']:
            dic_n = {'_id': str(line_res['time_local']) + '-' + line_num_str}
    
            for key in line_res:
               if line_res[key]:
                  dic_n[key] = line_res[key]
            main_stage.insert(0,dic_n)
            return
        
        #list_sfn = sorted(self.main_stage['sfn'], key=lambda x: x['time_local'],reverse=True)[:100]
        cmp_len = 100
        if len(main_stage) < cmp_len:
            cmp_len = len(main_stage)
            
        count_i = 0
        while count_i < cmp_len:
             if main_stage[count_i]['sfn'] == line_res['sfn']:
                main_stage[count_i]['time_process'] += int(line_res['time_local']) - int(main_stage[count_i]['time_local'])
                for key in line_res:
                    if line_res[key]:
                       main_stage[count_i][key]=line_res[key]
                break
             count_i = count_i + 1
      
        if count_i >= cmp_len:
             dic_i = {'_id': str(line_res['time_local']) + '-' + choice(random_char) + choice(random_char) + choice(random_char),
                      'time_process':0}
             for key in line_res:
                 if line_res[key]:
                    dic_i[key] = line_res[key]
             main_stage.insert(0,dic_i)

        return main_stage
        

# 具体log格式分析

"""
目的端cap的hwnsa_log
2018-09-16 10:11:04:hwnsa:rcv event:17,sfn:500
2018-09-16 10:11:04:==hwnsa:tgt cap,sta:5c6c7cff8d6b==
tgt cap:目的端cap
2018-09-16 10:11:04:hwnsa:tgt cap,recv TRF_REQ,negotiate switchType:2,sfn:500
目的端cap收到了TRF_REQ，并且是一个快速切换请求，type为1则是普通切换
2018-09-16 10:11:04:hwnsa:snd drv event:18,sfn:500
2018-09-16 10:11:04:hwnsa:tgt Cap,send TRF_RSP,sta_id:256,sfn:500
回复TRF_RSP给源端cap
2018-09-16 10:11:04:hwnsa:tgt cap,rcv UL_DATA,idx:0,sfn:511
Sta成功入网，收到上行数据，有此条log则表示目的端cap快速切换正常
"""
"""
log 格式导入：
list_key = [[keyIsNickname_1, key_1, value_1, split_1],[keyIsNickname_2, key_2, value_2, split_2],[keyIsNickname_3, key_3, value_3, split_3]...]
list_model = [prefix_1,split_pre_1,time_type,split_time,prefix_2,split_pre_2,list_key,sign_end]
log_format_list = [list_model_1,list_model_2,...]
"""
line_str = '2018-09-16 10:11:04:hwnsa:rcv event:17,sfn:500'
LOG_FORMAT =
line_str = '2018-09-16 10:11:04:==hwnsa:tgt cap,sta:5c6c7cff8d6b=='
LOG_FORMAT =
line_str = '2018-09-16 10:11:04:hwnsa:tgt cap,recv TRF_REQ,negotiate switchType:2,sfn:500'
LOG_FORMAT = ['','',2,':','','',[[0,'hwnsa','any_sign',','],[1,'recv','any_sign',','],[1,'switch','any_sign',','],[0,'sfn','any_sign','']],'']
line_str = '2018-09-16 10:11:04:hwnsa:snd drv event:18,sfn:500'
LOG_FORMAT =
line_str = '2018-09-16 10:11:04:hwnsa:tgt Cap,send TRF_RSP,sta_id:256,sfn:500'
LOG_FORMAT =
line_str = '2018-09-16 10:11:04:hwnsa:tgt cap,rcv UL_DATA,idx:0,sfn:511'
LOG_FORMAT =
