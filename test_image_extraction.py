import requests
import json
import time

url = "http://127.0.0.1:5005/v1/images/generations"

payload = {
    "model": "banana pro",
    "prompt": " `http://cdn2.manfanfan.com/agent_images/char_3_1768410675.png` `http://cdn2.manfanfan.com/agent_images/ac2d686e-d4bf-431a-98e3-3e7f8363ed43.png` 参考图的画风 生成一只赛博朋克风格的猫",
    "size": "1024x1024"
}

headers = {
    "Content-Type": "application/json"
}

print(f"Sending request to {url}...")
print(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")

try:
    start_time = time.time()
    response = requests.post(url, json=payload, headers=headers, timeout=1200) # Long timeout for generation
    end_time = time.time()
    
    print(f"Response Status Code: {response.status_code}")
    print(f"Time taken: {end_time - start_time:.2f} seconds")
    
    try:
        data = response.json()
        print("Response Data:")
        print(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"Failed to parse JSON response: {response.text}")

except Exception as e:
    print(f"Request failed: {e}")
