import ddddocr, requests, time
from urllib import parse
from bs4 import BeautifulSoup as Psoup

"""
    >>> pip install requests
    >>> pip install bs4
    >>> pip install ddddocr
"""

# 必填参数
USERNAME = ""  # 学号
PASSWORD = ""  # 门户密码
NAME = ""  # 课程名
SORT = "必修课"  # 课程分类，必修课（学科基础、专业必修课）、选修课（专业选修课）、通识课、专业内计划课、跨年级、跨专业
PAGE = 1  # 页码，从 1 开始，超出页码会异常
INDEX = -1  # 下标，请根据运行结果给出课程开头的数字

# 可选参数
TEACHER = ""  # 教师名称
DAY_OF_WEEK = ""  # 周几，1..7
SECTION = ""  # 节次，如 1-2，必须与周几搭配使用，不然是空的


class Sort:
    """课程分类"""
    def __init__(self, search_route, pick_route):
        self.search_route = search_route
        self.pick_route = pick_route


sorts = {
    "必修课": Sort("Bx", "bx"),
    "选修课": Sort("Xx", "xx"),
    "通识课": Sort("Ggxxk", "ggxxk"),
    "专业内计划课": Sort("Bxqjh", "bxqjh"),
    "跨年级": Sort("Knj", "knj"),
    "跨专业": Sort("Faw", "faw")
}
sorts_keys = list(sorts.keys())


