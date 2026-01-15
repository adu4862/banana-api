I will modify `lovart_routes.py` to automatically extract and download reference images from the prompt when they are not explicitly provided in the request payload.

**Step 1: Create Helper Functions in `lovart_routes.py`**
I will add a new helper function `_process_prompt_for_images(prompt)` that:
1.  Uses regular expressions to find image URLs in the prompt (handling both backticked `` `url` `` and plain URLs).
2.  Downloads these images to temporary files.
3.  Removes the URLs from the prompt string.
4.  Returns the cleaned prompt and the list of local file paths.

**Step 2: Update `api_generate_image` Route**
In the `api_generate_image` function:
1.  Check if `start_frame_image_path`, `start_frame_image_base64`, and `image_assets` are all empty.
2.  If empty, call `_process_prompt_for_images` with the received `prompt`.
3.  Update the `prompt` variable with the cleaned version.
4.  Append the downloaded file paths to `final_image_paths`.

**Step 3: Update `api_generate_image_openai` Route**
Similarly, in the `api_generate_image_openai` function:
1.  Check if `image_assets` and `start_frame_image_base64` are empty.
2.  If empty, call `_process_prompt_for_images`.
3.  Update the `prompt` and `final_image_paths`.

**Step 4: Verify `lovart_login.py` Capability**
I have reviewed `lovart_login.py` and confirmed that `run_generate_image_on_page` already supports uploading multiple images via `file_chooser.set_files(all_images)`. No changes are needed in `lovart_login.py` as it will correctly handle the list of files passed from the routes.

**Implementation Details:**
-   **Regex**: Will support standard `http/https` URLs, optionally wrapped in backticks or whitespace-separated.
-   **Download**: Will use `requests` with a timeout and save to `tempfile`.
-   **Cleanup**: The existing `finally` blocks in the routes already handle cleaning up `temp_file_paths`, so I just need to ensure the new paths are added to this list.
