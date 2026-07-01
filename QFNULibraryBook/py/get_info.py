import base64  # Base64 编解码模块，用于加密数据的编码
import logging  # 日志记录模块
import sys  # 系统接口模块，用于程序退出等
import time  # 时间相关模块，用于 sleep 等
import json
import os
from datetime import datetime  # 日期时间类
from datetime import timedelta  # 日期时间差类（用于加减天数）



import requests  # HTTP 请求库
from Crypto.Cipher import AES  # AES 加密算法
from Crypto.Util.Padding import pad, unpad  # 数据填充/去填充工具

# ==================== 日志配置 ====================
# 设置日志级别为 INFO，所有 INFO 及以上级别的日志都会输出到控制台
logging.basicConfig(level=logging.INFO)
# 创建一个名为 "开始打印日志" 的日志记录器
logger = logging.getLogger("开始打印日志")

# ==================== 教室名称与 ID 映射 ====================
# 将人类可读的教室名称映射到图书馆系统内部的数字 ID
# 这个映射是固定的，每个自习室对应一个唯一的 build_id
classroom_id_mapping = {
    "西校区图书馆-三层自习室": 38,  # 西校区图书馆 3 楼
    "西校区图书馆-四层自习室": 39,  # 西校区图书馆 4 楼
    "西校区图书馆-五层自习室": 40,  # 西校区图书馆 5 楼
    "西校区东辅楼-二层自习室": 41,  # 西校区东辅楼 2 楼
    "西校区东辅楼-三层自习室": 42,  # 西校区东辅楼 3 楼
    "东校区图书馆-三层电子阅览室": 21,  # 东校区图书馆 3 楼电子阅览室
    "东校区图书馆-三层自习室01": 22,  # 东校区图书馆 3 楼自习室 01
    "东校区图书馆-三层自习室02": 23,  # 东校区图书馆 3 楼自习室 02
    "东校区图书馆-四层中文现刊室": 24,  # 东校区图书馆 4 楼中文现刊室
    "综合楼-801自习室": 16,  # 综合楼 801 自习室
    "综合楼-803自习室": 17,  # 综合楼 803 自习室
    "综合楼-804自习室": 18,  # 综合楼 804 自习室
    "综合楼-805自习室": 19,  # 综合楼 805 自习室
    "综合楼-806自习室": 20,  # 综合楼 806 自习室
    "行政楼-四层东区自习室": 13,  # 行政楼 4 楼东区
    "行政楼-四层中区自习室": 14,  # 行政楼 4 楼中区
    "行政楼-四层西区自习室": 15,  # 行政楼 4 楼西区
    "电视台楼-二层自习室": 12,  # 电视台楼 2 楼
    "日照校区-一楼-南侧自习室":26,
    "日照校区-一楼-大厅":25,
    "日照校区-三楼-第一书库北门厅":30,
    "日照校区-三楼-长廊":29,
    "日照校区-二楼-南大厅":27,
    "日照校区-二楼-自习室":28,
    "日照校区-五楼-办公门厅":34,
    "日照校区-五楼-北区":35,
    "日照校区-五楼-长廊":33,
    "日照校区-四楼-第二书库北门厅":32,
    "日照校区-四楼-长廊":31,
}

# ==================== API 接口地址常量 ====================
# 图书馆预约系统的三个核心接口
URL_CLASSROOM_DETAIL_INFO = "http://libyy.qfnu.edu.cn/api/Seat/date"  # 获取教室详细信息（时间段等）
URL_CLASSROOM_SEAT = "http://libyy.qfnu.edu.cn/api/Seat/seat"  # 获取座位列表
URL_CHECK_STATUS = "http://libyy.qfnu.edu.cn/api/Member/seat"  # 查询个人预约状态

MAX_RETRIES = 100  # HTTP 请求最大重试次数
RETRY_DELAY = 3  # 每次重试之间的等待时间（秒）

