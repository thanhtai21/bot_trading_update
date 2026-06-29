import os
import asyncio
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

async def create_session(session_name, bot_name):
    """Tạo session file cho bot"""
    client = TelegramClient(session_name, 
                          int(os.getenv('API_ID')),
                          os.getenv('API_HASH'))
    
    print(f"\n🔐 Tạo session cho {bot_name}...")
    
    try:
        await client.start()
        me = await client.get_me()
        print(f"✅ {bot_name}: Đã đăng nhập với {me.first_name}")
        return True
    except Exception as e:
        print(f"❌ {bot_name}: Lỗi {e}")
        return False
    finally:
        if client.is_connected():
            await client.disconnect()

async def main():
    print("=" * 50)
    print("🤖 THIẾT LẬP SESSION TỰ ĐỘNG ĐĂNG NHẬP")
    print("=" * 50)
    
    # Kiểm tra session hiện có
    sessions = {
        'forward_bot_session': 'Forward Bot',
        'trading_bot_session': 'Trading Bot'
    }
    
    for session_file, bot_name in sessions.items():
        if os.path.exists(f"{session_file}.session"):
            print(f"✓ {bot_name}: Đã có session file")
        else:
            print(f"⚠  {bot_name}: Chưa có session, cần đăng nhập")
            await create_session(session_file, bot_name)
    
    print("\n" + "=" * 50)
    print("🎉 HOÀN THÀNH THIẾT LẬP!")
    print("=" * 50)
    print("\n📁 Các session file đã tạo:")
    
    for session_file, bot_name in sessions.items():
        if os.path.exists(f"{session_file}.session"):
            print(f"   - {session_file}.session")

    print("\n💡 Từ giờ các bot sẽ tự động đăng nhập không cần hỏi!")

if __name__ == "__main__":
    asyncio.run(main())
