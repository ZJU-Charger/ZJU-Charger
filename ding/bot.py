"""钉钉机器人封装"""

from dingtalkchatbot.chatbot import DingtalkChatbot
from datetime import datetime, timezone, timedelta


class DingBot:
    def __init__(self, webhook, secret):
        self.webhook = webhook
        self.secret = secret
        self.bot = DingtalkChatbot(webhook, secret=secret)

    def _get_timestamp(self):
        """获取当前时间戳（UTC+8）"""
        tz_utc_8 = timezone(timedelta(hours=8))
        return datetime.now(tz_utc_8).strftime("%Y-%m-%d %H:%M:%S")

    def format_status_message(self, data, show_all=False):
        """格式化状态消息

        Args:
            data: API 响应数据，格式为 {"updated_at": "...", "stations": [...]}
            show_all: 是否显示所有站点（包括无空闲的）

        Returns:
            格式化后的消息字符串
        """
        if not data or not data.get("stations"):
            return "暂无数据"

        stations = data["stations"]
        updated_at = data.get("updated_at", self._get_timestamp())

        # 过滤站点
        if not show_all:
            # 只显示有空闲的站点
            stations = [s for s in stations if s.get("free", 0) > 0]

        if not stations:
            return f"当前时间：{updated_at}\n\n暂无可用充电桩"

        # 按空闲数量排序
        stations.sort(key=lambda x: x.get("free", 0), reverse=True)

        message = f"> 当前空闲情况（{updated_at}）\n\n"

        total_free = 0
        total_used = 0
        total_error = 0
        total_total = 0

        for station in stations:
            name = station.get("name", "未知站点")
            free = station.get("free", 0)
            used = station.get("used", 0)
            error = station.get("error", 0)
            total = station.get("total", 0)

            total_free += free
            total_used += used
            total_error += error
            total_total += total

            if free > 0:
                message += f"[可用 {free}] {name}\n"
            else:
                message += f"[可用 0] {name}（无空闲）\n"

        message += f"\n##### **总计**\n"
        message += f"**{total_free}**可用/"
        message += f"**{total_used}**已用/"
        message += f"**{total_error}**错误/"
        message += f"**{total_total}**总端口\n"

        if total_total - total_error > 0:
            usage_rate = (total_used / (total_total - total_error)) * 100
            message += f"\n使用率: **{usage_rate:.2f}%**\n"

        return message

    def send_status_message(self, time, json_content):
        """发送状态消息（旧格式，向后兼容）"""
        if not json_content:
            print("No data to send.")
            return

        # Prepare the message
        total_num = 0
        total_available = 0
        total_used = 0
        total_error = 0
        message = f"> 抓取时间 - {time}\n"
        for site in json_content:
            message += f"##### **{site['site_name']}**\n"
            message += f"**{site['site_available']}**可用/"
            total_available += site["site_available"]
            message += f"**{site['site_used']}**已用/"
            total_used += site["site_used"]
            message += f"**{site['site_error']}**错误/"
            total_error += site["site_error"]
            message += f"**{site['site_total']}**总端口\n\n"
            total_num += site["site_total"]
        message += f"##### **总计**\n"
        message += f"**{total_available}**可用/"
        message += f"**{total_used}**已用/"
        message += f"**{total_error}**错误/"
        message += f"**{total_num}**总端口\n\n"
        message += f"使用率: **{(total_used / (total_num - total_error) * 100) if (total_num - total_error) > 0 else 0:.2f}%**\n\n"
        message += "> 有未收录站点请发送邮箱至 <群主邮箱>\n"
        # Send the message
        try:
            self.bot.send_markdown(title="站点状态更新", text=message)
        except Exception as e:
            print(f"Failed to send message: {e}")
            return
        print("Message sent successfully.")

    def send_markdown(self, title, text):
        """发送 Markdown 消息"""
        try:
            self.bot.send_markdown(title=title, text=text)
            return True
        except Exception as e:
            print(f"Failed to send markdown message: {e}")
            return False

    def send_text(self, msg, at_mobiles=None):
        """发送文本消息"""
        try:
            self.bot.send_text(msg=msg, at_mobiles=at_mobiles)
            return True
        except Exception as e:
            print(f"Failed to send text message: {e}")
            return False

    def send_error_message(self, time):
        """发送错误消息"""
        message = f"抓取时间 - {time}\n"
        message += f"查询API返回异常\n"
        message += "等待十分钟后自动重试\n"
        message += "通知群主"
        # Send the error message
        try:
            self.bot.send_text(msg=message, at_mobiles=["群主手机号"])
        except Exception as e:
            print(f"Failed to send error message: {e}")
            return
        print("Error message sent successfully.")
