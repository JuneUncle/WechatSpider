# -*- coding: utf-8 -*-
"""
Created on Tue Jul 11 15:06:15 2017
@author: zhangxunan
crawl data from weixin
"""
from selenium import webdriver
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import datetime
import time
import urllib2
import logging
import wechat_spider_database
import ConfigParser


logging.basicConfig(level=logging.INFO)
cp = ConfigParser.SafeConfigParser()
cp.read('wechat_crawl_history.conf')
logger = logging.getLogger(__name__)
conn = wechat_spider_database.mysqlConnection(logger) #调用数据库open
database = cp.get('db', 'table') #数据库表名称
kw = cp.get('keywords', 'kw').decode('utf-8') 

class wechat_spider:
    def __init__(self,kw):
        self.kw = kw  #初始化丢进来的关键词
        #self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:47.0) Gecko/20100101 FirePHP/0refox/47.0 FirePHP/0.7.4.1'} 
        self.timeout = 5
        self.sogou_search_url = "http://weixin.sogou.com/"
        #self.s = requests.Session()
        self.browser = webdriver.Chrome()
    
    def user_login(self):
        self.browser.get(self.sogou_search_url)
        self.browser.find_element_by_id("loginBtn").click()
        
        
        #出现的二维码标识 /x:html/x:body/x:div/x:div/x:div[2]/x:div[1]/x:img
        #WebDriverWait(self.browser,10).until(EC.presence_of_element_located((By.XPATH, "div/div/div[2]/div[1]/img")))
        
        print "请扫描屏幕上方二维码确认登录"
        time.sleep(10) #停留十秒
        # 未登录时候的xpath id('top_login')
        WebDriverWait(self.browser,20).until(EC.presence_of_element_located((By.XPATH, "id('login_yes')/a")))
        # 登录时的xpath id('login_yes')/x:a
        
    def get_search_html_by_kw(self):  
       
        self.browser.find_element_by_id("query").send_keys(self.kw)
        self.browser.find_element_by_class_name("swz").click()
        self.browser.find_element_by_class_name("tool").click()
        self.browser.find_element_by_class_name("all-wy-box").click()
        self.browser.find_element_by_link_text("一周内").click()
        soup = BeautifulSoup(self.browser.page_source, "html.parser")
        return  soup
    
    def get_search_body(self,html):
        
        content = html.find_all("ul", { "class" : "news-list" })
        content_detail = content[0].find_all(['title', 'li'])
        num=len(content_detail) #微信每页记录条目数
        for i in range(num):
            title =  content_detail[i].select('h3')[0].get_text().strip('\n')  #文献的题目并去掉前后的空格和回车
            wechatAccount = content_detail[i].select('a[class="account"]')[0].get_text()
            publishTime = content_detail[i].select('span[class="s2"]')[0].get_text().split('))')[1]
            if (u"小时" in publishTime):
                publishTime = int(publishTime.split(u'小时')[0])
                nowDate = datetime.datetime.now()- datetime.timedelta(hours=publishTime)
            elif(u"分钟" in publishTime):
                publishTime = int(publishTime.split(u'分钟')[0])
                nowDate = datetime.datetime.now()- datetime.timedelta(seconds=publishTime*60)  
            elif(u"天前" in publishTime):
                
                publishTime = int(publishTime.split(u'天前')[0])
                nowDate = datetime.datetime.now()- datetime.timedelta(hours=publishTime*24) 
            else:
                nowDate = datetime.datetime.strptime(publishTime,'%Y-%m-%d')
            print (nowDate)
            
            content_url = content_detail[i].select('h3')[0]
            body_url=""
            for url in content_url.find_all("a"):
                body_url = url.get('href')
            #print (news_url)
            request = urllib2.Request(body_url)
            response = urllib2.urlopen(request)
            body_html=response.read().decode('utf-8')
            news_html=BeautifulSoup(body_html,"lxml")
            #print (news_html)
            #从html中解析出body内容
            bodynum=len(news_html.select('p'))
            bodytxt=""
            for j in range(bodynum):
                bodytxt=bodytxt+news_html.select('p')[j].get_text()
            #print (bodytxt) 删除些没有用的文本
            bodytxt.replace('\n', '')
            if (u'功能介绍' in bodytxt):
                bodytxt = bodytxt.split(u'功能介绍')[1]
            if (bodytxt.find(u'赞赏长按二维码')!=-1):
                bodytxt = bodytxt.split(u'赞赏长按二维码')[0]
            sql ="""INSERT INTO """+ database +"""(keywords,title,source,publishtime,body) VALUES(%s, %s, %s, %s, %s)"""
            sql_content=[self.kw,title,wechatAccount,nowDate,bodytxt]
            re_value = wechat_spider_database.mysqlInsert(conn, sql, sql_content)
            print re_value
    
    def run(self):
        #爬虫入口函数
        # Step 0：模拟登陆账号
        self.user_login()
        
        # Step 1：GET请求到搜狗微信引擎，以微信公众号英文名称作为查询关键字 并返回html
        sougou_search_html = self.get_search_html_by_kw()
        #print sougou_search_html
        
        # Step 2: 获取body内容并写入到数据库中
        strTemp = sougou_search_html.find_all("div", { "class" : "mun" })[0].get_text().encode("utf-8") #判断总共有多少页
        news_number=strTemp.split('找到约')[1].split('条结果')[0].replace(',','')
        news_number=int(news_number)
        if(news_number%10!=0):
            page_number = news_number/10+1 #总的页数            
        else:
            page_number = news_number/10
        for i in range(page_number):
            self.get_search_body(sougou_search_html)
            WebDriverWait(self.browser,10).until(lambda x: x.find_element_by_xpath("id('sogou_next')")).click() #实现翻页功能
            sougou_search_html = BeautifulSoup(self.browser.page_source, "html.parser")


# main  
if __name__ == '__main__':  
    #kw = u"张一山"
    wechat_spider(kw).run()