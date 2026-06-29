import asyncio
import re
import os
import json
from datetime import datetime
from telethon import TelegramClient, events
import time
import requests
from collections import deque
import zmq

# Import cấu hình
from config import TRADING_CONFIG, KEYWORDS, NOTIFICATION_BOT_TOKEN, NOTIFICATION_CHAT_ID

load_dotenv()

API_ID = int(os.getenv('API_ID', 'YOUR_API_ID'))
API_HASH = os.getenv('API_HASH', 'YOUR_API_HASH')

# Group đích mà bot sẽ đọc tin nhắn
TARGET_GROUP = -1003895937153

# ZeroMQ port để kết nối tới EA MT5
EA_SOCKET_PORT = int(os.getenv('EA_SOCKET_PORT', '5555'))

# Biến toàn cục để lưu trữ tín hiệu đang chờ (chưa có SL/TP)
pending_signal_storage = {}
# Biến toàn cục để lưu trữ tín hiệu vào lệnh thành công gần nhất (cho Re-entry)
last_executed_signal = {}


# ========== CÁC HÀM PHÂN TÍCH SL/TP RIÊNG LẺ ==========
def parse_sl_tp_only(message):
    msg_lower = message.lower()
    
    if 'sl' not in msg_lower and 'tp' not in msg_lower:
        return None

    if any(keyword in msg_lower for keyword in ['buy', 'sell']):
        return None
    
    if re.search(r'\d{4,5}\.?\d*\s*-\s*\d{4,5}\.?\d*', msg_lower):
        return None

    sl_price = None
    tp_info = None

    sl_match_full = re.search(r'sl\s*:?\s*(\d{4,5}\.?\d*)', msg_lower)
    sl_match_short = re.search(r'sl\s*:?\s*(\d{1,2}(?:\.\d*)?)', msg_lower)

    if sl_match_full:
        sl_price = float(sl_match_full.group(1))
    elif sl_match_short:
        sl_price = float(sl_match_short.group(1))

    tp_match = re.search(r'tp\s*:?\s*(?:trên\s+|)(\d+)\s*pip', msg_lower)
    if tp_match:
        tp_info = {'pips': int(tp_match.group(1))}
        
    if sl_price is not None or tp_info is not None:
        return {'action': 'UPDATE_SLTP', 'stop_loss': sl_price, 'take_profit': tp_info}

    return None


# ========== CÁC HÀM GỬI THÔNG BÁO COPY ==========
async def send_copy_notification(message: str):
    """Gửi thông báo sao chép đến bot Telegram được cấu hình."""
    if not NOTIFICATION_BOT_TOKEN or NOTIFICATION_CHAT_ID == 'YOUR_NOTIFICATION_CHAT_ID':
        print("⚠️ Cảnh báo: NOTIFICATION_BOT_TOKEN hoặc NOTIFICATION_CHAT_ID chưa được cấu hình. Không gửi thông báo sao chép.")
        return
    
    url = f"https://api.telegram.org/bot{NOTIFICATION_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": NOTIFICATION_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = await asyncio.to_thread(requests.post, url, json=payload)
        response.raise_for_status()
        print("✅ Đã gửi thông báo sao chép thành công!")
    except requests.exceptions.RequestException as e:
        print(f"❌ Lỗi khi gửi thông báo sao chép: {e}")
    except Exception as e:
        print(f"❌ Lỗi không xác định khi gửi thông báo sao chép: {e}")


# ======== HÀM HỖ TRỢ DÀNH CHO LOGIC MỚI ==========
def get_nearest_price(current_price, short_price):
    if short_price >= 100:
        return float(short_price)

    current_price = float(current_price)
    short_price = float(short_price)

    base_100 = int(current_price / 100)
    
    price_low = float((base_100 - 1) * 100 + short_price)
    price_mid = float(base_100 * 100 + short_price)
    price_high = float((base_100 + 1) * 100 + short_price)

    diff_low = abs(current_price - price_low)
    diff_mid = abs(current_price - price_mid)
    diff_high = abs(current_price - price_high)

    min_diff = min(diff_low, diff_mid, diff_high)

    if min_diff == diff_low:
        return price_low
    elif min_diff == diff_mid:
        return price_mid
    else:
        return price_high


