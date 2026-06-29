import MetaTrader5 as mt5
from dotenv import load_dotenv
import os

load_dotenv()

def find_symbol():
    print("🔍 Đang tìm kiếm tên biểu tượng (Symbol) của Vàng...")
    print("=" * 50)
    
    # Kết nối MT5
    mt5_path = "C:/Program Files/MetaTrader 5 EXNESS/terminal64.exe"
    if not mt5.initialize(path=mt5_path):
        print(f"❌ Không thể khởi tạo MT5 với đường dẫn: {mt5_path}")
        return

    try:
        login_id = int(os.getenv('MT5_LOGIN'))
        password = os.getenv('MT5_PASSWORD')
        server = os.getenv('MT5_SERVER')
    except (TypeError, ValueError):
        print("❌ Lỗi: Vui lòng kiểm tra lại các biến MT5 trong file .env")
        return
        
    if not mt5.login(login=login_id, password=password, server=server):
        print(f"❌ Đăng nhập thất bại: {mt5.last_error()}")
        mt5.shutdown()
        return
    
    print("✅ Kết nối MT5 thành công. Đang lấy danh sách symbols...")
    
    # Lấy tất cả symbols
    symbols = mt5.symbols_get()
    
    gold_symbols = []
    if symbols:
        print(f"\n--- Tìm thấy {len(symbols)} symbols. Đang lọc 'GOLD' hoặc 'XAU' ---")
        for s in symbols:
            if "GOLD" in s.name.upper() or "XAU" in s.name.upper():
                gold_symbols.append(s.name)
    else:
        print("❌ Không thể lấy danh sách symbols.")
        
    mt5.shutdown()
    
    if gold_symbols:
        print("\n✅ Các biểu tượng Vàng có thể có trên sàn của bạn:")
        for i, name in enumerate(gold_symbols, 1):
            print(f"   {i}. {name}")
        
        print("\n💡 Vui lòng kiểm tra và sử dụng một trong những tên này trong code.")
        print(f"   Tên có khả năng cao nhất là: '{gold_symbols[0]}'")
    else:
        print("\n❌ Không tìm thấy biểu tượng nào liên quan đến Vàng!")

if __name__ == "__main__":
    find_symbol()
