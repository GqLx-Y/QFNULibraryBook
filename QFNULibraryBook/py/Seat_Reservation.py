import asyncio
import datetime
import logging
import os
import random
import sys
import time
from typing import SupportsInt

import requests
import yaml
import telegram

from get_bearer_token import get_bearer_token
from get_info import (
    find_seat_id_by_name,
    get_date,
    get_segment,
    get_build_id,
    encrypt,
    get_member_seat,
)

import json
import base64
import hmac
import hashlib
import urllib.parse


# ==================== 日志配置 ====================
logger = logging.getLogger("httpx")
logger.setLevel(logging.ERROR)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


# ==================== API 端点 ====================
URL_GET_SEAT = "http://libyy.qfnu.edu.cn/api/Seat/confirm"
URL_CHECK_OUT = "http://libyy.qfnu.edu.cn/api/Space/checkout"
URL_CANCEL_SEAT = "http://libyy.qfnu.edu.cn/api/Space/cancel"


# ==================== 全局配置变量 ====================
CHANNEL_ID = ""
TELEGRAM_BOT_TOKEN = ""
CLASSROOMS_NAME = []
USER_SEAT_ID = []
DATE = ""
USERNAME = ""
PASSWORD = ""
GITHUB = False
BARK_URL = ""
BARK_EXTRA = ""
ANPUSH_TOKEN = ""
ANPUSH_CHANNEL = ""
DD_BOT_SECRET = ""
DD_BOT_TOKEN = ""
PUSH_METHOD = ""
HOUR = 0
MINUTES = 0


# ==================== 配置文件读取 ====================
def read_config_from_yaml():
    """从 config.yml 读取配置并赋值给全局变量"""
    global CHANNEL_ID, TELEGRAM_BOT_TOKEN, CLASSROOMS_NAME, USER_SEAT_ID, DATE, USERNAME, PASSWORD
    global GITHUB, BARK_EXTRA, BARK_URL, ANPUSH_TOKEN, ANPUSH_CHANNEL, PUSH_METHOD
    global DD_BOT_TOKEN, DD_BOT_SECRET, HOUR, MINUTES

    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_file_path = os.path.join(current_dir, "config.yml")

    if not os.path.exists(config_file_path):
        logger.error(f"配置文件不存在: {config_file_path}")
        sys.exit(1)

    with open(config_file_path, "r", encoding="utf-8") as yaml_file:
        config = yaml.safe_load(yaml_file)

        CHANNEL_ID = config.get("CHANNEL_ID", "")
        TELEGRAM_BOT_TOKEN = config.get("TELEGRAM_BOT_TOKEN", "")
        CLASSROOMS_NAME = config.get("CLASSROOMS_NAME", [])
        USER_SEAT_ID = config.get("USER_SEAT_ID", [])
        DATE = config.get("DATE", "today")
        USERNAME = config.get("USERNAME", "")
        PASSWORD = config.get("PASSWORD", "")
        GITHUB = config.get("GITHUB", False)
        BARK_URL = config.get("BARK_URL", "")
        BARK_EXTRA = config.get("BARK_EXTRA", "")
        ANPUSH_TOKEN = config.get("ANPUSH_TOKEN", "")
        ANPUSH_CHANNEL = config.get("ANPUSH_CHANNEL", "")
        DD_BOT_TOKEN = config.get("DD_BOT_TOKEN", "")
        DD_BOT_SECRET = config.get("DD_BOT_SECRET", "")
        PUSH_METHOD = config.get("PUSH_METHOD", "")
        HOUR = config.get("HOUR")
        MINUTES = config.get("MINUTES")

    logger.info(f"配置加载成功 | 自习室: {CLASSROOMS_NAME} | 座位号: {USER_SEAT_ID} | 日期: {DATE}")