def generate_entry_prices(min_price, max_price, num_orders=5):
    if num_orders <= 1:
        return [(min_price + max_price) / 2]

    if num_orders > 1:
        step = (max_price - min_price) / (num_orders - 1)
        return [min_price + i * step for i in range(num_orders)]
    return [min_price]


def get_trade_volume(total_volume, num_orders=5):
    if num_orders == 0: return 0.0
    lot_per_order = round(total_volume / num_orders, 2)
    return max(lot_per_order, 0.01)


# ========== CÁC HÀM PHÂN TÍCH TÍN HIỆU (PHIÊN BẢN ĐƠN GIẢN) ==========

def parse_signal(message):
    msg_lower = message.lower()
    global pending_signal_storage

    if any(keyword in msg_lower for keyword in KEYWORDS['CLOSE_HALF']): return {'action': 'CLOSE_HALF'}
    if any(keyword in msg_lower for keyword in KEYWORDS['CLOSE']): return {'action': 'CLOSE_ALL'}

    sltp_signal = parse_sl_tp_only(msg_lower)
    if sltp_signal:
        print("ℹ️  Quy tắc 0: Phát hiện tin nhắn chỉ có SL/TP.")
        return sltp_signal

    shorthand_pattern = r'(?:(buy|sell)\s+(?:limit\s+)?(?:v[àa]ng|gold|xau)|(?:v[àa]ng|gold|xau)\s+(buy|sell)(?:\s+limit)?)\s+(\d{1,2}(?:\.\d*)?)\s*[-–—]\s*(\d{1,2}(?:\.\d*)?)'
    shorthand_entry_match = re.search(shorthand_pattern, msg_lower)
    
    if shorthand_entry_match:
        print("ℹ️  Quy tắc 2: Đã phát hiện tín hiệu dạng viết tắt.")
        pending_signal_storage.clear()

        short_entry_1 = float(shorthand_entry_match.group(3))
        short_entry_2 = float(shorthand_entry_match.group(4))
        entry_min = min(short_entry_1, short_entry_2)
        entry_max = max(short_entry_1, short_entry_2)
        
        shorthand_sl_match = re.search(r'sl\s*:?\s*(\d{1,2}(?:\.\d*)?)', msg_lower)
        if shorthand_sl_match:
            short_sl = float(shorthand_sl_match.group(1))
            context_price = (entry_min + entry_max) / 2
            full_sl = get_nearest_price(context_price, short_sl)
            return {'action': 'NEW_ORDER', 'trade_action': 'BUY' if 'buy' in msg_lower or 'canh buy' in msg_lower else 'SELL', 'entry_min': entry_min, 'entry_max': entry_max, 'stop_loss': full_sl}
        else:
            return {'action': 'PENDING_ORDER', 'trade_action': 'BUY' if 'buy' in msg_lower or 'canh buy' in msg_lower else 'SELL', 'entry_min': entry_min, 'entry_max': entry_max, 'is_shorthand': True}

    entry_range_match = re.search(r'(\d{4,5}\.?\d*)\s*[-–—]\s*(\d{4,5}\.?\d*)', msg_lower)
    if entry_range_match:
        trade_action = 'UNKNOWN'
        if 'sell' in msg_lower: trade_action = 'SELL'
        elif 'buy' in msg_lower: trade_action = 'BUY'
        
        if trade_action != 'UNKNOWN':
            print("ℹ️  Quy tắc 3: Đã tìm thấy Entry dạng giá đầy đủ (KÈO MỚI).")
            pending_signal_storage.clear()

            entry_min = float(entry_range_match.group(1))
            entry_max = float(entry_range_match.group(2))
            
            sl_match = re.search(r'sl\s*:?\s*(\d{4,5}\.?\d*)', msg_lower)
            if sl_match:
                stop_loss = float(sl_match.group(1))
                return {'action': 'NEW_ORDER', 'trade_action': trade_action, 'entry_min': min(entry_min, entry_max), 'entry_max': max(entry_min, entry_max), 'stop_loss': stop_loss}
            else:
                return {'action': 'PENDING_ORDER', 'trade_action': trade_action, 'entry_min': min(entry_min, entry_max), 'entry_max': max(entry_min, entry_max), 'is_shorthand': False}
        else:
            print("ℹ️  Phát hiện vùng giá nhưng không có từ khóa giao dịch. Bỏ qua.")

    for re_entry_keyword in KEYWORDS['RE_ENTRY']:
        if re_entry_keyword in msg_lower:
            re_entry_type = 'ANY'
            if 'sell' in re_entry_keyword: re_entry_type = 'SELL'
            elif 'buy' in re_entry_keyword: re_entry_type = 'BUY'
            return {'action': 'RE_ENTRY', 're_entry_type': re_entry_type}

    for key in KEYWORDS['MOVE_SL_PRICE']:
        pattern = rf'{key}\s*(\d{{4,5}}\.?\d*)'
        move_sl_match = re.search(pattern, msg_lower)
        if move_sl_match: 
            return {'action': 'MOVE_SL_PRICE', 'sl_price': float(move_sl_match.group(1))}

    if any(keyword in msg_lower for keyword in (KEYWORDS['MOVE_SL_TO_ENTRY'] + ["+50", "+20", "+30", "dời sl"])): 
        return {'action': 'MOVE_SL_TO_ENTRY'}

    return None


