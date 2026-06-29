# Cấu hình từ khóa
KEYWORDS = {
    # Từ khóa vào lệnh
    'ENTRY': ['buy', 'sell', 'buy limit', 'sell stop', 'canh buy', 'canh sell'],
    
    # Từ khóa chốt lệnh toàn bộ
    'CLOSE': ['chốt', 'lụm', 'chốt toàn bộ', 'close all', 'done kèo', 'chốt hết', 'chốt luôn', 'hủy'],
    
    # Từ khóa chốt một phần lệnh
    'CLOSE_HALF': ['chốt 1/2', 'chốt 1 nửa', 'chốt dần', '1/2', 'chốt một phần', 'chốt 1 phần', 'chốt bớt'],
    
    # Từ khóa dời SL về giá cụ thể
    'MOVE_SL_PRICE': ['dời sl về', 'move sl to', 'dời sl lên'],

    # Từ khóa dời SL về entry
    'MOVE_SL_TO_ENTRY': ['dời sl về entry', 'sl về be', 'sl entry'],

    # Từ khóa vào lại lệnh cũ (Re-entry)
    'RE_ENTRY': ['cứ plan này gd', 'sell lại', 'buy lại', 'vào lại', 'giao dịch lại', 're-entry', 're-buy', 're-sell', 'sell tiếp', 'buy tiếp'],
    
    # Từ khóa bỏ qua (ưu tiên thấp hơn)
    'IGNORE': ['thảo luận', 'bình luận', 'quan điểm', 'phân tích', 'ad']
}

# Cấu hình giao dịch theo logic mới
TRADING_CONFIG = {
    # Tổng khối lượng cho mỗi tín hiệu
    'TOTAL_VOLUME': 0.75, 
    
    # Số lệnh con sẽ chia ra từ 1 tín hiệu
    'NUM_ORDERS': 5,
    
    # Số lệnh con đầu tiên sẽ có TP
    'NUM_ORDERS_WITH_TP': 3,
}

# Cấu hình bot thông báo sao chép
NOTIFICATION_BOT_TOKEN = '8462808034:AAHTQLj6P9LfbbToYb1GshB18u6q9nirAGc'
NOTIFICATION_CHAT_ID = '-1003895937153' # <-- BẠN CẦN THAY THẾ ID NÀY!