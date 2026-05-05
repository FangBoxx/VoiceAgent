import aiomysql
from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB

# 全局连接池对象
pool = None

async def init_db_pool():
    """初始化数据库连接池（由 FastAPI lifespan 启动时调用）"""
    global pool
    if pool is None:
        try:
            pool = await aiomysql.create_pool(
                host=MYSQL_HOST, 
                port=MYSQL_PORT,
                user=MYSQL_USER, 
                password=MYSQL_PASSWORD,
                db=MYSQL_DB, 
                autocommit=True,  # 开启自动提交
                minsize=1,        # 最小保持连接数
                maxsize=10,       # 最大连接数，防止 Serverless 并发拉起过多打爆数据库
                pool_recycle=3600 # 定期回收连接（1小时），防止 Serverless 容器闲置导致连接被 MySQL 服务端主动断开
            )
            print("🗄️ 数据库连接池已成功初始化")
        except Exception as e:
            print(f"❌ [数据库] 连接池初始化失败: {e}")

async def close_db_pool():
    """关闭数据库连接池（由 FastAPI lifespan 销毁时调用）"""
    global pool
    if pool:
        pool.close()
        await pool.wait_closed()
        print("🗄️ 数据库连接池已关闭")

async def save_to_mysql(info: dict):
    """异步将访客信息写入本地 MySQL 数据库，使用连接池"""
    global pool
    if not pool:
        print("⚠️ [数据库] 连接池未初始化，无法保存数据")
        return

    try:
        # 从连接池中获取一个连接
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                    INSERT INTO visitors 
                    (visitor_name, company, purpose, plate_number, phone, visit_time) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                values = (
                    info.get('visitor_name', '未知'),
                    info.get('company', '未知'),
                    info.get('purpose', '未知'),
                    info.get('plate_number', '未知'),
                    info.get('phone', '未知'),
                    info.get('visit_time')
                )
                await cur.execute(sql, values)
                print("💾 [数据库] 访客信息已成功存入 MySQL")
    except Exception as e:
        print(f"❌ [数据库] 存储失败: {e}")

async def get_recent_visitor_by_phone(phone: str) -> dict | None:
    """根据手机号查询最近一次的访客记录，使用连接池"""
    global pool
    if not phone or phone == "未知":
        return None
        
    if not pool:
        print("⚠️ [数据库] 连接池未初始化，无法查询历史记录")
        return None

    try:
        # 从连接池中获取一个连接
        async with pool.acquire() as conn:
            # 使用 DictCursor 以便按字段名读取数据
            async with conn.cursor(aiomysql.DictCursor) as cur:
                sql = "SELECT * FROM visitors WHERE phone = %s ORDER BY visit_time DESC LIMIT 1"
                await cur.execute(sql, (phone,))
                result = await cur.fetchone()
                
        return result
    except Exception as e:
        print(f"❌ [数据库] 查询历史记录失败: {e}")
        return None