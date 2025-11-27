"""钉钉 webhook 路由处理"""
import hmac
import hashlib
import base64
import urllib.parse
from fastapi import APIRouter, Request, HTTPException, Header
from pydantic import BaseModel
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from ding.commands import parse_command, execute_all_command
from ding.bot import DingBot
from server.config import Config

router = APIRouter(prefix="/ding", tags=["ding"])

class DingMessage(BaseModel):
    """钉钉消息模型"""
    msgtype: str
    text: dict = None
    msgId: str = None

def verify_signature(timestamp, sign, secret):
    """验证钉钉签名"""
    if not secret:
        return True  # 如果没有设置 secret，跳过验证
    
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode('utf-8'),
        string_to_sign.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()
    
    sign_to_verify = base64.b64encode(hmac_code).decode('utf-8')
    return sign == sign_to_verify

@router.post("/webhook")
async def ding_webhook(
    request: Request,
    timestamp: str = Header(None, alias="timestamp"),
    sign: str = Header(None, alias="sign")
):
    """接收钉钉 webhook 请求"""
    # 验证签名
    if not verify_signature(timestamp or "", sign or "", Config.DINGTALK_SECRET):
        raise HTTPException(status_code=403, detail="签名验证失败")
    
    # 解析请求体
    try:
        body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="无效的请求体")
    
    # 提取消息内容
    msg_type = body.get("msgtype", "")
    if msg_type != "text":
        return {"errcode": 0, "errmsg": "只支持文本消息"}
    
    text_content = body.get("text", {}).get("content", "").strip()
    if not text_content:
        return {"errcode": 0, "errmsg": "消息内容为空"}
    
    # 解析命令
    command_type, args = await parse_command(text_content)
    
    # 初始化钉钉机器人
    bot = DingBot(Config.DINGTALK_WEBHOOK, Config.DINGTALK_SECRET)
    
    # 执行命令
    if command_type == "all":
        # 查询所有站点
        result = await execute_all_command()
        if "error" in result:
            bot.send_text(f"查询失败: {result['error']}")
        else:
            message = bot.format_status_message(result, show_all=True)
            bot.send_markdown("全部站点状态", message)
    
    else:
        # 未知命令
        help_text = """可用命令：
- 全部：查看所有站点状态"""
        bot.send_text(help_text)
    
    return {"errcode": 0, "errmsg": "ok"}
