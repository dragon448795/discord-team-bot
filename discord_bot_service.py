# discord_bot_service.py
# 這是一個為 Albion 分隊工具提供 Discord 數據的後台服務
# 需要安裝： pip install flask discord.py

from flask import Flask, request, jsonify
from flask_cors import CORS
import discord
import asyncio
import os

app = Flask(__name__)
CORS(app)  # 允許儀表板網頁呼叫

# ==== 重要：請將這裡的 YOUR_BOT_TOKEN 替換成您自己的 Discord 機器人令牌 ====
# ==== 重要：令牌已改為從環境變數讀取，請在部署平台設置 ====
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
# ======================================================================
# ======================================================================

# 快取，避免短時間內重複查詢同一個訊息
cache = {}

async def get_reactions_from_discord(channel_id, message_id):
    """真正的 Discord API 查詢函數"""
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    
    reactions_data = {}
    
    @client.event
    async def on_ready():
        print(f'Logged in as {client.user}')
        try:
            channel = client.get_channel(channel_id)
            if channel is None:
                channel = await client.fetch_channel(channel_id)
            
            message = await channel.fetch_message(message_id)
            
            # 收集每個反應的用戶名
            for reaction in message.reactions:
                emoji = str(reaction.emoji)
                users = []
                async for user in reaction.users():
                    if not user.bot:  # 過濾掉機器人自己
                        users.append(user.name)
                if users:  # 只記錄有人的反應
                    reactions_data[emoji] = users
                    
        except Exception as e:
            print(f"Error: {e}")
            reactions_data["error"] = str(e)
        finally:
            await client.close()
    
    await client.start(DISCORD_BOT_TOKEN)
    return reactions_data

@app.route('/get_reactions', methods=['GET'])
def get_reactions():
    """API 接口：根據訊息ID獲取反應列表"""
    message_link = request.args.get('message_link', '')
    
    if not message_link:
        return jsonify({"error": "請提供 message_link 參數"}), 400
    
    # 檢查快取
    if message_link in cache:
        print(f"使用快取數據: {message_link}")
        return jsonify(cache[message_link])
    
    try:
        # 從 Discord 訊息連結中提取 channel_id 和 message_id
        # 連結格式：https://discord.com/channels/server_id/channel_id/message_id
        parts = message_link.split('/')
        if len(parts) < 7:
            return jsonify({"error": "無效的 Discord 訊息連結格式"}), 400
        
        # 我們只需要最後兩個部分：channel_id 和 message_id
        channel_id = int(parts[-2])
        message_id = int(parts[-1])
        
        print(f"查詢 Discord 數據: channel={channel_id}, message={message_id}")
        
        # 使用 asyncio 執行異步函數
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        reactions = loop.run_until_complete(get_reactions_from_discord(channel_id, message_id))
        
        # 儲存到快取（5分鐘有效期）
        cache[message_link] = reactions
        if len(cache) > 100:  # 限制快取大小
            cache.pop(next(iter(cache)))
        
        return jsonify(reactions)
        
    except Exception as e:
        return jsonify({"error": f"處理錯誤: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """健康檢查接口"""
    return jsonify({"status": "ok", "service": "discord-reaction-fetcher"})

if __name__ == '__main__':
    # 重要：在運行前，請務必將 YOUR_BOT_TOKEN_HERE 替換為您自己的令牌
    if DISCORD_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("錯誤：請先修改程式碼中的 DISCORD_BOT_TOKEN 為您自己的機器人令牌！")
        exit(1)
    
    print("Discord 反應查詢服務啟動中...")
    print(f"API 接口: http://localhost:5000/get_reactions?message_link=您的訊息連結")
    app.run(host='0.0.0.0', port=5000, debug=False)