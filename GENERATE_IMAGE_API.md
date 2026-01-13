# Lovart 生成图片接口文档 (OpenAI 兼容版)

本文档描述了经过改造后的 Lovart 图片生成接口。**该接口已完全兼容 OpenAI DALL-E 接口标准**，可直接接入 New API (One API)、LangChain 等生态工具。

## 接口概述

- **URL**: `/v1/images/generations`
- **Method**: `POST`
- **Content-Type**: `application/json`
- **Authorization**: `Bearer <Your-API-Key>` (后端目前暂未校验 Key，可传任意值)

---

## 请求参数 (Request)

Body 为 JSON 格式，完全遵循 OpenAI 标准：

| 字段名 | 类型 | 必填 | 说明 | 内部映射逻辑 (后端实现参考) |
| :--- | :--- | :--- | :--- | :--- |
| `model` | string | 否 | 模型名称 (如 `lovart`, `dall-e-3`)。 | 可忽略，或用于区分不同底层模型。 |
| `prompt` | string | **是** | 图片生成的提示词。 | 对应原 `prompt`。 |
| `size` | string | 否 | 图片尺寸。 | **关键映射**: <br> `1024x1024` -> `ratio="1:1"` <br> `1792x1024` -> `ratio="16:9"` <br> `1024x1792` -> `ratio="9:16"` <br> `1024x768` -> `ratio="4:3"` <br> `768x1024` -> `ratio="3:4"` <br> *默认分辨率均为 2K* |
| `n` | integer | 否 | 生成数量 (默认 1)。 | 建议仅支持 1。 |
| `response_format`| string | 否 | 返回格式。 | 仅支持 `url`。 |
| `start_frame_image_base64` | string | 否 | **(扩展参数)** 参考图 Base64 编码。 | 支持上传参考图。 |

### 请求示例

```json
{
  "model": "lovart",
  "prompt": "一个赛博朋克风格的未来城市，霓虹灯，雨夜",
  "size": "1792x1024"
}
```

**带参考图的示例 (扩展字段):**
```json
{
  "model": "lovart",
  "prompt": "将草图渲染成真实照片",
  "start_frame_image_base64": "data:image/png;base64,iVBORw0KGgo..."
}
```

---

## 响应结果 (Response)

严格遵循 OpenAI 格式。

### 成功响应

- **Status Code**: `200 OK`

```json
{
  "created": 1705300000,
  "data": [
    {
      "url": "https://cdn.lovart.ai/artifacts/generator/2024/01/01/xxx.png"
    }
  ]
}
```

### 失败响应

- **Status Code**: `400` 或 `500`

```json
{
  "error": {
    "code": "invalid_parameter",
    "message": "Missing required parameters: prompt",
    "type": "invalid_request_error",
    "param": null
  }
}
```

---

## 接入 New API 配置指南

后端接口按上述文档改造完成后，在 New API (One API) 网页端配置如下：

1.  **类型**: 选择 **OpenAI** (不要选自定义)。
2.  **名称**: `Lovart` (任意)。
3.  **代理地址 (Base URL)**: 填写您的 Lovart 后端服务地址，**末尾不要带 `/v1`**。
    *   例如服务在 `http://192.168.1.100:5000`
    *   则此处填 `http://192.168.1.100:5000`
4.  **密钥 (Key)**: 填写任意值 (例如 `sk-any-key`)。
5.  **自定义模型**: 填入 `lovart` (或者您希望客户端调用的模型名)。

这样配置后，New API 会自动将请求发往 `http://192.168.1.100:5000/v1/images/generations`，完美兼容。
