import os

def switch_to_demo():
    """Chuyển sang tài khoản DEMO"""
    env_content = """# Telegram API
API_ID=36198955
API_HASH=c9b0939e084f14246aa5c00e804a0f0a

# MT5 DEMO Account
MT5_LOGIN=433044560
MT5_PASSWORD=T@i112233
MT5_SERVER=Exness-MT5Trial7
"""
    
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print("✅ Đã chuyển sang tài khoản DEMO")

def switch_to_real():
    """Chuyển sang tài khoản REAL"""
    env_content = """# Telegram API
API_ID=36198955
API_HASH=c9b0939e084f14246aa5c00e804a0f0a

# MT5 REAL Account
MT5_LOGIN=263265653
MT5_PASSWORD=T@i112233
MT5_SERVER=Exness-MT5Real37
"""
    
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print("✅ Đã chuyển sang tài khoản REAL")

# Menu
print("🤖 CHUYỂN ĐỔI TÀI KHOẢN")
print("1. DEMO Account")
print("2. REAL Account")
choice = input("Chọn (1/2): ")

if choice == "1":
    switch_to_demo()
elif choice == "2":
    switch_to_real()
else:
    print("❌ Lựa chọn không hợp lệ")