#用户座位号(列表)映射到系统座位号(列表)
def find_seat_id_by_name(build_id, user_seat_ids):
    """
    根据座位编号列表（从 1 开始）从 JSON 文件中查找对应的系统座位 ID

    Args:
        json_file_path (str): JSON 文件的完整路径
        user_seat_ids (list): 座位编号列表，从 1 开始，如 [1, 2, 3]
                              对应 name 字段 "001", "002", "003"

    Returns:
        list: 对应的系统座位 ID 列表
    """

    # 构建反向字典：ID -> 名称
    id_to_name = {v: k for k, v in classroom_id_mapping.items()}
    #获取路径
    current_path = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_path))
    # 构造 JSON 文件路径
    json_file_path = os.path.join(project_root, "QFNULibraryBook", "json", "seat_info", f"{id_to_name[build_id]}.json")
    # 检查文件是否存在
    if not os.path.exists(json_file_path):
        raise FileNotFoundError(f"JSON 文件不存在: {json_file_path}")

    # 读取 JSON 文件
    with open(json_file_path, "r", encoding="utf-8") as f:
        data = json.load(f).get("data", [])

    if not data:
        raise ValueError(f"JSON 文件中没有 data 字段或 data 为空: {json_file_path}")

    # 遍历用户输入的座位编号列表
    seat_ids = []
    for seat_num in user_seat_ids:
        # 将编号格式化为三位字符串，如 1 -> "001", 12 -> "012"
        seat_name = f"{seat_num:03d}"

        # 在 JSON 数据中查找 name 字段匹配的条目
        found = False
        for item in data:
            if item.get("name") == seat_name:
                seat_id = item.get("id")
                if seat_id is not None:
                    seat_ids.append(seat_id)
                    found = True
                    break

        # 如果未找到匹配的座位，记录警告
        if not found:
            print(f"⚠️ 警告: 未找到座位 {seat_name} 的映射")

    # 如果没有任何座位匹配到，抛出异常
    if not seat_ids:
        raise ValueError(f"未在 {json_file_path} 中找到任何匹配的座位: {user_seat_ids}")

    return seat_ids

# ==================== 日期获取函数 ====================
def get_date(date):
    """
    根据传入的参数获取目标预约日期

    Args:
        date (str): "today" 表示当天，"tomorrow" 表示明天

    Returns:
        str: 格式化后的日期字符串，如 "2024-06-22"

    流程：
    1. 判断参数是当天还是明天
    2. 如果是明天，在当前日期上加 1 天
    3. 将日期对象格式化为 YYYY-MM-DD 字符串
    """
    try:
        # 根据参数判断目标日期
        if date == "today":
            # 当天：直接取今天的日期
            nowday = datetime.now().date()
        elif date == "tomorrow":
            # 明天：在今天的日期上加 1 天
            nowday = datetime.now().date() + timedelta(days=1)
        else:
            # 参数不合法，记录错误并退出
            logger.error(f"未知的参数: {date}")
            sys.exit()

        # 将日期对象转换为 "YYYY-MM-DD" 格式的字符串
        if nowday:
            return nowday.strftime("%Y-%m-%d")
        else:
            logger.error("日期获取失败")
            sys.exit()

    except Exception as e:
        # 捕获任何异常并记录
        logger.error(f"获取日期异常: {str(e)}")
        sys.exit()


# ==================== HTTP POST 请求封装 ====================
def send_post_request_and_save_response(url, data, headers):
    """
    发送 POST 请求并返回 JSON 响应数据

    带有自动重试机制，最多重试 MAX_RETRIES 次，每次间隔 RETRY_DELAY 秒

    Args:
        url (str): 请求的目标 URL
        data (dict): 要发送的 JSON 数据体
        headers (dict): HTTP 请求头

    Returns:
        dict: 服务器返回的 JSON 响应数据

    Raises:
        超过最大重试次数后调用 sys.exit() 退出程序
    """
    retries = 0  # 重试计数器，初始为 0

    # 循环重试，直到成功或达到最大次数
    while retries < MAX_RETRIES:
        try:
            # 发送 POST 请求，自动将 data 序列化为 JSON
            # timeout=120 表示请求最长等待 120 秒
            response = requests.post(url, json=data, headers=headers, timeout=120)
            # 如果状态码 >= 400，抛出 HTTPError 异常（触发 except）
            response.raise_for_status()
            # 解析并返回 JSON 响应体
            response_data = response.json()
            return response_data

        except requests.exceptions.Timeout:
            # 请求超时，记录日志、增加重试计数、等待后重试
            logger.error("请求超时，正在重试...")
            retries += 1
            time.sleep(RETRY_DELAY)

        except Exception as e:
            # 其他异常（如连接错误、DNS解析失败等）
            logger.error(f"request请求异常: {str(e)}")
            retries += 1
            time.sleep(RETRY_DELAY)

    # 超过最大重试次数仍未成功
    logger.error("超过最大重试次数,请求失败。")
    sys.exit()  # 退出程序


# ==================== 教室 ID 查询 ====================
def get_build_id(classname):
    """
    根据教室名称获取对应的楼栋 ID

    Args:
        classname (str): 教室名称，如 "西校区图书馆-三层自习室"

    Returns:
        int: 教室在系统中的唯一 ID，如 38

    流程：
    1. 在 classroom_id_mapping 字典中查找名称对应的 ID
    2. 如果名称不存在，返回 None
    """
    logger.info(f"教室名称: {classname}")
    # 从映射字典中获取对应的 build_id
    build_id = classroom_id_mapping.get(classname)
    return build_id


