# Lovart 生成图片接口文档

本文档详细描述了 Lovart 后端服务中生成图片的接口使用方法。

## 接口概述

该接口用于自动化调用 Lovart 网页版进行 AI 图片生成。支持上传参考图、设置分辨率和宽高比。

- **URL**: `/api/lovart/generate_image`
- **Method**: `POST`
- **Content-Type**: `application/json`

---

## 请求参数 (Request)

Body 为 JSON 格式，支持以下字段：

| 字段名 | 类型 | 必填 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `prompt` | string | **是** | - | 图片生成的提示词 (Prompt)。 |
| `start_frame_image_base64` | string | 否 | `""` | **参考图 Base64 编码**。<br>支持带或不带 `data:image/xxx;base64,` 前缀。<br>**推荐使用此方式**上传参考图，适用于跨服务器调用。 |
| `start_frame_image_path` | string | 否 | `""` | **参考图本地路径** (仅限本地调试)。<br>必须是服务器上的绝对路径。<br>如果同时提供了 Base64，则优先使用 Base64。 |
| `resolution` | string | 否 | `"2K"` | 图片分辨率。<br>可选值：`"1K"`, `"2K"`, `"4K"`。 |
| `ratio` | string | 否 | `"16:9"` | 图片宽高比。<br>可选值：`"16:9"`, `"1:1"`, `"9:16"`, `"4:3"`, `"3:4"` 等 Lovart 支持的比例。 |

### 请求示例

**仅使用提示词：**
```json
{
    "prompt": "一个赛博朋克风格的未来城市，霓虹灯，雨夜"
}
```

**使用参考图 (Base64) 并指定分辨率和比例：**
```json
{
    "prompt": "将这张草图渲染成真实照片，电影质感",
    "start_frame_image_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD...",
    "resolution": "4K",
    "ratio": "16:9"
}
```

**使用参考图 (本地路径 - 仅限调试)：**
```json
{
    "prompt": "...",
    "start_frame_image_path": "C:\\Users\\Admin\\Desktop\\sketch.jpg"
}
```

---

## 响应结果 (Response)

接口返回 JSON 格式的数据。

### 成功响应

- **Status Code**: `200 OK`

```json
{
    "status": "success",
    "message": "图片生成完成",
    "data": {
        "points": 120,
        "start_frame_image_path": "C:\\Users\\Admin\\Desktop\\sketch.jpg",
        "image_url": "https://cdn.lovart.ai/artifacts/generator/2024/01/01/xxx.png"
    }
}
```

**字段说明：**
- `status`: 固定为 `"success"`。
- `message`: 描述信息。
- `data`:
    - `points`: (integer) 任务完成后的剩余积分估算（可能为空或不准确，取决于页面解析情况）。
    - `start_frame_image_path`: (string) 回传的参考图路径。
    - `image_url`: (string) **生成的图片下载链接**。

### 失败响应

- **Status Code**: `400 Bad Request` (参数错误) 或 `500 Internal Server Error` (执行错误)

```json
{
    "status": "error",
    "message": "缺少参数: prompt",
    "data": {}
}
```

或

```json
{
    "status": "error",
    "message": "系统繁忙，请稍后再试",
    "data": {}
}
```

**常见错误信息：**
- `缺少参数: prompt`: 未提供提示词。
- `没有可用的浏览器会话，请先调用/register登陆`: 后端尚未初始化浏览器，请先调用 `/api/lovart/register` 接口。
- `自动登陆超时`: 浏览器启动或登录失败。
- `重试多次失败 (积分不足或系统繁忙)`: 可能是账号积分耗尽或页面加载异常。

---

## 注意事项

1.  **参考图路径**: `start_frame_image_path` 必须是**服务器本地文件系统**上的有效绝对路径。如果是远程客户端调用，需要先将图片上传到服务器，或者自行修改后端代码支持 URL/Base64 上传。
2.  **并发限制**: 默认配置下，后端通过 `LOVART_POOL_SIZE` 环境变量控制浏览器实例数量（默认为 3）。如果请求过多，后续请求会排队或超时。
3.  **超时时间**: 整个生成过程默认超时时间较长（约 3-5 分钟），请确保客户端的请求超时设置足够大。
4.  **分辨率与比例**: 参数值必须与 Lovart 网页 UI 上显示的文本完全匹配（例如 `"2K"`, `"16:9"`），否则可能无法选中。