# ==================== 全局状态 ====================
FLAG = False
SEAT_RESULT = {}
USED_SEAT = []
MESSAGE = ""
AUTH_TOKEN = ""
NEW_DATE = ""
TOKEN_TIMESTAMP = None
TOKEN_EXPIRY_DELTA = datetime.timedelta(hours=1, minutes=30)


# 未使用==================== 排除座位ID ====================
EXCLUDE_ID = {
    "7115", "7120", "7125", "7130", "7135", "7140", "7145", "7150",
    "7155", "7160", "7165", "7170", "7175", "7180", "7185", "7190",
    "7241", "7244", "7247", "7250", "7253", "7256", "7259", "7262",
    "7291", "7296", "7301", "7306", "7311", "7316", "7321", "7326",
    "7331", "7336", "7341", "7346", "7351", "7356", "7361", "7366",
    "7369", "7372", "7375", "7378", "7381", "7384", "7387", "7390",
    "7417", "7420", "7423", "7426", "7429", "7432", "7435", "7438",
    "7443", "7448", "7453", "7458", "7463", "7468", "7473", "7478",
    "7483", "7488", "7493", "7498", "7503", "7508", "7513", "7518",
    "7569", "7572", "7575", "7578", "7581", "7584", "7587", "7590",
    "7761", "7764", "7767", "7770", "7773", "7776", "7779", "7782",
    "7785", "7788", "7791", "7794", "7797", "7800", "7803", "7806",
}

# ==================== 通知推送 ====================
def send_message():
    """根据配置的通知方式发送消息"""
    if not MESSAGE:
        return
    if PUSH_METHOD == "TG":
        asyncio.run(send_message_telegram())
    if PUSH_METHOD == "ANPUSH":
        send_message_anpush()
    if PUSH_METHOD == "BARK":
        send_message_bark()
    if PUSH_METHOD == "DD":
        dingtalk("脚本执行通知", MESSAGE, DD_BOT_TOKEN, DD_BOT_SECRET)

# ==================== 钉钉推送 ====================
def dingtalk(text, desp, DD_BOT_TOKEN, DD_BOT_SECRET=None):
    """钉钉机器人通知"""
    url = f"https://oapi.dingtalk.com/robot/send?access_token={DD_BOT_TOKEN}"
    headers = {"Content-Type": "application/json"}
    payload = {"msgtype": "text", "text": {"content": f"{text}\n{desp}"}}

    if DD_BOT_TOKEN and DD_BOT_SECRET:
        timestamp = str(round(time.time() * 1000))
        secret_enc = DD_BOT_SECRET.encode("utf-8")
        string_to_sign = f"{timestamp}\n{DD_BOT_SECRET}"
        string_to_sign_enc = string_to_sign.encode("utf-8")
        hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code).decode("utf-8").strip())
        url = f"{url}&timestamp={timestamp}&sign={sign}"

    response = requests.post(url, headers=headers, data=json.dumps(payload))
    try:
        data = response.json()
        if response.status_code == 200 and data.get("errcode") == 0:
            logger.info("钉钉发送通知消息成功")
        else:
            logger.error(f"钉钉发送通知消息失败: {data.get('errmsg')}")
    except Exception as e:
        logger.error(f"钉钉发送通知消息失败: {e}")

# ==================== bark推送 ====================
def send_message_bark():
    """Bark iOS 推送"""
    try:
        response = requests.get(BARK_URL + MESSAGE + BARK_EXTRA)
        if response.status_code == 200:
            logger.info("成功推送消息到 Bark")
        else:
            logger.error(f"Bark 推送失败，状态码: {response.status_code}")
    except requests.exceptions.RequestException:
        logger.error("Bark 推送异常，请检查链接")

# ==================== anpush推送 ====================
def send_message_anpush():
    """AnPush 推送"""
    url = "https://api.anpush.com/push/" + ANPUSH_TOKEN
    payload = {"title": "预约通知", "content": MESSAGE, "channel": ANPUSH_CHANNEL}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    requests.post(url, headers=headers, data=payload)

