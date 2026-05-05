import httpx
from config import WECHAT_WEBHOOK_URL

async def send_wechat_notification(info: dict):
    """异步发送企业微信通知"""
    markdown_content = f"""<font color="warning">**⚠️ 新访客待确认放行**</font>
> **访客姓名**: <font color="info">{info.get('visitor_name')}</font>
> **预计到访**: <font color="comment">{info.get('visit_time')}</font>
> **车牌号码**: <font color="info">{info.get('plate_number')}</font>
> **来访单位**: {info.get('company')}
> **来访事由**: {info.get('purpose')}
> **联系电话**: {info.get('phone')}"""

    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                WECHAT_WEBHOOK_URL,
                json={"msgtype": "markdown", "markdown": {"content": markdown_content}}
            )
            print("✅ 微信推送成功")
    except Exception as e:
        print(f"❌ 微信推送失败: {e}")