# ========== HÀM THỰC THI TÍN HIỆU ==========

def execute_trade(signal):
    """Thực thi tín hiệu: vào lệnh, đóng lệnh hoặc dời SL qua kết nối ZeroMQ tới EA trong MT5."""
    action = signal.get('action')

    # Thiết lập kết nối ZeroMQ tới EA chạy trong Wine trên Ubuntu
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect(f"tcp://localhost:{EA_SOCKET_PORT}")

    if action == 'CLOSE_ALL':
        response = socket.send_string(json.dumps({"action": "CLOSE_ALL"}))
        result = socket.recv_string()
        return result, "success" in result.lower()

    elif action == 'CLOSE_HALF':
        response = socket.send_string(json.dumps({"action": "CLOSE_HALF"}))
        result = socket.recv_string()
        return result, "success" in result.lower()

    elif action == 'MOVE_SL_TO_ENTRY':
        response = socket.send_string(json.dumps({"action": "MOVE_SL_TO_ENTRY"}))
        result = socket.recv_string()
        return result, "success" in result.lower()

    elif action == 'MOVE_SL_PRICE':
        response = socket.send_string(json.dumps({
            "action": "MOVE_SL_PRICE",
            "sl_price": signal.get('sl_price')
        }))
        result = socket.recv_string()
        return result, "success" in result.lower()

    elif action == 'NEW_ORDER':
        trade_data = {
            "action": "NEW_ORDER",
            "trade_action": signal.get('trade_action'),
            "entry_min": signal.get('entry_min'),
            "entry_max": signal.get('entry_max'),
            "sl": signal.get('stop_loss', 0.0)
        }
        response = socket.send_string(json.dumps(trade_data))
        result = socket.recv_string()
        return result, "success" in result.lower()

    else:
        return "Lỗi: Không thể xử lý tín hiệu được gửi", False


# ========== MAIN APPLICATION ==========

async def async_connect_mt5():
    print("✅ Đang sử dụng kết nối ZeroMQ tới EA MT5 (không cần kết nối trực tiếp MT5).")
    return True

