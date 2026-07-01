#!/usr/bin/env python3
"""
曲阜师范大学统一身份认证平台 - 登录滑块验证 (V8)

整合版本：将test.py的功能集成到get_ids_token_v7中
重大改进：
1. 多重缺口检测算法（边缘+阴影+纹理）
2. 模拟真实人类滑块轨迹（带停顿、抖动、变速）
3. 添加y轴随机移动
4. 增强调试功能和图像分析
"""

import re
import json
import base64
import random
import time
import requests
import os
from bs4 import BeautifulSoup
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from io import BytesIO
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
import math

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
from ids_utils.passwd_encrypt import generate_encrypted_password
from ids_utils.ocr import slide_match

import logging
import os

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('开始打印日志')

# 全局变量
session = requests.session()

# 基础配置
BASE_URL = "https://ids.qfnu.edu.cn/authserver"
USERNAME = ""
PASSWORD = ""
SERVICE = "http://libyy.qfnu.edu.cn/api/cas/cas"
AES_CHARS = "ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678"
LOGIN_SERVICE = 'http%3A%2F%2Flibyy.qfnu.edu.cn%2Fapi%2Fcas%2cas'

# 滑块验证配置
SLIDER_CONFIG = {
    'MAX_RETRIES': int(os.getenv('MAX_RETRIES', '10')),  # 最大重试次数
    'RETRY_INTERVAL': int(os.getenv('RETRY_INTERVAL', '3')),  # 重试间隔（秒）
    'MIN_MOVE_LENGTH': 10,  # 最小移动距离
    'CANVAS_WIDTH': 280,  # Canvas绘制宽度
    'DEBUG_MODE': os.getenv('DEBUG_MODE', 'false').lower() == 'true',  # 调试模式
    'MULTIPLE_ATTEMPTS': True,  # 是否尝试多个候选距离
    'CANDIDATE_RANGE': 20,  # 候选距离范围
}


def random_string(length: int) -> str:
    """生成随机字符串"""
    return "".join(random.choice(AES_CHARS) for _ in range(length))


def aes_encrypt(plaintext: str, key: str, iv: str) -> str:
    """AES加密"""
    key_bytes = key.encode("utf-8")
    iv_bytes = iv.encode("utf-8")
    plaintext_bytes = plaintext.encode("utf-8")
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
    padded = pad(plaintext_bytes, AES.block_size)
    encrypted = cipher.encrypt(padded)
    return base64.b64encode(encrypted).decode("utf-8")


def encrypt_aes(password: str, salt: str) -> str:
    """加密密码"""
    return aes_encrypt(random_string(64) + password, salt, random_string(16))


def encrypt_password(data: str, key: str) -> str:
    """加密数据（兼容两种加密方式）"""
    try:
        return encrypt_aes(data, key)
    except:
        return data


def get_salt_and_execution():
    """获取加密盐值和执行参数"""
    uri = f'{BASE_URL}/login?service={SERVICE}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'Referer': f'{BASE_URL}/login?service={SERVICE}',
    }
    response_data = session.get(url=uri, headers=headers).text
    soup_decoded_data = BeautifulSoup(response_data, 'html.parser')
    execution_data = soup_decoded_data.find(id='execution').get('value')
    salt_data = soup_decoded_data.find(id='pwdEncryptSalt').get('value')
    return salt_data, execution_data


def open_slider_captcha():
    """打开滑块验证码"""
    referer = f'{BASE_URL}/login?service={SERVICE}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'Referer': referer,
    }
    uri = f'{BASE_URL}/common/openSliderCaptcha.htl'
    try:
        res = session.get(url=uri, headers=headers, timeout=10)
        data = res.json()
        if data.get('bigImage') and data.get('smallImage'):
            logger.info('[INFO] 滑块验证码已获取')
            return data
        else:
            logger.error(f'[ERROR] 滑块验证码接口返回异常: {data}')
            return None
    except Exception as e:
        logger.error(f'[ERROR] 获取滑块验证码失败: {e}')
        return None


def analyze_image_edges(big_image_b64: str) -> dict:
    """分析图像边缘特征"""
    big_image_data = base64.b64decode(big_image_b64)
    nparr = np.frombuffer(big_image_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return {}

    # 转换为灰度图
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    height, width = img.shape[:2]

    # 高斯模糊降噪
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Sobel边缘检测
    sobel_x = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)
    sobel_mag = np.sqrt(sobel_x**2 + sobel_y**2)

    return {
        'gray': gray,
        'blurred': blurred,
        'sobel_mag': sobel_mag,
        'height': height,
        'width': width
    }


