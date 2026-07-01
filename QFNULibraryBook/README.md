# QFNULibraryBook

曲阜师范大学图书馆预约程序

## 项目简介

本项目是一个用于曲阜师范大学图书馆座位预约的自动化脚本，旨在为有学习需求的同学提供便捷的预约方式，帮助大家更高效地利用学习资源。本项目已集成 V8 版本的滑块验证功能，支持自动验证码识别，大幅提升抢座成功率。

## 免责声明和使用声明

本脚本仅供学习使用，使用本脚本预约图书馆座位后，请合理、有效地利用座位时间进行学习，以免占用其他有需求同学的学习资源。

**注意事项：**

1. 使用本脚本预约座位后，请按时前往图书馆学习。不得恶意占用座位或空占资源。
2. 本项目不对因违规使用或不当操作而导致的任何后果承担责任。
3. 请自觉遵守图书馆的相关规定，合理使用学习资源，共同维护良好的学习环境。

本项目为公益性质，任何滥用行为与开发者无关。开发者保留在必要时对项目进行调整或关闭的权利。

## 功能特点

- **智能滑块验证**：集成 V8 版本滑块验证功能，自动识别验证码，成功率大幅提升
- **智能座位选择**：支持指定座位号或随机选择，可根据自习室位置信息智能匹配
- **多时段支持**：支持预约今天、明天或指定日期的座位
- **自动签到签退**：支持自动签到和签退功能
- **多渠道通知**：支持钉钉、Telegram、Bark、Anpush等通知方式
- **自动重试机制**：网络请求失败时自动重试，确保抢座成功
- **灵活配置**：支持多个教室和座位号配置，可按优先级尝试

## 快速启动

### 前提条件

- Python 3.12.1（Python 3.10+）
- 运行环境：Windows 10、Ubuntu 20.04、MacOS 12.0+ 

### 安装依赖

```bash
pip install -r py/requirements.txt
```

### 配置程序

打开配置文件 `py/config.yml`，根据注释修改配置项：

#### 必填项
1. `USERNAME`：图书馆账号（学号）
2. `PASSWORD`：图书馆密码
3. `CLASSROOMS_NAME`：自习室名称列表（从 `json/seat_info` 目录查看支持的教室）
4. `USER_SEAT_ID`：座位号列表（支持多个，按顺序尝试）
5. `DATE`：预约日期（`today` 今天 / `tomorrow` 明天 / `2024-01-01` 指定日期）
6. `HOUR` 和 `MINUTES`：预约时间（24小时制）

#### 可选通知配置
7. `PUSH_METHOD`：通知方式（可选值：TG、ANPUSH、BARK、DD）
8. 对应通知方式的相关配置：
   - **TG**：`TELEGRAM_BOT_TOKEN` 和 `CHANNEL_ID`
   - **DD**：`DD_BOT_TOKEN` 和 `DD_BOT_SECRET`
   - **BARK**：`BARK_URL` 和 `BARK_EXTRA`
   - **ANPUSH**：`ANPUSH_TOKEN` 和 `ANPUSH_CHANNEL`

#### 高级配置
9. `GITHUB`：是否在 GitHub Actions 中运行（自动处理时差）
10. 排除座位：系统内置排除列表 `EXCLUDE_ID`，包含特殊座位编号

### 程序介绍

#### 主要程序

- **`py/Seat_Reservation.py`**：统一抢座程序（推荐使用）
  - 集成 V8 滑块验证功能
  - 支持多教室、多座位配置
  - 智能时间控制，可预约今天、明天或指定日期
  - 自动处理登录、抢座、通知全流程

#### 辅助程序

- **`py/check_in.py`**：签到程序，签到图书馆。该功能属于**违规操作**，请务必**谨慎使用**。
- **`py/sign_out.py`**：签退程序，签退图书馆。

#### 兼容性说明

旧版本的三个预约模式（`get_seat_tomorrow_mode_1.py`、`get_seat_tomorrow_mode_2.py`、`get_seat_tomorrow_mode_3.py`）已被新的统一程序 `Seat_Reservation.py` 替代，建议使用新版本以获得更好的功能和稳定性。

### 运行方式

#### 直接运行（推荐）

```bash
# 运统一抢座程序（推荐）
python py/Seat_Reservation.py

# 运行签到（谨慎使用）
python py/check_in.py

# 运行签退
python py/sign_out.py
```

**Seat_Reservation.py 使用说明：**
1. 程序会自动等待到配置的时间开始抢座
2. 支持多教室配置，会依次尝试每个教室
3. 支持多座位号配置，会按顺序尝试每个座位
4. 成功预约后会自动发送通知

## 技术特点

### V8 滑块验证功能

最新版本已集成 V8 滑块验证功能，具备以下特点：

- **多重缺口检测算法**：结合边缘检测、阴影分析和纹理特征
- **真实人类轨迹模拟**：包含停顿、抖动、变速等自然行为
- **Y轴随机移动**：模拟真实滑动时的上下偏移
- **多重尝试机制**：最多尝试10次，提高成功率
- **自动验证码识别**：自动获取、识别和提交验证码

