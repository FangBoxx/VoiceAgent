# VoiceAgent
本项目是一个模拟真实业务访客记录的智能语音代理（Voice Agent）服务。基于**Fast API**、**Twilio Media Streams**和**OpenAI Realtime API**构建，能够通过电话与访客进行低延迟的实时自然语言交互，自动收集访客信息，并推送到保安室的企业微信群。

项目采用 Python 开发，支持通过 Docker 进行快速容器化部署，并集成了 AI 提示词管理、数据库交互以及消息通知等功能。  

## ✨ 核心特性

- 📞 **实时语音交互**：通过 WebSocket 连接 Twilio 与 OpenAI Realtime API (gpt-realtime-1.5)，实现丝滑的实时语音对话体验。
- 🧠 **智能熟客识别**：根据来电号码自动查询 MySQL 数据库。如果是熟客，AI 会直接核对历史信息（姓名、车牌、常去单位、事由）；如果是生客，则分批引导收集登记信息。
- 🛠️ **工具调用 (Function Calling)**：AI 收集齐必备信息后，自动触发预设工具，将数据进行结构化处理。
- 🔔 **微信通知推送**：集成企业微信 Webhook，访客信息登记完成后立即以 Markdown 格式推送至安保工作群。
- 💾 **异步数据库连接池**：使用 `aiomysql` 实现高效的异步数据库读写，支持访客记录的持久化和查询。
- 🐳 **容器化部署**：提供完整的 Dockerfile 支持，一键构建与部署。

## 🤖 智能查询 Agent (基于 Dify)
为了方便安保人员和管理人员快速查阅历史记录和统计访客信息，本项目专门基于 Dify 框架设计了一个智能数据库查询 Agent。您可以直接使用自然语言（如：“查一下今天下午来过哪些车”、“上周去过 A 公司的访客有哪些”）来检索 MySQL 数据库中的访客记录。

👉 **在线体验：**[Dify 智能查询 Agent](https://udify.app/chat/yHGynkA5sxzSqQZd)

## 📁 项目结构

```text
├── main.py              # 应用程序的主入口文件，负责启动 Voice Agent 核心服务。
├── agent_prompt.py      # 管理和定义 AI 代理的System Prompts及交互逻辑。 
├── config.py            # 局配置文件，用于管理环境变量、API 密钥、数据库连接字符串等配置项。
├── database.py          # 负责与数据库进行交互，处理数据存储、查询和状态持久化。 
├── notifier.py          # 通知模块，负责在特定事件发生时发送警报或消息。 
├── requirements.txt     # Python 依赖清单
└── Dockerfile           # 容器化构建脚本
```
## 🚀 快速开始

### 前置要求
- Python 3.11
- MYSQL数据库
- Twilio账号以及配置好的号码
- OpenAI API Key
- 企业微信机器人Webhook地址

### 1. 本地环境配置
首先，克隆代码并安装依赖：
```Bash
pip install -r requirements.txt
```
在项目根目录创建```.env```文件，并配置以下环境变量：
```Python
# OpenAI 配置
OPENAI_API_KEY=your_openai_api_key

# 数据库配置 (按需修改)
MYSQLHOST=127.0.0.1
MYSQLPORT=3306
MYSQLUSER=root
MYSQLPASSWORD=your_password
MYSQL_DATABASE=blue_whale_park

# 可选：如果使用内网穿透工具(如 ngrok)，需配置公网 WebSocket 网址
# PUBLIC_WS_URL=wss://[your-ngrok-domain.com/media-stream](https://your-ngrok-domain.com/media-stream)
```

### 2. 本地启动运行
运行主程序：
```Bash
python main.py
# 或使用 uvicorn 直接启动
# uvicorn main:app --host 0.0.0.0 --port 8000
```
服务启动后将监听```8000``` 端口。你可以将公网地址（例如通过 ngrok 映射后的``` https://your-domain.com/twilio/incoming```）配置到 Twilio 的 Webhook 中。

### 3. Docker部署
项目已包```Dockerfile```，可以使用Docker进行部署：
```Bash
# 构建镜像
docker build -t bluewhale-voiceagent .

# 运行容器 (记得将环境变量通过文件或命令行参数传入)
docker run -d --name voiceagent -p 8000:8000 --env-file .env bluewhale-voiceagent
```
### 4.云端部署与体验
本项目已成功在 Railway 云平台完成部署并正常运行。

**🎉 直接通话体验**：任何通过验证的电话号码都可以直接拨打 Twilio 提供的专属电话号码，直接与本项目设计的 VoiceAgent 进行实时的语音对话
## ⚙️业务工作流说明
1. 接通电话：Twilio 接收到访客来电，触发 Webhook 并建立 WebSocket 音频流。

2. 号码识别：系统获取来电号码，并在 MySQL 库中查询是否有近期访问记录。

3. 动态提示词：
   - 熟客模式：老李直接询问“还是去 XX 公司吗？车牌还是 XX 吗？”。访客确认后直接放行。
   - 生客模式：老李分批询问访客姓名、车牌号、拜访单位及事由。

4. 信息记录与推送：AI 调用 submit_visitor_info 工具，后台将数据保存入库并通过企业微信机器人发送入园通知。

5. 挂断：语音提示“稍等给您抬杆”后，自动挂断电话。