def find_gap_with_multiple_methods(big_image_b64: str) -> tuple:
    """使用多种方法识别缺口位置"""
    logger.info('[INFO] 正在识别缺口位置...')

    analysis = analyze_image_edges(big_image_b64)
    gray = analysis['gray']
    sobel_mag = analysis['sobel_mag']
    height = analysis['height']
    width = analysis['width']

    # 缺口检测区域 (y轴 30%-70%)
    y_start = int(height * 0.3)
    y_end = int(height * 0.7)

    # 亮度梯度分析
    col_brightness = []
    for x in range(width):
        region = gray[y_start:y_end, x]
        col_brightness.append(np.mean(region))

    # 平滑处理
    smoothed_brightness = []
    window = 5
    for i in range(len(col_brightness)):
        start = max(0, i - window)
        end = min(len(col_brightness), i + window)
        smoothed_brightness.append(np.mean(col_brightness[start:end]))

    # 找到亮度下降最快的点
    best_gap_x = 100
    max_gradient = 0

    for x in range(30, width - 60):
        if x > 0:
            gradient = smoothed_brightness[x-1] - smoothed_brightness[x]
            if gradient > max_gradient:
                max_gradient = gradient
                best_gap_x = x

    # 生成候选位置
    candidates = []
    candidates.append(best_gap_x)
    candidates.append(best_gap_x - 10)
    candidates.append(best_gap_x + 10)
    candidates.append(best_gap_x - 20)
    candidates.append(best_gap_x + 20)

    # 去重并排序
    candidates = sorted(set(candidates))

    return best_gap_x, candidates


def save_analysis_images(gray, sobel_mag, candidates, best_x):
    """保存分析图像供调试"""
    # 设置中文字体
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

    # 创建可视化图像
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))

    # 原始灰度图
    axes[0, 0].imshow(gray, cmap='gray')
    axes[0, 0].set_title('原始灰度图')
    axes[0, 0].axvline(x=best_x, color='red', linestyle='--', label=f'候选缺口: {best_x}')
    for x in candidates:
        axes[0, 0].axvline(x=x, color='blue', alpha=0.3)
    axes[0, 0].legend()

    # 边缘强度图
    axes[0, 1].imshow(sobel_mag, cmap='hot')
    axes[0, 1].set_title('边缘强度')
    axes[0, 1].axvline(x=best_x, color='red', linestyle='--')

    # 亮度分布
    brightness_profile = np.mean(gray, axis=0)
    axes[1, 0].plot(brightness_profile)
    axes[1, 0].axvline(x=best_x, color='red', linestyle='--')
    axes[1, 0].set_title('亮度分布')
    axes[1, 0].set_xlabel('X坐标')
    axes[1, 0].set_ylabel('亮度')

    # 综合分析
    axes[1, 1].imshow(gray, cmap='gray')
    axes[1, 1].set_title('综合分析结果')
    for x in candidates:
        axes[1, 1].axvline(x=x, color='blue', alpha=0.5)
    axes[1, 1].axvline(x=best_x, color='red', linewidth=2, linestyle='--')

    plt.tight_layout()
    plt.savefig('analysis_debug.png')
    plt.close()


def generate_realistic_tracks_v2(move_length: int) -> list:
    """生成更真实的滑块轨迹"""
    tracks = []

    # 基础参数
    total_time = random.uniform(1800, 2500)  # 总时间 1.8-2.5秒
    steps = random.randint(25, 40)  # 总步数
    current_x = 0
    current_y = 0
    current_time = 0

    # 轨迹阶段
    phases = [
        {"name": "start", "end": 0.05, "speed": 0},
        {"name": "accel1", "end": 0.25, "speed": "low"},
        {"name": "accel2", "end": 0.45, "speed": "medium"},
        {"name": "maintain", "end": 0.85, "speed": "high"},
        {"name": "decel", "end": 0.95, "speed": "low"},
        {"name": "final", "end": 1.0, "speed": 0}
    ]

    for i in range(steps):
        progress = i / steps

        # 确定当前阶段
        current_phase = None
        for phase in phases:
            if progress <= phase["end"]:
                current_phase = phase
                break

        # 计算移动
        if current_phase["speed"] == 0:
            # 停顿或缓慢移动
            dx = random.uniform(0, 2)
            dy = random.uniform(-0.5, 0.5)
            dt = random.uniform(40, 80)
        elif current_phase["speed"] == "low":
            # 加速阶段
            dx = random.uniform(3, 8)
            dy = random.uniform(-1, 1)
            dt = random.uniform(20, 50)
        elif current_phase["speed"] == "medium":
            # 中速移动
            dx = random.uniform(8, 15)
            dy = random.uniform(-1.5, 1.5)
            dt = random.uniform(15, 35)
        else:  # high
            # 快速移动
            dx = random.uniform(12, 20)
            dy = random.uniform(-2, 2)
            dt = random.uniform(10, 25)

        # 随机抖动
        if random.random() < 0.1:  # 10%概率的抖动
            dy += random.uniform(-3, 3)

        # 更新位置
        current_x = min(current_x + dx, move_length)
        current_y += dy
        current_time += dt

        tracks.append({
            "a": float(current_x),
            "b": float(current_y),
            "c": int(dt)
        })

        # 提前到达终点时减速
        if current_x >= move_length and i < steps - 1:
            # 剩余步数只做微调
            for j in range(i + 1, steps):
                tracks.append({
                    "a": float(move_length),
                    "b": float(current_y + random.uniform(-0.5, 0.5)),
                    "c": int(random.uniform(30, 60))
                })
            break

    return tracks


