import requests
import time
import random
import string
import platform

# ================= 配置区域 =================

# 1. 代理配置 (v2rayN)
PROXY_HOST = "192.168.1.159"
PROXY_PORT = 7897 

# 构造 requests 专用的代理字典
proxies = {
    'http': f'socks5://{PROXY_HOST}:{PROXY_PORT}',
    'https': f'socks5://{PROXY_HOST}:{PROXY_PORT}'
}

# 2. Mailu 官方 API 配置
# 注意：API 地址建议固定为主服务器地址，因为它是管理入口
API_TOKEN = 'M9K175RXZDWJ0K3C7Y5R2W9FRH29SN0G'
API_URL = 'https://mail.mx892.asia/api/v1' 

# 3. 自定义 Bridge API 配置 (用于读取邮件)
BRIDGE_URL = 'http://130.94.41.184:5000/get_latest_email'
BRIDGE_SECRET = 'MySuperSecretKey123!'

# 4. 域名池配置 (在此处添加所有已在 Mailu 后台添加过的域名)
AVAILABLE_DOMAINS = [
    "mx9922x.site",
    "kp4829m.space",
    "mx892.asia", 
    "mx892.fun", 
    "mx892.icu", 
    "mx892.online", 
    "mx892.site", 
    "mx892.space", 
    "mx892.website", 
    "mx9922x.site", 
    "kp4829m.space",
    "dax452x.store",
    "dixk297jx.site",
    "ij7hx6d.christmas",
    "sgc585x2.online",
    "ij7hx6d.lat",
    "ij7hx6d.mom",
    "ij7hx6d.pics",
    "ij7hx6d.surf",
    "kp4829m.space",
    # "new-domain.com"
]

# ===========================================

def generate_random_user():
    """生成随机的邮箱账号和密码"""
    # 随机选择一个域名
    selected_domain = random.choice(AVAILABLE_DOMAINS)
    
    # 生成随机用户名
    random_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    email = f'user_{random_id}@{selected_domain}'
    
    # 密码固定或随机均可
    password = 'StrongPassword123!'
    
    return email, password

def create_user(email, password):
    """使用 Mailu 官方 API 创建用户"""
    headers = {
        'Authorization': f'Bearer {API_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'email': email,
        'raw_password': password,
        'comment': 'Python Auto Create',
        'quota': 1000000000,
        'enabled': True
    }

    print(f"[-] [注册] 正在创建用户: {email}")
    
    try:
        # 发送请求 (带代理)
        # 注意：这里是向主服务器 API 发送指令，请求在子域名下创建用户
        response = requests.post(f'{API_URL}/user', json=payload, headers=headers, proxies=proxies, timeout=15)
        
        if response.status_code == 200:
            print(f"[+] [注册] 用户创建成功！")
            return True
        elif response.status_code == 409:
            print(f"[!] [注册] 用户已存在。")
            return True
        else:
            print(f"[x] [注册] 失败: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"[x] [注册] 连接错误: {e}")
        return False

def check_email_via_bridge(email, password):
    """调用自定义 Bridge API 获取邮件"""
    
    payload = {
        "api_secret": BRIDGE_SECRET,
        "email": email,      # 传入刚才随机生成的完整邮箱
        "password": password
    }
    
    print(f"[-] [收取] 正在检测邮箱 ({email})...")
    
    resp = None
    try:
        # 尝试 1: 优先走代理
        resp = requests.post(BRIDGE_URL, json=payload,  timeout=10)
    except requests.exceptions.RequestException:
        # 尝试 2: 代理失败则直连 (可能是代理不支持该端口或目标拒绝代理 IP)
        try:
            resp = requests.post(BRIDGE_URL, json=payload, proxies=None, timeout=10)
        except Exception as e_direct:
            print(f"[x] [收取] 连接失败 (代理和直连均不可达): {e_direct}")
            return

    try:
        # 解析结果
        if resp.status_code != 200:
            print(f"[x] [收取] 服务器报错: {resp.status_code} - {resp.text}")
            return

        data = resp.json()
        
        if data.get("status") == "success":
            print("\n" + "="*40)
            print(f"★ 收到新邮件！")
            print(f"接收邮箱: {email}")
            print(f"主题: {data.get('subject')}")
            print(f"发件人: {data.get('sender')}")
            print("内容：")
            print(data.get("content"))
            print("="*40 + "\n")
        elif data.get("status") == "empty":
            # 简化输出，避免刷屏
            pass 
        else:
            print(f"[!] [收取] 未知状态: {data}")
            
    except Exception as e:
        print(f"[x] [收取] 出错: {e}")

# ================= 主程序 =================
if __name__ == "__main__":
    # 1. 生成随机身份
    current_email, current_password = generate_random_user()
    
    print(f"--- 本次测试目标: {current_email} ---")

    # 2. 先创建用户
    if create_user(current_email, current_password):
        print(f"[-] 账号 {current_email} 准备就绪。")
        print(f"[-] 请现在给这个邮箱发一封测试邮件！")
        print("[-] 开始轮询 (每 5 秒一次)...")
        
        # 3. 循环读取
        while True:
            check_email_via_bridge(current_email, current_password)
            time.sleep(5)
