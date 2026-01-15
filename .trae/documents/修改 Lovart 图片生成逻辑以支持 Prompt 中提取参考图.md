# 修改 Lovart 图片生成逻辑以支持 Prompt 中提取参考图

## 1. 修改 `lovart_routes.py`
### 目标：从 Prompt 中解析并下载参考图
- 在 `api_generate_image_openai` 接口中增加逻辑。
- 当未显式提供参考图 (`image_assets` 或 `start_frame_image_base64` 为空) 时：
    - 使用正则表达式从 `prompt` 中提取所有 URL (例如 `https://...`)。
    - 支持处理被反引号 (`) 包裹的 URL。
    - 使用 `requests` 下载这些图片到临时文件。
    - 将临时文件路径加入 `final_image_paths` 列表。
    - 清理 `prompt` 中的 URL 文本，只保留描述性文字，避免 URL 干扰生成模型。

## 2. 优化 `lovart_login.py`
### 目标：确保图片上传成功
- 审查 `run_generate_image_on_page` 中的上传逻辑。
- 确认 `file_chooser.set_files(all_images)` 被正确调用。
- **增强逻辑**：在上传后添加检查步骤，等待界面上出现上传图片的缩略图或加载完成的标志，以防止在图片未上传完成时就开始生成。

## 3. 验证
- 模拟请求，在 prompt 中包含图片 URL，验证是否能成功触发上传并生成图片。