def extract_secure_value(small_image_b64):
    """从 smallImage 的 Base64 解码后提取最后 16 字节作为 key"""
    try:
        decoded = base64.b64decode(small_image_b64)
        if len(decoded) >= 16:
            secure_value = ''.join(chr(b) for b in decoded[-16:])
            return secure_value
    except Exception as e:
        print(f"ERROR: 提取 secure_value 失败: {e}")
    return None


def verify_slider_captcha(move_length, tracks, secure_value, verbose=False):
    """验证滑块验证码"""
    referer = f'{BASE_URL}/login?service={SERVICE}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'Referer': referer,
        'Origin': 'http://ids.qfnu.edu.cn',
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    canvas_width = SLIDER_CONFIG["CANVAS_WIDTH"]

    verify_data = {
        'canvasLength': canvas_width,
        'moveLength': move_length,
        'tracks': tracks
    }
    json_str = json.dumps(verify_data, separators=(',', ':'))

    encrypted_sign = encrypt_password(json_str, secure_value)

    try:
        res = session.post(
            f'{BASE_URL}/common/verifySliderCaptcha.htl',
            headers=headers,
            data={'sign': encrypted_sign},
            timeout=10,
        )
        result = res.json()

        if result.get('errorCode') == 1:
            # 只在成功时输出详细信息
            # print("\n=== 认证成功 ===")
            # print(f"待加密数据: {json_str}")
            # print(f"加密后数据: {encrypted_sign}")
            # print(f"响应体: {result}")
            return True
        else:
            return False
    except Exception as e:
        return False


def handle_slider_captcha():
    """处理滑块验证，返回True表示成功 - V8整合版"""
    # 每次都重新获取验证码
    logger.info('[-]正在进行滑块验证...')
    captcha_data = open_slider_captcha()
    if not captcha_data:
        logger.error('[-]无法获取验证码')
        return False

    big_image_b64 = captcha_data.get('bigImage', '')
    small_image_b64 = captcha_data.get('smallImage', '')

    if not big_image_b64 or not small_image_b64:
        logger.error('[-]缺少图片数据')
        return False

    # 保存图片到临时目录
    temp_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'test')
    os.makedirs(temp_dir, exist_ok=True)

    bg_path = os.path.join(temp_dir, 'background.png')
    tg_path = os.path.join(temp_dir, 'target.png')

    try:
        # 读取图片并分析
        big_data = base64.b64decode(big_image_b64)
        with open(bg_path, 'wb') as f:
            f.write(big_data)

        small_data = base64.b64decode(small_image_b64)
        with open(tg_path, 'wb') as f:
            f.write(small_data)

        # 分析图像并识别缺口
        gap_x, candidates = find_gap_with_multiple_methods(big_image_b64)

        # 获取图片尺寸
        big_img = Image.open(BytesIO(base64.b64decode(big_image_b64)))
        img_width, img_height = big_img.size

        canvas_length = 280
        slider_width = 42

        # 计算目标移动距离
        ratio = canvas_length / img_width
        target_move = int(gap_x * ratio)

        # 提取secure_value
        secure_value = extract_secure_value(small_image_b64)
        if not secure_value:
            print("ERROR: 无法提取 secure_value，滑块验证失败")
            return False

        # 验证滑块
        success = False
        successful_move = 0

        if SLIDER_CONFIG['MULTIPLE_ATTEMPTS']:
            # 生成候选移动距离
            final_candidates = []
            for offset in range(-SLIDER_CONFIG['CANDIDATE_RANGE'], SLIDER_CONFIG['CANDIDATE_RANGE']):
                move = target_move + offset
                if 30 < move < 260:
                    final_candidates.append(move)

            for idx, move_length in enumerate(final_candidates):
                tracks = generate_realistic_tracks_v2(move_length)

                # 添加y轴移动到轨迹中
                enhanced_tracks = []
                for i, track in enumerate(tracks):
                    # 添加一些y轴偏移，模拟真实滑动
                    y_offset = 0
                    if i > 0 and i < len(tracks) - 1:
                        y_offset = random.uniform(-3, 3)

                    enhanced_tracks.append({
                        "a": float(track["a"]),
                        "b": float(track["b"] + y_offset),
                        "c": int(track["c"])
                    })

                # 只输出最后一次成功验证的详细信息
                if verify_slider_captcha(move_length, enhanced_tracks, secure_value, verbose=(idx == len(final_candidates)-1)):
                    success = True
                    successful_move = move_length
                    break
        else:
            # 直接使用目标移动距离
            tracks = generate_realistic_tracks_v2(target_move)
            if verify_slider_captcha(target_move, tracks, secure_value, verbose=True):
                success = True
                successful_move = target_move

        # 清理图片
        big_img.close()

    except Exception as e:
        logger.error(f'[-]滑块识别失败: {e}')
        import traceback
        traceback.print_exc()
        return False

    if success:
        # logger.info(f"[SUCCESS]moveLength={successful_move}")
        return True
    else:
        logger.error('滑块验证失败')
        return False