# ==================== 时间段获取 ====================
def get_segment(build_id, nowday):
    """
    获取指定教室在指定日期的时间段 ID

    图书馆的座位按时间段划分（如上午、下午、晚上），
    每个时间段有一个唯一的 segment ID

    Args:
        build_id (int): 教室的楼栋 ID
        nowday (str): 日期字符串，如 "2024-06-22"

    Returns:
        str: 时间段的 ID

    流程：
    1. 向服务器请求教室的详细信息
    2. 在返回的数据中找到目标日期的条目
    3. 提取该日期的第一个时间段的 ID
    """
    try:
        # 构造请求数据：只传 build_id
        post_data = {"build_id": build_id}

        # 构造 HTTP 请求头
        request_headers = {
            "Content-Type": "application/json",  # 数据格式为 JSON
            "Connection": "keep-alive",  # 保持长连接
            "Accept": "application/json, text/plain, */*",  # 接受的响应类型
            "lang": "zh",  # 语言：中文
            "X-Requested-With": "XMLHttpRequest",  # AJAX 请求标记
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
            "Origin": "http://libyy.qfnu.edu.cn",  # 来源页面
            "Referer": "http://libyy.qfnu.edu.cn/h5/index.html",  # 引用页面
            "Accept-Encoding": "gzip, deflate",  # 支持的压缩方式
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,pl;q=0.5",  # 语言优先级
        }

        # 发送 POST 请求获取教室详细信息
        res = send_post_request_and_save_response(
            URL_CLASSROOM_DETAIL_INFO, post_data, request_headers
        )

        segment = None
        # 遍历返回的日期数据，找到目标日期的条目
        for item in res["data"]:
            if item["day"] == nowday:
                # 提取该日期的第一个时间段的 ID
                segment = item["times"][0]["id"]
                break

        return segment

    except Exception as e:
        logger.error(f"获取segment时出错: {str(e)}")
        sys.exit()


# ==================== 加密密钥生成 ====================
def get_key():
    """
    根据当前日期动态生成 AES 加密密钥

    密钥生成规则：
    1. 取当前日期（YYYYMMDD 格式），如 "20240622"
    2. 将其反转得到回文，如 "22604202"
    3. 将日期和回文拼接： "2024062222604202"

    这种动态密钥机制确保每天的加密密钥都不同，
    增加了逆向工程的难度

    Returns:
        str: 生成的加密密钥
    """
    # 获取当前日期，格式化为 "YYYYMMDD"，如 "20240622"
    current_date = datetime.now().strftime("%Y%m%d")

    # 将日期字符串反转，得到回文，如 "22604202"
    palindrome = current_date[::-1]

    # 拼接日期和回文作为密钥
    key = current_date + palindrome

    return key


# ==================== AES 加密函数 ====================
def encrypt(text):
    """
    使用 AES-CBC 模式对文本进行加密

    加密流程：
    1. 动态生成当日密钥（见 get_key()）
    2. 使用固定的 IV（初始化向量）
    3. 对明文进行 PKCS7 填充
    4. AES-CBC 加密
    5. Base64 编码输出

    Args:
        text (str): 要加密的原始文本

    Returns:
        str: Base64 编码后的加密字符串
    """
    # 获取当日的动态密钥
    key = get_key()
    # 固定的初始化向量（IV），所有加密都使用同一个 IV
    iv = "ZZWBKJ_ZHIHUAWEI"

    # 将密钥和 IV 转换为字节格式（AES 要求输入为 bytes）
    key_bytes = key.encode("utf-8")
    iv_bytes = iv.encode("utf-8")

    # 创建 AES 加密器
    # MODE_CBC: Cipher Block Chaining 模式，安全性高于 ECB
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)

    # 对明文进行加密：
    # 1. text.encode("utf-8") 将字符串转为字节
    # 2. pad(...) 进行 PKCS7 填充，确保数据长度是块大小的整数倍
    # 3. cipher.encrypt(...) 执行加密
    ciphertext_bytes = cipher.encrypt(pad(text.encode("utf-8"), AES.block_size))

    # 将加密后的字节数据转为 Base64 字符串，便于在网络中传输
    return base64.b64encode(ciphertext_bytes).decode("utf-8")


# ==================== AES 解密函数 ====================
def decrypt(ciphertext):
    """
    对加密字符串进行解密（与 encrypt 函数对应）

    解密流程：
    1. Base64 解码
    2. AES-CBC 解密
    3. 去除 PKCS7 填充
    4. 转回原始字符串

    Args:
        ciphertext (str): Base64 编码的加密字符串

    Returns:
        str: 解密后的原始文本
    """
    # 获取当日的动态密钥（与加密时一致）
    key = get_key()
    # 固定的初始化向量（与加密时一致）
    iv = "ZZWBKJ_ZHIHUAWEI"

    # 将密钥和 IV 转换为字节格式
    key_bytes = key.encode("utf-8")
    iv_bytes = iv.encode("utf-8")

    # 将 Base64 字符串解码回原始字节
    ciphertext_bytes = base64.b64decode(ciphertext)

    # 创建 AES 解密器
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)

    # 执行解密
    decrypted_bytes = cipher.decrypt(ciphertext_bytes)

    # 去除 PKCS7 填充，并转回字符串
    decrypted_text = unpad(decrypted_bytes, AES.block_size).decode("utf-8")

    return decrypted_text


