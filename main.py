import os
import json
import base64
import asyncio
import ssl
import audioop
from datetime import datetime
from zoneinfo import ZoneInfo
import websockets
from fastapi import FastAPI, WebSocket, Request, Response
from contextlib import asynccontextmanager


from config import OPENAI_API_KEY, OPENAI_WS_URL, OPENAI_REALTIME_MODEL
from database import save_to_mysql, get_recent_visitor_by_phone, init_db_pool, close_db_pool
from notifier import send_wechat_notification
from agent_prompt import get_system_instructions, TOOLS

# 定义生命周期事件
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db_pool()    # 容器启动时建立连接池
    yield
    await close_db_pool()   # 容器关闭时释放连接池

# 将 lifespan 传入 FastAPI 实例
app = FastAPI(lifespan=lifespan)


@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket):
    """Twilio Media Streams WebSocket 入口"""
    await websocket.accept()
    print("🔗 Twilio Media Stream 已连接")

    stream_sid = None
    call_sid = None
    caller_phone = "未知"
    openai_ws = None
    closing_state = 0

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "OpenAI-Beta": "realtime=v1"
    }

    try:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        openai_ws = await websockets.connect(
            OPENAI_WS_URL,
            extra_headers=headers,
            ssl=ssl_ctx
        )
        print("🔗 OpenAI Realtime API 已连接")

        async def receive_from_twilio():
            nonlocal stream_sid, call_sid, caller_phone
            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)
                    event = data.get("event")

                    if event == "connected":
                        print("📞 Twilio Stream 连接确认")

                    elif event == "start":
                        stream_sid = data["start"]["streamSid"]
                        call_sid = data["start"].get("callSid", "unknown")
                        raw_phone = data["start"].get("customParameters", {}).get("callerPhone", "未知")
                        caller_phone = raw_phone.replace("+86", "").replace("(", "").replace(")", "").replace(" ", "").replace("-", "").strip()
                        print(f"📞 通话开始 | Stream: {stream_sid} | Call: {call_sid} | Phone: {caller_phone}")

                        history = await get_recent_visitor_by_phone(caller_phone)
                        if history:
                            print(f"🔍 [回访识别] 发现熟客：{history.get('visitor_name', '未知')}")
                        else:
                            print("🆕 [回访识别] 新访客")

                        instructions = get_system_instructions(history)

                        await openai_ws.send(json.dumps({
                            "type": "session.update",
                            "session": {
                                "modalities": ["audio", "text"],
                                "instructions": instructions,
                                "voice": "echo",
                                "input_audio_format": "pcm16",
                                "output_audio_format": "pcm16",
                                "input_audio_transcription": {
                                    "model": "whisper-1",
                                    "language":"zh"
                                },
                                "turn_detection": {
                                    "type": "server_vad",
                                    "threshold": 0.4,
                                    "prefix_padding_ms": 500,
                                    "silence_duration_ms": 1200
                                },
                                "tools": TOOLS,
                                "tool_choice": "auto"
                            }
                        }))
                        print("⚙️ OpenAI Session 已按访客身份动态配置")

                        if history:
                            name_prefix = history['visitor_name'][0] if history['visitor_name'] else ''
                            greeting_prompt = (
                                f"这是熟客。请必须直接确认他的历史信息！直接说：'{name_prefix}师傅您好，今天是不是还去{history['company']}{history['purpose']}？车牌还是{history['plate_number']}吗？' 绝对不要问您贵姓或车牌号多少！"
                            )
                        else:
                            greeting_prompt = "这是生客。请直接开口问：'师傅进门登记，您贵姓？车牌号多少？'"

                        await openai_ws.send(json.dumps({
                            "type": "response.create",
                            "response": {
                                "modalities": ["audio", "text"],
                                "instructions": greeting_prompt
                            }
                        }))

                    elif event == "media":
                        payload = base64.b64decode(data["media"]["payload"])
                        pcm_8k = audioop.ulaw2lin(payload, 2)
                        pcm_24k, _ = audioop.ratecv(pcm_8k, 2, 1, 8000, 24000, None)
                        audio_b64 = base64.b64encode(pcm_24k).decode()
                        await openai_ws.send(json.dumps({
                            "type": "input_audio_buffer.append",
                            "audio": audio_b64
                        }))

                    elif event == "stop":
                        print(f"📞 通话结束 | Stream: {stream_sid}")
                        break

            except Exception as e:
                print(f"❌ Twilio 接收异常: {e}")

        async def receive_from_openai():
            nonlocal closing_state
            try:
                async for message in openai_ws:
                    response = json.loads(message)
                    event_type = response.get("type")

                    if event_type == "response.audio.delta":
                        if not stream_sid:
                            continue
                        audio_data = base64.b64decode(response["delta"])
                        pcm_8k, _ = audioop.ratecv(audio_data, 2, 1, 24000, 8000, None)
                        ulaw_data = audioop.lin2ulaw(pcm_8k, 2)
                        await websocket.send_text(json.dumps({
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {
                                "payload": base64.b64encode(ulaw_data).decode()
                            }
                        }))

                    elif event_type == "response.audio_transcript.delta":
                        delta = response.get("delta", "")
                        print(f"\r🤖 老李: {delta}", end="", flush=True)

                    elif event_type == "response.audio.done":
                        print() 

                    elif event_type == "response.done":
                        print("✅ 此轮 OpenAI 响应完成")
                        if closing_state == 1:
                            closing_state = 2
                            print("🔄 工具调用完毕，等待大模型生成最后一句语音流...")
                        elif closing_state == 2:
                            print("👋 结束语已生成，等待音频播放完毕后自动挂断...")
                            await asyncio.sleep(3)
                            try:
                                await websocket.close()
                                print("📞 电话已挂断")
                            except Exception:
                                pass

                    elif event_type == "conversation.item.input_audio_transcription.completed":
                        transcript = response.get("transcript", "")
                        if transcript:
                            print(f"\n👤 访客: {transcript}")

                    elif event_type == "response.function_call_arguments.done":
                        closing_state = 1
                        call_id = response.get("call_id")
                        args = json.loads(response.get("arguments", "{}"))
                        
                        china_time = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
                        args["visit_time"] = china_time
                        args["phone"] = caller_phone
                        
                        print(f"\n🛠️ 触发推送: {args}")

                        await asyncio.create_task(send_wechat_notification(args))
                        await asyncio.create_task(save_to_mysql(args))

                        await openai_ws.send(json.dumps({
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": json.dumps({"success": True, "message": "访客信息已推送"})
                            }
                        }))

                        await openai_ws.send(json.dumps({
                            "type": "response.create",
                            "response": {
                                "modalities": ["audio", "text"],
                                "instructions": "工具调用已成功。请严格执行：直接回复且只回复'好嘞，稍等给您抬杆'，绝不要说任何其他多余的字。"
                            }
                        }))

                    elif event_type == "error":
                        print(f"\n❌ OpenAI 错误: {response}")

            except Exception as e:
                error_msg = str(e).lower()
                if "accept" in error_msg or "disconnect" in error_msg or "closed" in error_msg:
                    print("📞 Twilio 通话流已正常断开")
                else:
                    print(f"❌ Twilio 接收异常: {e}")

        await asyncio.gather(receive_from_twilio(), receive_from_openai())

    except Exception as e:
        print(f"❌ 连接异常: {e}")

    finally:
        if openai_ws:
            try:
                await openai_ws.close()
            except Exception:
                pass
        print("🔗 连接已清理")

@app.post("/twilio/incoming")
async def incoming_call(request: Request):
    """Twilio Webhook 入口"""
    form_data = await request.form()
    caller_phone = form_data.get("From", "未知")

    public_ws_url = os.getenv("PUBLIC_WS_URL")
    if not public_ws_url:
        host = request.headers.get("x-forwarded-host") or request.headers.get("host", "localhost:8000")
        scheme = "wss" if request.headers.get("x-forwarded-proto") == "https" else "ws"
        public_ws_url = f"{scheme}://{host}/media-stream"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{public_ws_url}">
            <Parameter name="callerPhone" value="{caller_phone}" />
        </Stream>
    </Connect>
</Response>"""

    print(f"📲 Twilio 来电，返回 Stream TwiML: {public_ws_url}")
    return Response(content=twiml, media_type="text/xml")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "voice-agent-realtime"}

if __name__ == "__main__":
    import uvicorn
    print("🚀 Voice Agent with OpenAI Realtime API 启动中...")
    print(f"   模型: {OPENAI_REALTIME_MODEL}")
    print(f"   端口: 8000")
    print(f"   WebSocket: /media-stream")
    uvicorn.run(app, host="0.0.0.0", port=8000)