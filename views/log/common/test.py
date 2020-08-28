import requests        #导入requests包
    
url = 'https://www.baidu.com/baidu?wd=%E7%8E%8B%E7%9F%B3'
strhtml = requests.get(url)        #Get方式获取网页数据
print(strhtml.text)