# ==================== 个人座位查询 ====================
def get_member_seat(auth):
    """
    查询用户当前的座位预约状态

    用于判断是否已经有预约成功的座位，避免重复抢座

    Args:
        auth (str): 认证令牌，格式为 "bearer xxx"

    Returns:
        dict: 服务器返回的座位信息数据
        None: 如果请求失败或 Token 失效
    """
    try:
        # 构造请求数据
        post_data = {
            "page": 1,  # 页码
            "limit": 3,  # 每页条数
            "authorization": auth  # 认证令牌
        }

        # 构造 HTTP 请求头
        request_headers = {
            "Content-Type": "application/json",
            "Connection": "keep-alive",
            "Accept": "application/json, text/plain, */*",
            "lang": "zh",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
            "Origin": "http://libyy.qfnu.edu.cn",
            "Referer": "http://libyy.qfnu.edu.cn/h5/index.html",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,pl;q=0.5",
            "Authorization": auth,  # 认证令牌放在请求头中
        }

        # 发送 POST 请求查询个人座位
        res = send_post_request_and_save_response(
            URL_CHECK_STATUS, post_data, request_headers
        )
        return res

    except KeyError:
        # 如果返回数据中没有预期的字段，可能是 Token 失效
        logger.error("数据获取失败, Token 失效，重新获取")
        return None


# ==================== 可用座位信息查询 ====================
def get_seat_info(build_id, segment, nowday):
    """
    获取指定教室在指定时间段的可用座位列表

    这是抢座的核心数据源，返回所有状态为"空闲"的座位

    Args:
        build_id (int): 教室的楼栋 ID
        segment (str): 时间段 ID
        nowday (str): 日期字符串，如 "2024-06-22"

    Returns:
        list: 可用座位列表，每个元素为 {"id": 座位ID, "no": 座位号}
    """
    interrupted = False  # 用于标记是否被中断

    # 外层循环：防止 KeyboardInterrupt 导致程序崩溃
    while not interrupted:
        try:
            # 内层循环：持续请求直到成功
            while True:
                try:
                    # 构造请求数据
                    post_data = {
                        "area": build_id,  # 教室 ID
                        "segment": segment,  # 时间段 ID
                        "day": nowday,  # 日期
                        "startTime": "08:00",  # 开始时间
                        "endTime": "22:00",  # 结束时间
                    }

                    # 构造 HTTP 请求头
                    request_headers = {
                        "Content-Type": "application/json",
                        "Connection": "keep-alive",
                        "Accept": "application/json, text/plain, */*",
                        "lang": "zh",
                        "X-Requested-With": "XMLHttpRequest",
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
                        "Origin": "http://libyy.qfnu.edu.cn",
                        "Referer": "http://libyy.qfnu.edu.cn/h5/index.html",
                        "Accept-Encoding": "gzip, deflate",
                        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,pl;q=0.5",
                    }

                    # 发送 POST 请求获取座位信息
                    res = send_post_request_and_save_response(
                        URL_CLASSROOM_SEAT, post_data, request_headers
                    )

                    free_seats = []  # 存放空闲座位的列表

                    # 遍历所有座位，筛选出状态为"空闲"的
                    for seat in res["data"]:
                        if seat["status_name"] == "空闲":
                            # 提取座位 ID 和座位号
                            free_seats.append({
                                "id": seat["id"],  # 座位的唯一编号
                                "no": seat["no"]  # 座位号（如 "A-001"）
                            })

                    # 每次请求后等待 1 秒，避免请求过于频繁被限流
                    time.sleep(1)
                    return free_seats  # 返回空闲座位列表

                except requests.exceptions.Timeout:
                    # 请求超时，记录警告并继续重试
                    logger.warning("请求超时，正在重试...")

                except Exception as e:
                    # 其他异常，记录并退出
                    logger.error(f"获取座位信息异常: {str(e)}")
                    sys.exit()

                # 每次重试间隔 1 秒
                time.sleep(1)

        except KeyboardInterrupt:
            # 用户按下 Ctrl+C
            logger.info("主动停止程序")
            interrupted = True

        except Exception as e:
            # 其他异常
            logger.error(f"循环异常: {str(e)}")
            sys.exit()


# ==================== 程序入口 ====================
if __name__ == "__main__":
    # 程序从这里开始执行
    logger.info("")