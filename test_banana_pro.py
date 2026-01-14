import requests
import base64
import json
import os
import time

# ================= 配置区域 =================
# 代理地址 (New-API / One-API 地址)
BASE_URL = "http://114.66.28.185:51878"
API_KEY = "WOnY467peOTkVeKeQTNQk7oJToht67pXKubFIeynr0Wse7Ll"

# 本地图片路径
IMAGE_PATH = r"H:\BaiduNetdiskDownload\Shuke1130\Shuke\backend\项目\20260112_145033_11111\fusions\fusion_1.jpg"

# Prompt
PROMPT = "参考图片 画风 生成 [10]. 【近景】。荒野中。2个人, (@江萌)(女性, 20岁)，身穿一件浅蓝色衣衫; (@老夫人)(女性, 60岁)，身穿一件棕褐色衣衫。前者蹲在地上，一手握着后者的手腕，另一只手拿着木钗挑起一只红头黑触角的长虫，眼神严肃认真地看着后者，虫子在木钗尖端扭动，后者看着虫子瞪大眼睛神情惊恐。阴天散射光。微动效果, 固定镜头, 平视, 越肩镜头"

# 模型名称
MODEL = "banana pro"
# ===========================================

def get_image_base64(path):
    """读取图片并转换为Base64字符串"""
    if not os.path.exists(path):
        print(f"错误: 图片文件不存在: {path}")
        return None
        
    try:
        with open(path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            # 获取扩展名
            ext = os.path.splitext(path)[1][1:].lower()
            if ext == 'jpg': ext = 'jpeg'
            if not ext: ext = 'jpeg'
            
            return f"data:image/{ext};base64,{encoded_string}"
    except Exception as e:
        print(f"读取图片异常: {e}")
        return None

def test_generate_image():
    print(f"{'='*50}")
    print(f"Testing Model: {MODEL}")
    print(f"Target Endpoint: {BASE_URL}/v1/images/generations")
    print(f"{'='*50}")

    # 1. 编码图片
    print("Step 1: Encoding Reference Image...")
    base64_image = get_image_base64(IMAGE_PATH)
    
    image_assets_list = []
    if base64_image:
        image_assets_list.append(base64_image)
        print(f"[SUCCESS] Image encoded. Length: {len(base64_image)} chars")
    else:
        print("警告: 未找到参考图或读取失败，将仅使用 Prompt 生成")

    # 2. 准备 Payload
    print("\nStep 2: Preparing Request Payload...")
    
    # 构造标准 OpenAI Payload
    payload = {
        "model": MODEL,
        "prompt": PROMPT,
        # 你的后端默认逻辑：未命中的分辨率都会作为 1:1 处理
        # 如果需要 16:9，请改为 "1792x1024"
        # 如果需要 9:16，请改为 "1024x1792"
        "size": "1024x1024", 
    }

    # 【关键修改】利用 user 字段透传数据
    # new-api 会过滤掉 payload 里的自定义字段（如 image_assets），但会保留 user 字段。
    # 你的后端 lovart_routes.py (lines 646-660) 包含了解析 user 字段 JSON 的逻辑。
    if image_assets_list:
        # 将自定义参数封装到字典中
        bypass_data = {
            "image_assets": image_assets_list,
            # 你也可以在这里传 start_frame_image_base64 等其他参数
        }
        # 序列化为字符串放入 user 字段
        payload["user"] = json.dumps(bypass_data)
        print("Strategy: Wrapping 'image_assets' inside 'user' field to bypass API proxy filtering.")
    else:
        payload["user"] = "test-user-id"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    # 3. 发送请求
    url = f"{BASE_URL}/v1/images/generations"
    print(f"\nStep 3: Sending POST request to {url}...")
    print("Waiting for response (this may take 30-60 seconds)...")
    
    start_time = time.time()
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=600)
        elapsed = time.time() - start_time
        
        print(f"\n[RESPONSE] Status Code: {response.status_code} (Time: {elapsed:.2f}s)")
        
        if response.status_code == 200:
            result = response.json()
            print("\n生成成功!")
            
            # 打印结果（截断过长的 URL 以便查看）
            print_result = result.copy()
            if "data" in print_result:
                for item in print_result["data"]:
                    if "url" in item and len(item["url"]) > 100:
                        item["url"] = item["url"][:50] + "..." + item["url"][-20:]
            
            print(json.dumps(print_result, indent=2, ensure_ascii=False))
            
            # 打印完整 URL
            if "data" in result and len(result["data"]) > 0:
                print(f"\nFull Image URL: {result['data'][0]['url']}")
            else:
                print("返回数据格式异常 (No data field or empty).")
        else:
            print("\n生成失败!")
            print("错误信息:", response.text)
            
    except Exception as e:
        print(f"\n请求发生异常: {e}")

if __name__ == "__main__":
    test_generate_image()