### 核心架构

项目采用模块化设计，主要组件包括：

- **认证模块**：`get_bearer_token_v8.py` - 处理登录和验证码
- **信息获取模块**：`get_info.py` - 获取座位、教室、时间段信息
- **核心预约模块**：`Seat_Reservation.py` - 主要抢座逻辑
- **通知模块**：支持多种通知方式的实现
- **工具模块**：`ids_utils/` - 包含加密、OCR等工具函数

### 自动化流程

1. **配置读取**：从 `config.yml` 读取用户配置
2. **时间等待**：等待到达预设的预约时间
3. **身份验证**：自动处理登录和滑块验证
4. **信息获取**：获取可用座位和时间段信息
5. **智能抢座**：按配置顺序尝试预约座位
6. **状态检查**：检查预约状态并发送通知

## 贡献者

### 核心贡献
- **[@GqLx-Y](https://github.com/W1ndys)**：三次开发者，整合 V8 滑块验证功能
- **[@W1ndys](https://github.com/W1ndys)**：二次开发者
- **[@sakurasep](https://github.com/sakurasep)**：原作者
- **[@nakaii-002](https://github.com/nakaii-002)**：签到功能贡献者，获取身份验证 Auth_Token 的实现

### V8 滑块验证
- **V8 版本整合**：集成自动滑块验证功能，大幅提升登录成功率
- **自动识别技术**：采用先进的图像识别算法处理验证码

## 开源许可协议

本项目是由 [W1ndys](https://github.com/W1ndys) 基于 [上杉九月](https://github.com/sakurasep) 的 开源项目 [qfnuLibraryBook](https://github.com/sakurasep/qfnuLibraryBook) 二次开发，使用 CC BY-NC 4.0 协议进行授权，拷贝、分享或基于此进行创作时请遵守协议内容：

```
Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)

This is a human-readable summary of (and not a substitute for) the license. You are free to:

Share — copy and redistribute the material in any medium or format
Adapt — remix, transform, and build upon the material

The licensor cannot revoke these freedoms as long as you follow the license terms.
Under the following terms:

Attribution — You must give appropriate credit, provide a link to the license, and indicate if changes were made. You may do so in any reasonable manner, but not in any way that suggests the licensor endorses you or your use.

NonCommercial — You may not use the material for commercial purposes.

No additional restrictions — You may not apply legal terms or technological measures that legally restrict others from doing anything the license permits.

Notices:

## 故障排除

### 常见问题

#### 1. 导入错误
```
ModuleNotFoundError: No module named 'get_bearer_token_v8'
```
**解决方案**：
- 确保 `get_bearer_token_v8.py` 文件在 `py/` 目录下
- 检查 Python 路径设置

#### 2. 滑块验证失败
- **检查网络连接**：确保网络通畅
- **查看日志**：程序会自动重试最多10次
- **账号密码**：确认账号密码正确

#### 3. 找不到座位信息
```
JSON 文件不存在: json/seat_info/xxx.json
```
**解决方案**：
- 检查 `CLASSROOMS_NAME` 配置是否正确
- 查看 `json/seat_info` 目录下有哪些教室数据

#### 4. 时间配置问题
- **24小时制**：`HOUR` 和 `MINUTES` 使用24小时制
- **时区处理**：如果使用 GitHub Actions，设置 `GITHUB: true` 会自动加8小时

### 依赖安装

确保安装所有必要的依赖包：
```bash
pip install -r py/requirements.txt
```

**主要依赖说明**：
- `requests`：HTTP 请求库
- `pyyaml`：YAML 配置文件解析
- `python-telegram-bot`：Telegram 机器人通知
- `pycryptodome`：加密相关功能
- `beautifulsoup4`：HTML 解析
- `cryptography`：安全加密功能

You do not have to comply with the license for elements of the material in the public domain or where your use is permitted by an applicable exception or limitation.
No warranties are given. The license may not give you all of the permissions necessary for your intended use. For example, other rights such as publicity, privacy, or moral rights may limit how you use the material.

## 写到最后(使用流程小白版)
**库准备**：在pycharm终端中使用pip install命令安装必要的库，复制pip install -r py/requirements.txt运行即可

**配置信息**：在config.yml文件中按照注释要求配置信息，如果要使用钉钉推送则需要在钉钉上建一个群配置群机器人，在config.yml中填写DD_BOT_TOKEN和DD_BOT_SECRET字段

**使用细节**：在config.yml中可以选择场馆CLASSROOMS_NAME(确保名称与系统一致，这里只可以选一个，否则会出现逻辑错误)和座位号USER_SEAT_ID(可选多个座位，按顺序尝试)，可以选择预约时间，如果要预约第二天的座位，则填入tomorrow并将时间设置为19：20(可第一时间抢到第二天的座位)

**最终执行**：
- `Seat_Reservation.py`：指定位置定时预约
- `check_in.py`：自动签到，需预约后才可使用
- `sign_out.py`：自动签退，需签到后才可使用

**写道最最后**：
使用程序进行操作时不要登录系统，否则可能发生未知报错