# ==================== telegram推送 ====================
async def send_message_telegram():
    """Telegram 推送"""
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=CHANNEL_ID, text=MESSAGE)
        logger.info("成功推送消息到 Telegram")
    except Exception as e:
        logger.error(f"发送消息到 Telegram 失败: {e}")


# ==================== 认证管理 ====================
def get_auth_token():
    """获取或刷新 Bearer Token"""
    global TOKEN_TIMESTAMP, AUTH_TOKEN, MESSAGE
    try:
        if not USERNAME or not PASSWORD:
            raise ValueError("未找到用户名或密码")

        if TOKEN_TIMESTAMP is None or (datetime.datetime.now() - TOKEN_TIMESTAMP) > TOKEN_EXPIRY_DELTA:
            name, token = get_bearer_token(USERNAME, PASSWORD)
            if token is None:
                logger.error("获取 token 失败，账号密码错误或者网络错误。")
                MESSAGE += "\n获取 token 失败，账号密码错误或者网络错误。"
                send_message()
                sys.exit()
            else:
                logger.info(f"成功获取授权码")
                AUTH_TOKEN = "bearer" + str(token)
                TOKEN_TIMESTAMP = datetime.datetime.now()
        else:
            logger.info("使用现有授权码")
    except Exception as e:
        logger.error(f"获取授权码时发生异常: {str(e)}")
        sys.exit()


# ==================== 座位状态检查 ====================
def check_book_seat():
    """检查是否已有预约"""
    global MESSAGE, FLAG
    try:
        res = get_member_seat(AUTH_TOKEN)
        if res is not None and "msg" in res and res["msg"] == "您尚未登录":
            get_auth_token()
        if res is not None and "data" in res:
            for entry in res["data"]["data"]:
                if entry["statusName"] == "预约成功":
                    seat_id = entry["name"]
                    name = entry["nameMerge"]
                    logger.info(f"预约成功：你当前的座位是 {name} {seat_id}")
                    FLAG = True
                    MESSAGE += f"预约成功：你当前的座位是 {name} {seat_id}\n"
                    send_message()
                    break
                elif entry["statusName"] == "使用中" and DATE == "today":
                    logger.info("存在正在使用的座位")
                    FLAG = True
                    break
    except KeyError:
        logger.error("获取个人座位出现错误")


def check_reservation_status():
    """检查预约响应状态"""
    global FLAG, MESSAGE
    if isinstance(SEAT_RESULT, dict) and "msg" in SEAT_RESULT:
        status = SEAT_RESULT["msg"]
        if status == "预约成功":
            logger.info("成功预约")
            check_book_seat()
            FLAG = True
        elif status == "当前用户在该时段已存在座位预约，不可重复预约":
            logger.info("重复预约")
            check_book_seat()
            FLAG = True
        elif status == "开放预约时间19:20":
            logger.info("未到预约时间")
            time.sleep(1)
        elif status == "您尚未登录":
            logger.info("没有登录，将重新尝试获取 token")
            get_auth_token()
        elif status == "该空间当前状态不可预约":
            logger.info("此位置已被预约或位置不可用")
        elif status == "取消成功":
            logger.info("取消成功")
            sys.exit()
        elif status == "请选择座位不能为空":
            logger.error("请选择座位不能为空 - 座位ID可能为空")
        else:
            logger.info(f"未知状态信息: {status}")
            FLAG = True
    else:
        logger.error("未能获取有效的座位预约状态，token已失效")
        MESSAGE += "\n未能获取有效的座位预约状态，token已失效"
        send_message()
        sys.exit()


# ==================== HTTP POST 请求 ====================
def send_post_request_and_save_response(url, data, headers):
    """发送 POST 请求，带重试机制"""
    retries = 0
    while retries < 20:
        try:
            response = requests.post(url, json=data, headers=headers, timeout=120)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.error("请求超时，正在重试...")
            retries += 1
        except Exception as e:
            logger.error(f"request请求异常: {str(e)}")
            retries += 1
    logger.error("超过最大重试次数,请求失败。")
    MESSAGE += "\n超过最大重试次数,请求失败。"
    send_message()
    sys.exit()


