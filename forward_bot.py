import asyncio
from telethon import TelegramClient, events
from dotenv import load_dotenv
import os
# from config import KEYWORDS # Không cần import KEYWORDS nếu không lọc

load_dotenv()

# --- Cấu hình ---
API_ID = int(os.getenv('API_ID', 'YOUR_API_ID'))
API_HASH = os.getenv('API_HASH', 'YOUR_API_HASH')
SOURCE_GROUP = -1002060563160  # ID của "BMT FOREX - VIP- PTKT NÂNG CAO"
TARGET_GROUP = -1003895937153   # ID của kênh Admin để nhận log/forward

async def main():
    """Chương trình chính của Forward Bot."""
    print("🤖 Khởi động Forward Bot v2.1 (Fix Sync & Security)...")

    # sequential_updates=True giúp đảm bảo tin nhắn được xử lý đúng thứ tự và tránh lỗi đồng bộ
    client = TelegramClient('session_forwarder', API_ID, API_HASH, sequential_updates=True)

    # Tạo một hàng đợi để đảm bảo thứ tự gửi tin nhắn
    message_queue = asyncio.Queue()

    async def worker():
        """Worker xử lý hàng đợi tin nhắn một cách tuần tự."""
        while True:
            target_entity, message_text = await message_queue.get()
            try:
                await client.send_message(target_entity, message_text)
                print(f"✈️  Đã chuyển tiếp xong: \"{message_text[:30]}...\"")
            except Exception as e:
                print(f"❌ Lỗi khi gửi tin nhắn: {e}")
                await asyncio.sleep(1) # Đợi 1 giây trước khi thử lại nếu lỗi
            finally:
                message_queue.task_done()

    async with client:
        print("✅ Đã kết nối Telegram thành công.")

        # Chạy worker trong nền
        asyncio.create_task(worker())

        try:
            # Tìm ID của các kênh/nhóm
            source_entity = await client.get_entity(SOURCE_GROUP)
            target_entity = await client.get_entity(TARGET_GROUP)

            print(f"   Nguồn: {source_entity.title} (ID: {source_entity.id})")
            print(f"   Đích:  {target_entity.title} (ID: {target_entity.id})")

            @client.on(events.NewMessage(chats=SOURCE_GROUP))
            async def handler(event):
                # Bỏ qua tin nhắn quá cũ (hơn 1 phút) để tránh loop hoặc lỗi sync khi khởi động
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                msg_date = event.message.date

                if (now - msg_date).total_seconds() > 60:
                    print(f"⏳ Bỏ qua tin nhắn cũ từ lúc: {msg_date}")
                    return

                message_text = event.message.message
                if not message_text: return

                print(f"\n📩 Nhận tin: \"{message_text[:50]}...\"")
                await message_queue.put((target_entity, message_text))

            print("\n🎧 Đang lắng nghe tin nhắn...")
            await client.run_until_disconnected()

        except Exception as e:
            print(f"❌ Lỗi trong quá trình thực thi: {e}")
            print("🔄 Đang khởi động lại sau 5 giây...")
            await asyncio.sleep(5)
            await main() # Đệ quy để khởi động lại khi gặp lỗi nặng

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\n❌ Đã xảy ra lỗi: {e}")