async def async_initialize_gold_symbol():
    print("✅ Bắt đầu: Không cần tự động tìm symbol Vàng.")
    return

async def async_execute_trade(signal):
    return await asyncio.to_thread(execute_trade, signal)

async def async_main():
    print("="*50)
    print("🤖 BMT TRADING BOT v2.0 - PHIÊN BẢN ĐƠN GIẢN")
    print("="*50)
    
    if not await async_connect_mt5():
        print("⚠️  Không thể kết nối MT5. Bot sẽ không thể giao dịch.")
    else:
        await async_initialize_gold_symbol()
    
    client = TelegramClient('session_trader', API_ID, API_HASH)

    processed_message_ids = deque(maxlen=500)
    global pending_signal_storage
    global last_executed_signal

    async with client:
        me = await client.get_me()
        bot_id = me.id
        print(f"✅ Bot đang chạy với tài khoản: {me.first_name} (ID: {bot_id})")
        print("✅ Đã kết nối Telegram. Đang chờ tín hiệu...")

        @client.on(events.NewMessage(chats=TARGET_GROUP))
        async def handler(event):
            global pending_signal_storage
            global last_executed_signal
            
            if event.sender_id == bot_id:
                return

            bot_icons = ('🤖', '🚀', '✅', '❌', '⚡', '⏹️', '🔄', '🕒', '📊', 'ℹ️', '⚠️', '📩')
            if event.message.message.strip().startswith(bot_icons):
                return
            
            if event.id in processed_message_ids:
                print(f"ℹ️  Tin nhắn ID {event.id} đã được xử lý trước đó. Bỏ qua.")
                return
            processed_message_ids.append(event.id)
                
            try:
                message_text = event.message.message
                print(f"\n📩 Nhận được tin nhắn mới: \"{message_text[:100]}...\"")
                
                try:
                    await event.delete()
                except Exception as e:
                    print(f"⚠️ Không thể xóa tin nhắn gốc: {e}")

                await send_copy_notification(f"📩 **Nhận tín hiệu mới:**\n`{message_text}`")
                
                signal = parse_signal(message_text)
                
                if not signal:
                    print("ℹ️  Không phải tín hiệu giao dịch hợp lệ. Bỏ qua.")
                    return

                print(f"🎯 Phân tích tín hiệu: {signal}")
                action = signal.get('action')

                if action == 'PENDING_ORDER':
                    pending_signal_storage.update(signal)
                    response_msg = (
                        "🤖 **GHI NHỚ LỆNH TẠM THỜI**\n"
                        "--------------------------\n"
                        f"🔹 Loại: **{signal['trade_action']}**\n"
                        f"🔹 Sản phẩm: **GOLD**\n"
                        f"🔹 Vùng vào: `{signal['entry_min']} - {signal['entry_max']}`\n"
                        "--------------------------\n"
                        "👉 *Vui lòng gửi SL/TP để hoàn tất lệnh.*"
                    )
                    await send_copy_notification(response_msg)
                    return

                elif action == 'RE_ENTRY':
                    if not last_executed_signal:
                        await send_copy_notification("🤖 **LỖI:** Không tìm thấy lệnh nào trước đó để vào lại.")
                        return
                    
                    re_entry_type = signal.get('re_entry_type', 'ANY')
                    if re_entry_type != 'ANY' and last_executed_signal.get('trade_action') != re_entry_type:
                        await send_copy_notification(f"🤖 **LỖI:** Lệnh cũ không phải là {re_entry_type}. Không thể vào lại.")
                        return
                    
                    full_signal = last_executed_signal.copy()
                    full_signal['action'] = 'NEW_ORDER'
                    
                    result_msg, success = await async_execute_trade(full_signal)
                    title = "🚀 **VÀO LẠI LỆNH (RE-ENTRY)**" if success else "❌ **LỖI VÀO LẠI LỆNH**"

                elif action == 'UPDATE_SLTP':
                    if not pending_signal_storage:
                        response_msg = "🤖 **LỖI:** Không có lệnh nào đang chờ để cập nhật SL/TP."
                        await send_copy_notification(response_msg)
                        return

                    full_signal = pending_signal_storage.copy()
                    
                    new_sl = signal.get('stop_loss')
                    if new_sl is not None:
                        if full_signal.get('is_shorthand', False) and new_sl < 100:
                            context_price = (full_signal['entry_min'] + full_signal['entry_max']) / 2
                            full_sl = get_nearest_price(context_price, new_sl)
                        else:
                            full_sl = new_sl
                        
                        if (full_signal['trade_action'] == 'SELL' and full_sl <= full_signal['entry_max']) or \
                           (full_signal['trade_action'] == 'BUY' and full_sl >= full_signal['entry_min']):
                            err_msg = f"🤖 **LỖI LOGIC:**\nSL `{full_sl}` không hợp lệ so với vùng vào lệnh. Lệnh chờ đã bị hủy."
                            await send_copy_notification(err_msg)
                            pending_signal_storage.clear()
                            return

                        full_signal['stop_loss'] = full_sl
                    else:
                        await send_copy_notification("🤖 **LỖI:** Lệnh cần phải có Stop Loss. Lệnh chờ đã bị hủy.")
                        pending_signal_storage.clear()
                        return

                    if signal.get('take_profit'):
                        full_signal['take_profit'] = signal.get('take_profit')
                    
                    full_signal['action'] = 'NEW_ORDER'
                    pending_signal_storage.clear()

                    result_msg, success = await async_execute_trade(full_signal)
                    if success:
                        last_executed_signal = full_signal.copy()
                    title = "✅ **KÍCH HOẠT LỆNH GHÉP THÀNH CÔNG**" if success else "❌ **LỖI THỰC THI LỆNH GHÉP**"
                    
                else:
                    result_msg, success = await async_execute_trade(signal)
                    
                    if success and action in ['NEW_ORDER']:
                        last_executed_signal = signal.copy()

                    if action == 'UPDATE_ORDER':
                        title = "🔄 **CẬP NHẬT LỆNH**" if success else "❌ **LỖI CẬP NHẬT**"
                    elif action == 'CLOSE_ALL':
                        title = "⏹️ **ĐÓNG TOÀN BỘ LỆNH**" if success else "❌ **LỖI ĐÓNG LỆNH**"
                    else:
                        title = "⚡ **THỰC THI LỆNH MỚI**" if success else "❌ **LỖI THỰC THI**"

                full_response_msg = (
                    f"{title}\n"
                    "--------------------------\n"
                    f"{result_msg}\n"
                    "--------------------------\n"
                    "🕒 *Thời gian:* " + time.strftime("%H:%M:%S")
                )
                
                await send_copy_notification(full_response_msg)

            except Exception as e:
                print(f"🔥🔥 LỖI NGHIÊM TRỌNG KHI XỬ LÝ TIN NHẮN: {e}")
                print(f"   Tin nhắn gây lỗi: {event.message.message[:200]}")
                error_reply_msg = f"🤖 **Bot gặp lỗi:**\nĐã xảy ra lỗi khi xử lý tin nhắn của bạn. Chi tiết: `{e}`"
                
                await send_copy_notification(error_reply_msg)
        
        await client.run_until_disconnected()

if __name__ == "__main__":
    while True:
        try:
            asyncio.run(async_main())
        except KeyboardInterrupt:
            print("\n👋 Đã dừng bot.")
            break
        except Exception as e:
            print(f"\n🔥🔥 LỖI CRITICAL - BOT SẼ KHỞI ĐỘNG LẠI SAU 15 GIÂY 🔥🔥")
            print(f"Lỗi: {e}")
            time.sleep(15)