# ==================== 预约请求 ====================
def post_to_get_seat(select_id, segment):
    """发送预约请求"""
    global SEAT_RESULT
    origin_data = '{{"seat_id":"{}","segment":"{}"}}'.format(select_id, segment)
    aes_data = encrypt(str(origin_data))

    post_data = {"aesjson": aes_data}
    request_headers = {
        "Content-Type": "application/json",
        "Connection": "keep-alive",
        "Accept": "application/json, text/plain, */*",
        "lang": "zh",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        "Origin": "http://libyy.qfnu.edu.cn",
        "Referer": "http://libyy.qfnu.edu.cn/h5/index.html",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Authorization": AUTH_TOKEN,
    }

    SEAT_RESULT = send_post_request_and_save_response(URL_GET_SEAT, post_data, request_headers)
    check_reservation_status()


# ==================== 主抢座逻辑 ====================
def select_seat(build_id, segment, nowday):
    """核心抢座逻辑"""
    global MESSAGE, FLAG
    retries = 0

    while not FLAG and retries < 200:
        retries += 1
        logger.info("*" * 50)
        logger.info(f"正在尝试第{retries}次循环预约")

        # 根据 USER_SEAT_ID 列表查找对应的系统座位 ID
        logger.info(f"USER_SEAT_ID 当前值: {USER_SEAT_ID} (类型: {type(USER_SEAT_ID)})")
        seat_id_list = find_seat_id_by_name(build_id, USER_SEAT_ID)
        logger.info(f"找到的座位ID列表: {seat_id_list}")

        for seat_id in seat_id_list:
            logger.info(f"尝试预约座位ID: {seat_id}")
            post_to_get_seat(seat_id, segment)
            if SEAT_RESULT.get("msg") == "预约成功":
                logger.info("恭喜成功预约！")
                break

    if retries >= 200:
        logger.error("超过最大重试次数,无法获取座位")
        MESSAGE += "\n超过最大重试次数,无法获取座位"
        send_message()
        sys.exit()

# ==================== 主流程 ====================
def get_info_and_select_seat():
    """主流程：获取信息 -> 验证身份 -> 选择座位"""
    global AUTH_TOKEN, NEW_DATE, MESSAGE
    try:
        NEW_DATE = get_date(DATE)
        get_auth_token()

        for classroom in CLASSROOMS_NAME:
            build_id = get_build_id(classroom)
            segment = get_segment(build_id, NEW_DATE)
            select_seat(build_id, segment, NEW_DATE)

    except KeyboardInterrupt:
        logger.info("主动退出程序，程序将退出。")
# ==================== 时间控制 ====================
def check_time():
    """控制程序的启动时机"""
    global MESSAGE

    current_time = datetime.datetime.now()
    if GITHUB:
        current_time += datetime.timedelta(hours=8)

    reservation_time = current_time.replace(hour=HOUR, minute=MINUTES, second=0, microsecond=0)
    time_difference = (reservation_time - current_time).total_seconds()

    # 如果预约时间已过，则设为明天同一时间
    if time_difference < 0:
        reservation_time = reservation_time + datetime.timedelta(days=1)
        time_difference = (reservation_time - current_time).total_seconds()
        logger.info(f"预约时间已过，调整为明天 {reservation_time.hour}:{reservation_time.minute}")

    logger.info(f"程序等待{time_difference}秒后启动")
    time.sleep(max(0, time_difference - 10))
    get_info_and_select_seat()



# ==================== 程序入口 ====================
if __name__ == "__main__":
    try:
        read_config_from_yaml()
        check_time()
    except KeyboardInterrupt:
        logger.info("主动退出程序，程序将退出。")





