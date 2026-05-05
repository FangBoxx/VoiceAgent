import os
from dotenv import load_dotenv

load_dotenv()

# ================= OpenAI 配置 =================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("请设置 OPENAI_API_KEY 环境变量（用于 OpenAI Realtime API）")

OPENAI_REALTIME_MODEL = "gpt-realtime-1.5"
OPENAI_WS_URL = f"wss://api.openai.com/v1/realtime?model={OPENAI_REALTIME_MODEL}"

# ================= 业务配置 =================
WECHAT_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=ff85e525-ec09-4e95-aa83-5423e112fcdc"

TWILIO_RATE = 8000      # Twilio 发送的音频采样率 (Hz)
OPENAI_RATE = 24000     # OpenAI Realtime API 要求的采样率 (Hz)

# ================= 数据库配置 =================
MYSQL_HOST = os.getenv("MYSQLHOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQLPORT", 3306))
MYSQL_USER = os.getenv("MYSQLUSER", "root")
MYSQL_PASSWORD = os.getenv("MYSQLPASSWORD", "") 
MYSQL_DB = os.getenv("MYSQL_DATABASE", "blue_whale_park")