class User:
    __root = "http://jwxt.gdufe.edu.cn"
    __base = "/jsxsd"
    __captcha = "/verifycode.servlet"
    __login = "/xk/LoginToXkLdap"
    __entry = "/xsxk/xklc_list?Ves632DSdyV=NEW_XSD_PYGL"
    __check_campus = "/xsxkkc/checkXq"
    __check_have_pass = "/xsxkkc/checkXscj"

    @staticmethod
    def __course_pick(course_id, sort):
        """选课路由"""
        return f"/xsxkkc/{sorts[sort].pick_route}xkOper?jx0404id={course_id}&xkzy=&trjf=&cxxdlx=1"

    def __init__(self, name, pwd, max_retry = 20):
        """登录"""
        print(
            "本项目完全免费。我们的 Github 仓库是 https://github.com/Kiteio/easy-course。如果对您有帮助，请花点时间为我们点亮 Star。")
        print("使用本项目代表您同意我们 Github 上的免责声明。")
        print()

        if name == "" or pwd == "":
            raise Exception("请参照文档填写您的账号信息。")

        with requests.Session() as session:
            self.__session = session

        # 获取 Cookie
        self.__session.get(self.__root + self.__base)

        for count in range(0, 5):
            # 获取验证码
            response = self.__session.get(self.__root + self.__base + self.__captcha)
            # 识别验证码
            ocr = ddddocr.DdddOcr(show_ad=False)
            text = ocr.classification(response.content)
            # 发送登录请求
            data = {
                "USERNAME": name,
                "PASSWORD": pwd,
                "RANDOMCODE": text
            }
            response = self.__session.post(self.__root + self.__base + self.__login, data=data)
            # 验证登录结果
            soup = Psoup(response.text, "html.parser")
            if soup.find("title").text == "学生个人中心":
                self.name = name
                self.__enter_system(max_retry)
                return
        raise Exception("超出最大重试次数，登录失败，请检查信息后重试。")

    def __enter_system(self, max_retry=20):
        """进入选课系统"""
        entry = None
        response = self.__session.get(self.__root + self.__base + self.__entry)

        soup = Psoup(response.text, "html.parser")
        tags = soup.find("table", id="tbKxkc").find_all("a")
        for tag in tags:
            if tag.text == "进入选课":
                entry = tag["href"]
                break

        if entry is None:
            if max_retry > 0:
                sleep_time = 2
                print(f"[{self.name}] 无进入选课链接，{sleep_time}s 后重试")
                time.sleep(sleep_time)
                return self.__enter_system(max_retry - 1)
            else:
                raise Exception(f"[{self.name}] 无进入选课链接，超出最大重试次数")

        self.__session.get(self.__root + entry)
        print(f"[{self.name}] 进入选课系统")

    def search(self, name, sort, index, teacher="", day_of_week="", section=""):
        """搜索课程，仅限非专业课"""
        print(self.__root + self.__base + self.__course_search(
            name, sort, teacher, day_of_week, section
        ))
        response = self.__session.post(
            self.__root + self.__base + self.__course_search(
                name, sort, teacher, day_of_week, section
            ),
            data=self.__form(index)
        )
        return self.__parse(response)

    def list(self, sort, index):
        """课程列表，仅限专业课"""
        response = self.__session.post(
            self.__root + self.__base + self.__course_list(sort),
            data=self.__form(index)
        )
        return self.__parse(response)

    @staticmethod
    def __course_list(sort):
        """课程列表路由，只能是专业课（必修/选修）"""
        if sort is not sorts[sorts_keys[0]] and sort is not sorts[sorts_keys[1]]:
            raise Exception(f"SORT 只能为 {sorts_keys[0]}, {sorts_keys[1]}")
        return f"/xsxkkc/xsxk{sort.search_route}xk"

    @staticmethod
    def __course_search(name, sort, teacher, day_of_week, section):
        """课程搜索路由，仅限通识课、专业内计划课、跨年级、跨专业"""
        if sort is sorts[sorts_keys[0]] or sort is sorts[sorts_keys[1]]:
            raise Exception("课程搜索只能为非必修课、非选修课")
        # 节次判空，不为空加上 -
        section = (section if section.endswith("-") else section + "-") if section != "" else section
        # 二次编码
        name = User.__encode(name)
        teacher = User.__encode(teacher)

        route = f"/xsxkkc/xsxk{sort.search_route}xk?kcxx={name}&skls={teacher}&skxq={day_of_week}&skjc={section}&sfym=false&sfct=false"
        # 通识课需要家电其他参数
        if sort is sorts[sorts_keys[3]]:
            route += "&szjylb=&xq=&szkclb="

        return route

    @staticmethod
    def __encode(string):
        """二次编码"""
        return parse.quote(parse.quote(string))

    @staticmethod
    def __form(index=0, count=15):
        """查找课程表单"""
        return {
            "sEcho": index,
            "iColumns": count - 1,
            "sColumns": "",
            "iDisplayStart": count * index,
            "iDisplayLength": count
        }

    @staticmethod
    def __parse(response):
        """解析请求结果"""
        course_list = response.json()["aaData"]
        mlist = []
        for item in course_list:
            mlist.append({
                "课程号": item["kch"],
                "课程名称": item["kcmc"],
                "学分": item["ksfs"],
                "教师": item["skls"],
                "上课时间": item["sksj"],
                "上课地点": item["skdd"],
                "课堂人数": item["xxrs"],
                "选课人数": item["xkrs"],
                "id": item["jx0404id"]
            })
        return mlist

    def pick(self, course_id, sort):
        """选课"""
        response = self.__session.get(self.__root + self.__base + self.__course_pick(course_id, sort))
        data = response.json()

        try:
            try:
                if data["success"]:
                    print(f"[{self.name}] 选课成功")
                else:
                    if data["message"] == "选课失败：此课堂选课人数已满！":
                        print(f"{self.name} 满员")
                        time.sleep(1)
                        return self.pick(course_id, sort)
                    else:
                        print(f"[{self.name}] {data['message']}")
            except KeyError as e:
                print(f"[{self.name}] 账号可能在别处登录，已退出")
        except RecursionError as e:
            # 递归过限
            self.pick(course_id, sort)


if __name__ == "__main__":
    user = User(USERNAME, PASSWORD)
    if SORT == sorts_keys[0] or SORT == sorts_keys[1]:
        courses = user.list(sorts[SORT], PAGE - 1)
    else:
        courses = user.search(NAME, sorts[SORT], PAGE - 1, TEACHER, DAY_OF_WEEK, SECTION)

    print("\n结果:")
    for i, course in enumerate(courses):
        print(f"[{i}] {', '.join([f'{k}: {v}' for k, v in course.items()])}")
    print()

    if INDEX == -1:
        print(f"INDEX = -1，已退出")
    else:
        user.pick(courses[INDEX]["id"], SORT)