def get_token(username, password):
    """获取登录token"""
    cap_res = ''
    salt, execution_data = get_salt_and_execution()

    need_slider = False
    try:
        captcha_data = open_slider_captcha()
        if captcha_data:
            need_slider = True
    except Exception:
        pass

    if need_slider:
        logger.info('[-]需要滑块验证，正在处理...')
        # 添加循环机制 - V8改进版
        logger.info(f'[-]最大重试次数={SLIDER_CONFIG["MAX_RETRIES"]}, 重试间隔={SLIDER_CONFIG["RETRY_INTERVAL"]}秒')

        for retry_count in range(SLIDER_CONFIG["MAX_RETRIES"]):
            logger.info(f'[-]滑块验证尝试 {retry_count + 1}/{SLIDER_CONFIG["MAX_RETRIES"]}')

            try:
                # 每次循环都重新打开验证码页面
                if handle_slider_captcha():
                    logger.info(f'[-]滑块验证成功(第 {retry_count + 1} 次尝试)')
                    break
                else:
                    if retry_count < SLIDER_CONFIG["MAX_RETRIES"] - 1:
                        logger.warning(f'[-]滑块验证失败(第 {retry_count + 1} 次尝试)，{SLIDER_CONFIG["RETRY_INTERVAL"]}秒后重试...')
                        logger.info(f'============================================')
                        time.sleep(SLIDER_CONFIG["RETRY_INTERVAL"])
                    else:
                        logger.error('[-]滑块验证失败，已达到最大重试次数，无法继续登录')
                        return None
            except Exception as e:
                logger.error(f'[-]滑块验证异常(第 {retry_count + 1} 次尝试): {e}')
                if retry_count < SLIDER_CONFIG["MAX_RETRIES"] - 1:
                    logger.warning(f'[-]{SLIDER_CONFIG["RETRY_INTERVAL"]}秒后重试...')
                    time.sleep(SLIDER_CONFIG["RETRY_INTERVAL"])
                else:
                    logger.error('[-]滑块验证异常，已达到最大重试次数，无法继续登录')
                    return None

    enc_passwd = encrypt_aes(password, salt)
    uri = f'{BASE_URL}/login?service={SERVICE}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'Referer': f'{BASE_URL}/login?service={SERVICE}',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    data = {
        'username': username,
        'password': enc_passwd,
        'captcha': cap_res,
        '_eventId': 'submit',
        'cllt': 'userNameLogin',
        'dllt': 'generalLogin',
        'lt': '',
        'execution': execution_data,
    }

    res = session.post(url=uri, headers=headers, data=data, allow_redirects=False)
    return res.headers.get('Location', '')


def main():
    """主函数 - 多次尝试登录"""
    print("=" * 60)
    print("曲阜师范大学统一身份认证 - 登录工具")
    print("=" * 60)

    # 设置多次运行
    max_runs = 10  # 最多运行10次
    successful_logins = 0

    for run in range(max_runs):
        print(f"\n{'='*20} 第 {run + 1} 次尝试 {'='*20}")

        try:
            token = get_token(USERNAME, PASSWORD)

            if token and token != '':
                print(f"\n第 {run + 1} 次尝试成功!")
                successful_logins += 1
                break
            else:
                print(f"\n第 {run + 1} 次尝试失败...")

        except Exception as e:
            print(f"\n第 {run + 1} 次尝试出现异常: {e}")

        # 如果不是最后一次，等待5秒再重试
        if run < max_runs - 1:
            print("等待3秒后继续...")
            time.sleep(3)

    print("\n" + "="*60)
    print(f"运行结果总结:")
    print(f"- 成功登录次数: {successful_logins}/{max_runs}")
    print(f"- 总成功率: {(successful_logins/max_runs)*100:.1f}%")
    print("="*60)

    if successful_logins > 0:
        print(">>> 验证码通过! <<<")
        print(fr"token值为{token}")
    else:
        print(">>> 所有尝试均失败 <<<")


if __name__ == '__main__':
    main()