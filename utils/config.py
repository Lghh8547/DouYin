import os, sys
from enum import Enum
import json
import logging
from utils.logger import setup_logger

logger = setup_logger(level=logging.DEBUG)

"""
是否启用调试模式
更详细的日志打印，浏览器操作可视化等
"""
DEBUG = True
config = None
userData = None
fileConfig = None


def get_file_config():
    """
    读取项目内配置文件。
    默认优先读取 config.local.json；也可用 CONFIG_FILE 指定其他 JSON 配置文件。
    """
    global fileConfig

    if fileConfig is not None:
        return fileConfig

    config_paths = []
    configured_path = os.getenv("CONFIG_FILE")
    if configured_path:
        config_paths.append(configured_path)
    config_paths.extend(["config.local.json", "config.json"])

    for path in config_paths:
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as file:
            fileConfig = json.load(file)
        logger.info(f"已加载配置文件: {path}")
        return fileConfig

    fileConfig = {}
    return fileConfig


def get_setting(key, default=None):
    env_value = os.getenv(key)
    if env_value is not None:
        return env_value
    return get_file_config().get(key, default)


def parse_json_setting(key, default):
    value = get_setting(key, default)
    if isinstance(value, str):
        return json.loads(value)
    return value


class Environment(Enum):
    GITHUBACTION = "GITHUB_ACTION"  # GitHub Action 运行
    LOCAL = "LOCAL"  # 本地代码运行
    PACKED = "PACKED"  # PyInstaller 打包运行

    def __str__(self):
        return self.value


def get_environment():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Environment.PACKED
    elif os.getenv("GITHUB_ACTIONS") == "true":
        return Environment.GITHUBACTION
    else:
        return Environment.LOCAL


def get_config():
    """
    获取配置信息
    :return: 配置字典
    """
    global config

    if config:
        return config

    config = {
        "proxyAddress": get_setting("PROXY_ADDRESS", ""),
        "messageTemplate": get_setting("MESSAGE_TEMPLATE", "[盖瑞]今日火花[加一]\\n—— [右边] 每日一言 [左边] ——\\n[API]"),
        "hitokotoTypes": parse_json_setting("HITOKOTO_TYPES", ["文学", "影视", "诗词", "哲学"]),
        "matchMode": get_setting("MATCH_MODE", "nickname"),  # 是否使用短 ID 进行好友匹配
        "browserTimeout": int(get_setting("BROWSER_TIMEOUT", "120000")),  # 浏览器操作超时时间，单位毫秒
        "friendListTimeout": int(get_setting("FRIEND_LIST_WAIT_TIME", "2000")),  # 好友列表加载超时时间，单位毫秒
        "taskRetryTimes": int(get_setting("TASK_RETRY_TIMES", "3")),  # 任务重试次数
        "logLevel": get_setting("LOG_LEVEL", "DEBUG"),  # 日志级别
    }

    return config

def sanitize_cookies(cookies):
    if len(cookies) == 1 and isinstance(cookies[0], list):
        cookies = cookies[0]

    for cookie in cookies:
        if "sameSite" in cookie:
            cookie.pop("sameSite")  # 移除 sameSite 字段，Playwright 可能不支持该字段
    return cookies


def get_userData():
    """
    获取用户数据目录
    :return: 用户数据目录路径
    """
    global userData

    if userData:
        return userData

    tasks = parse_json_setting("TASKS", [])

    userData = []

    for task in tasks:
        username = task.get("username", "未知用户")
        unique_id = task.get("unique_id")
        if not unique_id:
            logger.warning(f"{username} 的任务  缺少 unique_id 字段，已跳过")
            continue
        cookies = task.get("cookies")
        if isinstance(cookies, str):
            try:
                cookies = json.loads(cookies.encode("utf-8").decode("unicode_escape"))
            except json.JSONDecodeError:
                logger.warning(f"{username} 的任务 cookies 字段格式不正确，已跳过")
                continue
        if cookies is None:
            cookies_key = f"cookies_{unique_id}".upper()
            cookies_value = get_setting(cookies_key, "")
            if isinstance(cookies_value, str):
                cookies_value = cookies_value.encode("utf-8").decode("unicode_escape")
            if not cookies_value:
                logger.warning(
                    f"{username} 的任务 缺少 cookies 字段或 {cookies_key} 配置，已跳过"
                )
                continue
            try:
                cookies = json.loads(cookies_value) if isinstance(cookies_value, str) else cookies_value
            except json.JSONDecodeError:
                logger.warning(f"{username} 的任务 {cookies_key} 格式不正确，已跳过")
                continue

        userData.append(
            {
                "unique_id": unique_id,
                "username": username,
                "cookies": sanitize_cookies(cookies),
                "targets": task.get("targets", []),
                "group_targets": task.get("group_targets", []),  # 群聊目标列表
            }
        )

    return userData
