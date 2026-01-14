import base64
import requests
import json
import os

# 配置
API_URL = "http://127.0.0.1:5005/v1/images/generations"
IMAGE_PATH = r"H:\BaiduNetdiskDownload\Shuke1130\Shuke\backend\项目\20260112_145033_11111\fusions\fusion_1.jpg"
PROMPT = "参考图片 画风 生成 [10]. 【近景】。荒野中。2个人, (@江萌)(女性, 20岁)，身穿一件浅蓝色衣衫; (@老夫人)(女性, 60岁)，身穿一件棕褐色衣衫。前者蹲在地上，一手握着后者的手腕，另一只手拿着木钗挑起一只红头黑触角的长虫，眼神严肃认真地看着后者，虫子在木钗尖端扭动，后者看着虫子瞪大眼睛神情惊恐。阴天散射光。微动效果, 固定镜头, 平视, 越肩镜头"

def get_image_base64(path):
    """读取图片并转换为Base64字符串"""
    if not os.path.exists(path):
        print(f"错误: 图片文件不存在: {path}")
        # 如果文件不存在，为了演示，我们可以创建一个假的base64或者直接报错
        # 这里为了测试流程，如果文件不存在，我们就不传图片
        return None
        
    with open(path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        # 添加前缀
        ext = os.path.splitext(path)[1][1:].lower()
        if ext == 'jpg': ext = 'jpeg'
        return f"data:image/{ext};base64,{encoded_string}"

def test_generate_image():
    print("准备调用生图接口...")
    
    # 准备 Payload
    payload = {
        "model": "lovart",
        "prompt": PROMPT,
        "size": "1024x1024" # 对应 1:1，你可以根据需要修改
    }
    
    # 读取图片并添加到 Payload
    base64_img = get_image_base64(IMAGE_PATH)
    if base64_img:
        print(f"图片已转换为 Base64 (长度: {len(base64_img)})")
        # 使用 image_assets 数组 (推荐方式)
        payload["image_assets"] = [base64_img]
    else:
        print("警告: 未找到参考图，将仅使用 Prompt 生成")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer sk-test-key"
    }
    
    print(f"发送请求到: {API_URL}")
    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=600) # 超时设置长一点
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n生成成功!")
            if "data" in result and len(result["data"]) > 0:
                print(f"图片URL: {result['data'][0]['url']}")
            else:
                print("返回数据格式异常:", json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("\n生成失败!")
            print("错误信息:", response.text)
            
    except Exception as e:
        print(f"\n请求发生异常: {e}")

if __name__ == "__main__":
    test_generate_image()
