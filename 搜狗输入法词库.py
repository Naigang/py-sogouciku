import requests
import os
import struct
import binascii
from queue import Queue
from threading import Thread
from lxml import etree

curdir = os.path.dirname(os.path.abspath(__file__))
os.chdir(curdir)

# 批量提取某分类下的 词库文件链接地址
class ExtraLink(Thread):
    def __init__(self, list_q, url_q):
        super().__init__()
        self.list_q = list_q
        self.url_q = url_q
        self.headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh-TW;q=0.9,zh;q=0.8",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
            "Cookie": "SUID=C90A58DA3220910A000000005DCC326A; SUV=1573663339296953; pgv_pvi=2035922944; usid=Iu695fswUjywa-1s; wuid=AAHgddlqLAAAAAqHM3Q0LAAAkwA=; front_screen_resolution=1920*1080; FREQUENCY=1579276796197_3; sw_uuid=9516767232; ssuid=1338371992; IPLOC=CN5101; sct=61; SNUID=D7319A3A0703A0028803CC5207937A34; ld=sZllllllll2WKteAlllllVEUE$6lllll5B1czZllllwllllllylll5@@@@@@@@@@; PHPSESSID=rav4u14r5tmhnu4lj39lcqi667; SMYUV=1591013268290426; UM_distinctid=1726fc7dcb51c4-0ae002dae1a34-f7d1d38-1fa400-1726fc7dcb625c; CNZZDATA1253526839=1408869244-1591009181-https%253A%252F%252Fwww.baidu.com%252F%7C1591013942",
            "Host": "pinyin.sogou.com",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.61 Safari/537.36"
        }
    
    def run(self):
        while True:
            try:
                link_url = self.list_q.get()
                source = self.download(link_url)
                if not source:
                    continue
                self.extra_link(source)
            finally:
                self.list_q.task_done()

    def download(self, url):
        try:
            req = requests.get(url, headers=self.headers, timeout=15)
        except requests.RequestException as e:
            print("列表页抓取错误: ", e)
            html = None
        else:
            req.encoding = "utf8"
            html = req.text
        return html

    # 解析html页面
    def extra_link(self, html):
        if not html:
            return False
        doc = etree.HTML(html)
        main = doc.xpath('//div[@id="dict_detail_list"]//div[@class="dict_dl_btn"]')
        for item in main:
            link = ''.join(item.xpath('./a/attribute::href'))
            self.url_q.put(link)

# 下载词库链接并转换为txt文件
class SogouCiku(Thread):
    def __init__(self, url_q):
        super().__init__()
        self.startPy = 0x1540  # 拼音表偏移
        self.startChinese = 0x2628  # 汉语词组表偏移
        # self.GPy_Table = {}  # 全局拼音表
        self.GTable = []  # 解析结果 关键词列表
        self.url_q = url_q

    def run(self):
        while True:
            try:
                url = self.url_q.get()

                s = self.download(url)
                if not s:
                    continue
                res, fn, tn = self.scel2txt(s)
                r = self.save(res, fn, tn)
                if r:
                    self.GTable = []
            finally:
                self.url_q.task_done()

    def download(self, url):
        try:
            req = requests.get(url)
        except requests.RequestException as e:
            print(e)
            source = None
        else:
            source = req.content
        return source

    # 原始字节码转为字符串
    def byte2str(self, data):
        pos = 0
        str = ''
        while pos < len(data):
            c = chr(struct.unpack('H', bytes([data[pos], data[pos + 1]]))[0])
            if c != chr(0):
                str += c
            pos += 2
        return str

    # 读取中文表
    def getChinese(self, data, f_name, t_name):
        pos = 0
        while pos < len(data):
            # 同音词数量
            same = struct.unpack('H', bytes([data[pos], data[pos + 1]]))[0]

            # 拼音索引表长度
            pos += 2
            py_table_len = struct.unpack(
                'H', bytes([data[pos], data[pos + 1]]))[0]

            # 拼音索引表
            pos += 2

            # 中文词组
            pos += py_table_len
            for i in range(same):
                # 中文词组长度
                c_len = struct.unpack('H', bytes(
                    [data[pos], data[pos + 1]]))[0]
                # 中文词组
                pos += 2
                word = self.byte2str(data[pos: pos + c_len])
                # 扩展数据长度
                pos += c_len
                ext_len = struct.unpack('H', bytes([data[pos], data[pos + 1]]))[0]
                # 词频
                pos += 2
                # 保存
                self.GTable.append(word)
                # 到下个词的偏移位置
                pos += ext_len
        return (self.GTable, f_name, t_name)

    def scel2txt(self, txt):
        # 分隔符
        print('-' * 80)
        if txt:
            data = txt
        else:
            print("没用内容 直接返回")
            return
        file_name = self.byte2str(data[0x338:0x540])
        text_name = self.byte2str(data[0x130:0x338])
        text_name = text_name.replace("/", "")
        text_name = text_name.replace("_", "")
        print("词库名：", file_name)  # .encode('GB18030')
        print("词库类型：", text_name )
        # print("描述信息：", self.byte2str(data[0x540:0xd40]))
        # print("词库示例：", self.byte2str(data[0xd40:self.startPy]))
        result = self.getChinese(data[self.startChinese:], file_name, text_name)
        return result

    @staticmethod
    def save(result, fn, tn):
        if not result:
            return False
        folder_path = os.path.join(curdir, fn)
        if not os.path.exists(folder_path):
            os.mkdir(folder_path)
        try:
            f = open(f'{folder_path}/{tn}.txt', 'w', encoding="utf-8")
            for word in result:
                f.write(word + '\n')
        except OSError:
            pass
        f.close()
        return True


if __name__ == '__main__':
    url_q = Queue()
    list_q = Queue()

    url = ["https://pinyin.sogou.com/dict/cate/index/{}/default/{}".format(x,y) for x in [436] for y in range(1,143)]
    
    for u in url:
        list_q.put(u)
    
    for i in range(10):
        EL = ExtraLink(list_q, url_q)
        EL.daemon = True
        EL.start()

    for i in range(10):
        SC = SogouCiku(url_q)
        SC.daemon = True
        SC.start()

    list_q.join()
    url_q.join()

    print("执行完毕....")
