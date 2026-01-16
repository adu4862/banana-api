# -*- coding: utf-8 -*-
"""
Lovart Login Automation using Camoufox & Playwright
"""

import asyncio
import time
import re
import requests
import threading
import random
import string
from threading import Thread, Event, Lock
from colorama import Fore, Style, init

# Patch browserforge to prevent repeated downloads/checks on startup
# try:
#     import browserforge.download
#     # Disable the download check by mocking the function
#     browserforge.download.DownloadIfNotExists = lambda **kwargs: None
# except ImportError:
#     pass

# from camoufox.async_api import AsyncCamoufox
from playwright.async_api import Page, expect, async_playwright

import os
import sys
import uuid
import requests
from qiniu import Auth, put_data, put_file

# BitBrowser Configuration
BITBROWSER_API_URL = "http://127.0.0.1:54345"
# Configure your Browser IDs here. Ensure you have enough IDs for the pool size.
BITBROWSER_IDS = [
    "browser_id_1", "browser_id_2", "browser_id_3", 
    "browser_id_4", "browser_id_5", "browser_id_6"
]

def open_bitbrowser(browser_id):
    """
    Start BitBrowser window via API and get WebSocket address
    """
    url = f"{BITBROWSER_API_URL}/browser/open"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "id": browser_id,
        "args": [],
        "loadExtensions": False,
        "extractIp": False
    }

    try:
        print(f"Opening BitBrowser ID: {browser_id}")
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        data = resp.json()
        
        if data['success']:
            ws_endpoint = data['data']['ws']
            print(f"✅ Browser started, WS: {ws_endpoint}")
            return ws_endpoint
        else:
            print(f"❌ Failed to start browser: {data.get('msg')}")
            return None
    except Exception as e:
        print(f"❌ API Exception: {e}")
        return None

def close_bitbrowser_api(browser_id):
    """
    Close BitBrowser window via API
    """
    url = f"{BITBROWSER_API_URL}/browser/close"
    payload = {"id": browser_id}
    try:
        requests.post(url, json=payload, timeout=10)
        print(f"✅ Browser {browser_id} closed via API")
    except Exception as e:
        print(f"Close exception: {e}")

def delete_bitbrowser_window(browser_id):
    """
    Delete BitBrowser window via API
    """
    url = f"{BITBROWSER_API_URL}/browser/delete"
    payload = {"id": browser_id}
    try:
        print(f"🗑️ Deleting BitBrowser window: {browser_id}")
        resp = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=10)
        data = resp.json()
        if data.get('success'):
             print(f"✅ Browser {browser_id} deleted successfully")
        else:
             print(f"❌ Failed to delete browser: {data.get('msg')}")
    except Exception as e:
        print(f"❌ Delete exception: {e}")

def create_bitbrowser_window(name_prefix="Lovart-Auto", proxy_info=None):
    """
    Create a new BitBrowser window via API and return its ID.
    """
    url = f"{BITBROWSER_API_URL}/browser/update"
    headers = {'Content-Type': 'application/json'}
    
    # Basic configuration for a new window
    payload = {
        "platform": "Other", # Generic platform
        "name": f"{name_prefix}-{int(time.time())}",
        "remark": "Created by Lovart Script",
        "url": "", # Default URL
        "proxyMethod": 2, # 2 = Custom Proxy, 3 = Extract IP
        "proxyType": "noproxy", # Default to no proxy, can be updated if proxy_info provided
        "browserFingerPrint": {
            "coreVersion": "124" # Suggest a recent version, or leave empty/remove to let it pick default
        } 
    }
    
    # If we want random fingerprint, passing empty object or specific fields might be needed.
    # BitBrowser docs say: "When creating a profile with a random fingerprint object, simply pass an empty object {}"
    payload["browserFingerPrint"] = {}

    if proxy_info:
        # Example proxy_info: {"type": "socks5", "host": "...", "port": ..., "user": "...", "password": "..."}
        payload["proxyMethod"] = 2
        payload["proxyType"] = proxy_info.get("type", "noproxy")
        payload["host"] = proxy_info.get("host", "")
        payload["port"] = proxy_info.get("port", "")
        payload["proxyUserName"] = proxy_info.get("user", "")
        payload["proxyPassword"] = proxy_info.get("password", "")

    try:
        print(f"Creating new BitBrowser window...")
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        data = resp.json()
        
        if data.get('success'):
            new_id = data['data']['id']
            print(f"✅ Created new browser window: {new_id}")
            return new_id
        else:
            print(f"❌ Failed to create browser: {data.get('msg')}")
            return None
    except Exception as e:
        print(f"❌ Create API Exception: {e}")
        return None



# 七牛云配置
QINIU_ACCESS_KEY = os.getenv('QINIU_ACCESS_KEY', 'YrFo8wwXHr1G2T150slBn5pHd-adC7o91UZHlgYU')
QINIU_SECRET_KEY = os.getenv('QINIU_SECRET_KEY', 'fiUUq52QQRMBwTJkZfUb1KYcF6d6FFTrHOn78_Pr')
QINIU_BUCKET_NAME = os.getenv('QINIU_BUCKET_NAME', 'manga-adu')
QINIU_CDN_DOMAIN = os.getenv('QINIU_DOMAIN', 'http://cdn2.manfanfan.com').strip()

def upload_image_to_qiniu(image_url: str) -> str:
    """
    下载图片并上传到七牛云，返回 CDN 地址
    """
    try:
        # 1. 下载图片
        print(f"[lovart] Downloading image from: {image_url}")
        resp = requests.get(image_url, timeout=30)
        if resp.status_code != 200:
            print(f"[lovart] Failed to download image: {resp.status_code}")
            return image_url # Fallback to original URL
        
        image_data = resp.content
        
        # 2. 构建文件名
        # 使用 UUID 防止冲突，保持后缀
        ext = ".png" # 默认为 png
        if ".jpg" in image_url or ".jpeg" in image_url:
            ext = ".jpg"
        
        key = f"agent_images/{uuid.uuid4()}{ext}"
        
        # 3. 上传七牛云
        print(f"[lovart] Uploading to Qiniu: {key}")
        q = Auth(QINIU_ACCESS_KEY, QINIU_SECRET_KEY)
        token = q.upload_token(QINIU_BUCKET_NAME, key, 3600)
        
        ret, info = put_data(token, key, image_data)
        
        if info.status_code == 200:
            cdn_url = f"{QINIU_CDN_DOMAIN}/{key}"
            print(f"[lovart] Upload success. CDN URL: {cdn_url}")
            return cdn_url
        else:
            print(f"[lovart] Qiniu upload failed: {info.text_body}")
            return image_url # Fallback
            
    except Exception as e:
        print(f"[lovart] Upload to Qiniu error: {e}")
        return image_url # Fallback

def setup_playwright_env():
    """
    设置Playwright环境变量
    检查本地是否存在browsers目录，如果存在则设置为PLAYWRIGHT_BROWSERS_PATH
    这样可以在没有安装Playwright的机器上使用本地打包的浏览器
    """
    try:
        # 获取当前执行目录
        if getattr(sys, 'frozen', False):
            # 打包后的exe目录
            base_dir = os.path.dirname(sys.executable)
        else:
            # 脚本运行时的目录
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
        # 检查可能的浏览器目录位置
        possible_paths = [
            os.path.join(base_dir, 'browsers'),
            os.path.join(os.path.dirname(base_dir), 'browsers'),
            # 兼容旧逻辑
            os.path.join(base_dir, 'backend', 'browsers')
        ]
        
        for browser_path in possible_paths:
            if os.path.exists(browser_path) and os.path.isdir(browser_path):
                print(f"发现本地浏览器目录: {browser_path}")
                os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browser_path
                return True
                
        # 如果环境变量中已设置，则打印
        if "PLAYWRIGHT_BROWSERS_PATH" in os.environ:
            print(f"使用环境变量中的浏览器路径: {os.environ['PLAYWRIGHT_BROWSERS_PATH']}")
            return True
            
    except Exception as e:
        print(f"设置Playwright环境时出错: {e}")
    
    return False

# Initialize colorama
init()

# Configuration: Number of concurrent browser sessions
_LOVART_POOL_SIZE = int(os.environ.get("LOVART_POOL_SIZE", 6))

_lovart_sessions_lock = Lock() # Protects access to the _lovart_sessions list structure
_lovart_sessions = []
# Initialize pool with empty slots
for _ in range(_LOVART_POOL_SIZE):
    _lovart_sessions.append({
        "thread": None,
        "loop": None,
        "browser": None,
        "context": None,
        "page": None,
        "busy_lock": Lock(), # Threading lock to mark session as busy
        "last_active": 0, # Timestamp of last activity
        "bitbrowser_id": None, 
    })

_LOVART_VIEWPORT = {"width": 1280, "height": 720}

def lovart_get_pool_size() -> int:
    return _LOVART_POOL_SIZE

def lovart_has_session(index: int = None) -> bool:
    with _lovart_sessions_lock:
        if index is not None:
            if 0 <= index < len(_lovart_sessions):
                sess = _lovart_sessions[index]
                thread_obj = sess.get("thread")
                loop = sess.get("loop")
                page = sess.get("page")
                return bool(thread_obj and loop and page and thread_obj.is_alive() and not loop.is_closed())
            return False
        
        # If index is None, check if ANY session is alive
        for sess in _lovart_sessions:
            thread_obj = sess.get("thread")
            loop = sess.get("loop")
            page = sess.get("page")
            if thread_obj and loop and page and thread_obj.is_alive() and not loop.is_closed():
                return True
        return False

def lovart_get_session_by_index(index: int):
    with _lovart_sessions_lock:
        if 0 <= index < len(_lovart_sessions):
            sess = _lovart_sessions[index]
            return sess.get("loop"), sess.get("page")
    return None, None

def lovart_acquire_session(timeout: float = 5.0):
    """
    Find and lock an available session.
    Returns: (index, loop, page) or (None, None, None)
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        # 1. Snapshot valid sessions
        candidates = []
        with _lovart_sessions_lock:
            for idx, sess in enumerate(_lovart_sessions):
                thread_obj = sess.get("thread")
                loop = sess.get("loop")
                page = sess.get("page")
                if thread_obj and loop and page and thread_obj.is_alive() and not loop.is_closed():
                    candidates.append((idx, sess))
        
        if not candidates:
            return None, None, None

        # 2. Try to acquire lock on one of them
        for idx, sess in candidates:
            busy_lock = sess.get("busy_lock")
            if busy_lock.acquire(blocking=False):
                # Update last active time
                with _lovart_sessions_lock:
                     _lovart_sessions[idx]["last_active"] = time.time()
                return idx, sess.get("loop"), sess.get("page")
        
        time.sleep(0.1)
    
    return None, None, None

def lovart_release_session(index: int):
    with _lovart_sessions_lock:
        if 0 <= index < len(_lovart_sessions):
            sess = _lovart_sessions[index]
            busy_lock = sess.get("busy_lock")
            sess["last_active"] = time.time() # Update on release too
            try:
                busy_lock.release()
            except RuntimeError:
                # Already released
                pass

def lovart_cleanup_idle_sessions(max_idle_seconds: float = 600.0):
    """
    Close sessions that have been idle for too long.
    """
    indices_to_close = []
    with _lovart_sessions_lock:
        now = time.time()
        for idx, sess in enumerate(_lovart_sessions):
            thread_obj = sess.get("thread")
            loop = sess.get("loop")
            # Only check active sessions
            if thread_obj and loop and not loop.is_closed():
                last_active = sess.get("last_active", 0)
                # Ensure we don't close a busy session
                busy_lock = sess.get("busy_lock")
                if not busy_lock.locked() and (now - last_active > max_idle_seconds) and last_active > 0:
                    indices_to_close.append(idx)
    
    if indices_to_close:
        print(f"[lovart] Cleaning up idle sessions: {indices_to_close}")
        for idx in indices_to_close:
            lovart_close_session(idx)

async def lovart_ensure_viewport(page: Page, width: int = 1080, height: int = 1920):
    try:
        current = page.viewport_size
    except Exception:
        current = None

    if isinstance(current, dict) and current.get("width") == width and current.get("height") == height:
        return

    try:
        await page.set_viewport_size({"width": width, "height": height})
    except Exception:
        pass

async def lovart_prepare_canvas_page(page: Page, timeout_ms: int = 10000):
    await lovart_ensure_viewport(page, width=_LOVART_VIEWPORT["width"], height=_LOVART_VIEWPORT["height"])
    
    # Define indicators for both Video and Image menus
    # Update: Use generic path selector fallback because test-id might be missing
    video_menu_btn = page.get_by_test_id("generate-menu-video")
    image_menu_btn = page.get_by_test_id("generate-menu-image")
    
    # Fallback using unique path fragments (Circle for Image, Triangle for Video)
    # Image Icon contains a circle: M7.499 6a1.5 1.5
    # Video Icon contains a triangle: M7.35 7.037
    image_path_fragment = "M7.499 6a1.5 1.5"
    video_path_fragment = "M7.35 7.037"
    
    image_menu_fallback = page.locator(f'button:has(svg path[d*="{image_path_fragment}"])').first
    video_menu_fallback = page.locator(f'button:has(svg path[d*="{video_path_fragment}"])').first
    
    # Generic fallback (if we just want to know we are on the page)
    # svg_path_d_start = "M10.1 2.5a.4.4 0 0 1 .4.4v.5a.4.4 0 0 1-.4.4H4.772"
    # menu_btn_fallback = page.locator(f'button:has(svg path[d^="{svg_path_d_start}"])').first
    
    # 1. Quick check: if already visible, return immediately
    try:
        if await video_menu_btn.is_visible() or await image_menu_btn.is_visible() or \
           await image_menu_fallback.is_visible() or await video_menu_fallback.is_visible():
            return
    except Exception:
        pass

    # 2. Check for Onboarding / Welcome popups and close them
    # Example: "Skip", "Next", "Start Creating" buttons
    # Common onboarding texts in Chinese or English
    skip_texts = ["跳过", "Skip", "下一步", "Next", "开始创作", "Start Creating", "我知道了", "Got it"]
    for text in skip_texts:
        try:
            btn = page.locator("button").filter(has_text=text).first
            if await btn.count() > 0 and await btn.is_visible():
                print(f"Closing onboarding popup: {text}")
                await btn.click()
                await asyncio.sleep(0.5)
        except Exception:
            pass

    # 3. If not on Canvas page, navigate there
    try:
        if not page.url.startswith("https://www.lovart.ai/canvas"):
            print("Navigating to Canvas page...")
            await page.goto("https://www.lovart.ai/canvas", timeout=timeout_ms)
    except Exception:
        pass

    # 4. Wait for load state
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
    except Exception:
        pass

    # 5. Wait for either Video OR Image menu to be visible
    # We use a loop to check periodically to avoid "Expect.to_be_visible" failing on one if the other is present
    start_time = time.time()
    while time.time() - start_time < (timeout_ms / 1000):
        try:
            if await video_menu_btn.is_visible() or await image_menu_btn.is_visible() or \
               await image_menu_fallback.is_visible() or await video_menu_fallback.is_visible():
                return
            
            # Check for popups again during wait
            await lovart_close_right_bottom_popup(page)
            
        except Exception:
            pass
        await asyncio.sleep(0.5)

    # 6. If timed out, try one last reload and check
    try:
        print("Canvas menu not found, reloading...")
        await page.reload(timeout=10000) # Wait 10 seconds
        await page.wait_for_load_state("domcontentloaded", timeout=10000)
        
        # Check again quickly
        if await video_menu_btn.is_visible() or await image_menu_btn.is_visible() or \
           await image_menu_fallback.is_visible() or await video_menu_fallback.is_visible():
            return
            
    except Exception as e:
        print(f"Reload failed: {e}")
        pass

    # Final check (will throw error if fails)
    if await image_menu_btn.is_visible() or await image_menu_fallback.is_visible() or await video_menu_fallback.is_visible():
        return
    
    # If we are here, everything failed.
    # Instead of just expecting and failing, raise a specific error that triggers a full restart
    raise Exception("Canvas menu not found after reload. Triggering session destroy.")

async def lovart_close_right_bottom_popup(page: Page):
    candidates = [
        page.locator("div.close-btn").filter(has=page.locator('svg[viewBox="0 0 24 24"]')).first,
        page.locator("div.close-btn").first,
        page.get_by_role("button", name="知道了").first,
    ]

    for loc in candidates:
        try:
            if await loc.count() == 0:
                continue
            if not await loc.is_visible():
                continue
            await loc.click(timeout=1500)
            await asyncio.sleep(0.2)
            return True
        except Exception:
            continue
    return False

async def lovart_scroll_canvas_up(page: Page, pixels: int = 100):
    canvas = page.get_by_test_id("elements-canvas")
    if await canvas.count() == 0:
        canvas = page.locator('[data-testid="elements-canvas"]').first
    if await canvas.count() == 0:
        return False

    try:
        await canvas.scroll_into_view_if_needed(timeout=1500)
    except Exception:
        pass

    try:
        box = await canvas.bounding_box()
        if box:
            x = box["x"] + box["width"] / 2
            y = box["y"] + box["height"] / 2
            await page.mouse.move(x, y)
    except Exception:
        pass

    try:
        await page.mouse.wheel(0, abs(pixels))
        await asyncio.sleep(0.1)
        return True
    except Exception:
        pass

    try:
        await page.evaluate("(d) => window.scrollBy(0, d)", abs(pixels))
        await asyncio.sleep(0.1)
        return True
    except Exception:
        return False

async def lovart_handle_security_verification(page: Page, prefix: str = "[lovart]"):
    """
    通用处理 Security Verification / Cloudflare 验证弹窗
    策略：不依赖具体 class，而是依赖 role、text 和结构
    """
    # 1. 检测弹窗是否存在
    # 使用正则匹配标题，忽略大小写
    # 定位策略：查找包含 "Security Verification" 或 "安全验证" 标题的 Dialog 或 容器
    try:
        # 也可以直接找 role="dialog" 且可见的元素
        modal = page.locator('section[role="dialog"]').filter(has_text=re.compile(r"Security Verification|安全验证", re.IGNORECASE)).first
        if await modal.count() == 0:
            # 备用：如果没有 standard dialog role，找标题所在的任何容器
            header = page.locator("h2, h3, div").filter(has_text=re.compile(r"^\s*(Security Verification|安全验证)\s*$", re.IGNORECASE)).first
            if await header.count() == 0 or not await header.is_visible():
                return False
            # 获取标题的外层容器 (通常是弹窗主体)
            modal = header.locator("xpath=./ancestor::div[contains(@class, 'Modal') or count(*) > 3][1]")
    except Exception:
        return False

    if not await modal.is_visible():
        return False

    print(f"{prefix} 🛡️ Security Verification modal detected.")

    # 2. 处理 Cloudflare Turnstile (确保获取到 Token)
    # Cloudflare 的 input name 通常固定为 cf-turnstile-response
    cf_input = modal.locator('input[name="cf-turnstile-response"]').first
    if await cf_input.count() == 0:
        # 尝试全局搜索
        cf_input = page.locator('input[name="cf-turnstile-response"]').first

    start_time = time.time()
    token_found = False
    
    # 尝试最多 10 秒等待 Token 出现
    while time.time() - start_time < 10:
        if await cf_input.count() > 0:
            val = await cf_input.get_attribute("value")
            if val and len(val) > 20:
                print(f"{prefix} ✅ Turnstile token found. Ready to continue.")
                token_found = True
                break
        
        # 如果没有 token，尝试点击 Widget
        # Widget 通常在一个 iframe 里，或者是一个 div 容器
        # 策略：找到 input 的父级 iframe 或 div 并点击
        print(f"{prefix} ⏳ Waiting for Turnstile... attempting to activate widget.")
        
        # 尝试1: 点击 iframe (如果存在)
        frames = page.frames
        clicked_frame = False
        for frame in frames:
            if "cloudflare" in frame.url or "turnstile" in frame.url:
                try:
                    # 点击 iframe 内部的 checkbox 或 body
                    cb = frame.locator("input[type='checkbox']").first
                    if await cb.count() > 0:
                        await cb.click(force=True)
                        clicked_frame = True
                    else:
                        await frame.locator("body").click(force=True)
                        clicked_frame = True
                except:
                    pass
        
        # 尝试2: 如果没有 iframe，点击 input 附近的容器
        if not clicked_frame and await cf_input.count() > 0:
            try:
                # 点击 input 的父级 div (通常是 widget wrapper)
                wrapper = cf_input.locator("xpath=..").first
                if await wrapper.is_visible():
                     await wrapper.click(force=True)
                else:
                     # 再往上一层
                     await cf_input.locator("xpath=../..").first.click(force=True)
            except:
                pass
        
        await asyncio.sleep(1)

    # 3. 点击 "Continue" 按钮
    # 策略：在 modal 内部寻找带有 Continue/继续 文本的按钮
    # 只要弹窗还在，就反复尝试点击
    
    print(f"{prefix} 👆 Attempting to click Continue...")
    
    # 定义按钮查找器列表 (优先级从高到低)
    button_locators = [
        # 1. 精确匹配文字的按钮
        modal.locator('button').filter(has_text=re.compile(r"^\s*(Continue|继续)\s*$", re.IGNORECASE)),
        # 2. 包含文字的按钮
        modal.locator('button').filter(has_text=re.compile(r"(Continue|继续)", re.IGNORECASE)),
        # 3. 任何看起来像按钮的 div (有文字且居中) - 针对你提供的 HTML 中的结构
        modal.locator('div, a').filter(has_text=re.compile(r"^\s*(Continue|继续)\s*$", re.IGNORECASE)).filter(has=page.locator("xpath=self::*[contains(@class, 'cursor-pointer') or contains(@class, 'btn') or contains(@class, 'text-center')]")),
        # 4. 最后的手段：弹窗里唯一的那个大按钮 (通常是最后一个按钮)
        modal.locator('button').last, 
    ]

    for _ in range(5): # 最多尝试 5 轮点击
        if not await modal.is_visible():
            print(f"{prefix} ✅ Modal closed.")
            return True

        clicked = False
        for loc in button_locators:
            try:
                if await loc.count() > 0 and await loc.first.is_visible():
                    # 确保它是启用的
                    if await loc.first.is_disabled():
                        print(f"{prefix} Button disabled, waiting...")
                        await asyncio.sleep(0.5)
                        continue
                    
                    # 尝试多种点击方式
                    btn = loc.first
                    # 1. JS Click (最稳，无视遮挡)
                    await btn.evaluate("e => e.click()")
                    # 2. 物理点击 (作为补充)
                    try:
                        await btn.click(timeout=500, force=True) 
                    except: 
                        pass
                    
                    clicked = True
                    print(f"{prefix} Clicked button: {await btn.inner_text()}")
                    break # 这一轮点到了就不试其他 selector 了
            except Exception:
                continue
        
        if not clicked:
            # 如果没找到按钮，可能是 DOM 还没渲染完，或者按钮在 shadow root 里
            print(f"{prefix} No button found yet...")
        
        # 检查是否消失
        try:
            await expect(modal).to_be_hidden(timeout=1500)
            print(f"{prefix} ✅ Verification passed.")
            return True
        except:
            # 还在，继续下一轮
            pass
            
    # 如果还是没消失，返回失败
    return not await modal.is_visible()

async def _lovart_close_session_async(index: int = None):
    indices_to_close = []
    if index is not None:
        indices_to_close = [index]
    
    for idx in indices_to_close:
        sess = None
        with _lovart_sessions_lock:
            if idx < len(_lovart_sessions):
                sess = _lovart_sessions[idx]
        
        if not sess:
            continue

        browser = sess.get("browser")
        context = sess.get("context")
        bitbrowser_id = sess.get("bitbrowser_id")

        # For BitBrowser, we should close via API
        if bitbrowser_id:
            close_bitbrowser_api(bitbrowser_id)
            # IMPORTANT: Delete the window to free up the 10-window limit for free users
            delete_bitbrowser_window(bitbrowser_id)
            # Reset the global ID mapping so next time we create a new one
            if idx < len(BITBROWSER_IDS):
                BITBROWSER_IDS[idx] = None
        else:
            # Fallback for standard playwright cleanup if any
            try:
                if context:
                    await context.close()
            except:
                pass
            finally:
                if browser:
                    try:
                        await browser.close()
                    except:
                        pass

        with _lovart_sessions_lock:
            # Preserve the lock
            busy_lock = sess.get("busy_lock")
            _lovart_sessions[idx] = {
                "thread": None,
                "loop": None,
                "browser": None,
                "context": None,
                "page": None,
                "busy_lock": busy_lock if busy_lock else Lock(),
                "bitbrowser_id": None,
            }

def lovart_close_session(index: int = None, timeout: float = 30.0):
    if index is not None:
        loop = None
        with _lovart_sessions_lock:
            if index < len(_lovart_sessions):
                loop = _lovart_sessions[index].get("loop")
        
        if not loop or loop.is_closed():
            return

        future = asyncio.run_coroutine_threadsafe(_lovart_close_session_async(index), loop)
        try:
            future.result(timeout=timeout)
        except:
            pass
    else:
        # Close all
        loops_indices = []
        with _lovart_sessions_lock:
            for idx, sess in enumerate(_lovart_sessions):
                loop = sess.get("loop")
                if loop and not loop.is_closed():
                    loops_indices.append((idx, loop))
        
        for idx, loop in loops_indices:
             future = asyncio.run_coroutine_threadsafe(_lovart_close_session_async(idx), loop)
             try:
                future.result(timeout=timeout)
             except:
                pass

async def run_generate_video_on_page(page: Page, duration_label: str, start_frame_image_path: str, prompt: str, session_index: int = -1):
    prefix = f"[Session {session_index}] [lovart]" if session_index >= 0 else "[lovart]"
    await lovart_ensure_viewport(page, width=_LOVART_VIEWPORT["width"], height=_LOVART_VIEWPORT["height"])
    if not page.url.startswith("https://www.lovart.ai/canvas"):
        await page.goto("https://www.lovart.ai/canvas", timeout=60000)

    points = await _lovart_get_points_async(page)
    if points < 20:
        return False, "积分低于20", {"points": points, "low_points": True}

    video_menu_btn = page.get_by_test_id("generate-menu-video")
    
    # Check if video_menu_btn is visible, if not, try fallback (assuming the user's reported button IS the video button or we can find it)
    # The user reported path starts with "M10.1 2.5..."
    # We will try to click it if found.
    if not await video_menu_btn.is_visible():
        # Video Icon contains a triangle: M7.35 7.037
        video_path_fragment = "M7.35 7.037"
        
        # If the button provided by user is actually the Video button (or generic menu button), we can use it.
        # Let's try to find ANY button with that path and click it if testid fails.
        fallback_btn = page.locator(f'button:has(svg path[d*="{video_path_fragment}"])').first
        if await fallback_btn.is_visible():
            print(f"{prefix} Using fallback menu button (Video)...")
            video_menu_btn = fallback_btn
    
    await expect(video_menu_btn).to_be_visible(timeout=10000)
    await video_menu_btn.click()
    await asyncio.sleep(1)

    await lovart_close_right_bottom_popup(page)
    await lovart_scroll_canvas_up(page, pixels=100)

    model_btn = page.get_by_test_id("generator-model-button")
    await expect(model_btn).to_be_visible(timeout=10000)
    await model_btn.click()
    await asyncio.sleep(1)

    try:
        await page.mouse.wheel(0, 100)
    except Exception:
        pass
    await page.evaluate("() => window.scrollBy(0, 100)")
    await asyncio.sleep(0.2)

    option_btn = page.get_by_test_id("generator-model-option-vidu/vidu-q2")
    last_err = None
    for attempt in range(6):
        try:
            try:
                await option_btn.scroll_into_view_if_needed(timeout=1500)
            except Exception:
                pass

            await expect(option_btn).to_be_visible(timeout=2000)
            await option_btn.click()
            await asyncio.sleep(1)
            last_err = None
            break
        except Exception as e:
            last_err = e
            try:
                await model_btn.click(timeout=2000)
            except Exception:
                pass
            await asyncio.sleep(0.2)
            menu_el = page.locator('[role="menu"], [role="listbox"]').first
            delta = 260 if attempt % 2 == 0 else -260
            if await menu_el.count() > 0 and await menu_el.is_visible():
                await menu_el.evaluate("(el, d) => { el.scrollTop = (el.scrollTop || 0) + d; }", delta)
            else:
                try:
                    await page.mouse.wheel(0, delta)
                except Exception:
                    await page.evaluate("(d) => window.scrollBy(0, d)", delta)
            await asyncio.sleep(0.2)

    if last_err is not None:
        raise last_err

    count_btn = page.get_by_test_id("generator-count-button")
    await expect(count_btn).to_be_visible(timeout=10000)
    await count_btn.click()
    await asyncio.sleep(1)

    duration_btn = page.locator("div.flex.flex-wrap.items-center.gap-2 button").filter(has_text=duration_label).first
    await expect(duration_btn).to_be_visible(timeout=10000)
    await duration_btn.click()
    await asyncio.sleep(1)

    await page.keyboard.press("Escape")
    await asyncio.sleep(1)

    start_frame_btn = page.locator("span.lovart-menu-popover").filter(has_text="起始").first
    await expect(start_frame_btn).to_be_visible(timeout=10000)
    hover_panel = start_frame_btn.locator('xpath=ancestor::div[contains(@class,"border-panel")]').first
    if await hover_panel.count() > 0:
        await hover_panel.hover()
    else:
        await start_frame_btn.hover()
    await asyncio.sleep(0.3)
    await start_frame_btn.evaluate("(el) => el.click()")
    await asyncio.sleep(1)

    upload_option = page.get_by_test_id("generator-image-reference-option-uploadImageFromLocal")
    await expect(upload_option).to_be_visible(timeout=10000)

    async with page.expect_file_chooser() as fc_info:
        await upload_option.hover()
        await asyncio.sleep(0.2)
        await upload_option.evaluate("(el) => el.click()")
    file_chooser = await fc_info.value
    await file_chooser.set_files(start_frame_image_path)

    prompt_input = page.get_by_test_id("generator-prompt-input").first
    await expect(prompt_input).to_be_visible(timeout=10000)
    await prompt_input.fill(prompt)
    await lovart_scroll_canvas_up(page, pixels=100)

    context = page.context
    done_event = asyncio.Event()
    click_ts = None
    result = {
        "video_url": None,
        "cover_url": None,
        "matched_json_url": None,
        "matched_json_status": None,
        "network_hits": [],
    }

    def _maybe_add_hit(hit: dict):
        if len(result["network_hits"]) >= 120:
            return
        result["network_hits"].append(hit)

    async def _on_request(request):
        nonlocal click_ts
        if click_ts is None:
            return

        try:
            url = request.url or ""
            rt = request.resource_type
        except Exception:
            return

        if rt not in ("fetch", "xhr") and ".mp4" not in url and ".jpg" not in url and ".jpeg" not in url:
            return

        _maybe_add_hit({"type": "request", "rt": rt, "method": request.method, "url": url})

        if result["video_url"] is None and ".mp4" in url:
            result["video_url"] = url
            done_event.set()

    async def _on_response(response):
        nonlocal click_ts
        if click_ts is None:
            return

        try:
            url = response.url or ""
            rt = response.request.resource_type
            method = response.request.method
            status = response.status
            ct = (response.headers or {}).get("content-type", "")
        except Exception:
            return

        if rt not in ("fetch", "xhr") and ".mp4" not in url and ".jpg" not in url and ".jpeg" not in url:
            return

        _maybe_add_hit({"type": "response", "rt": rt, "status": status, "method": method, "ct": ct, "url": url})

        if result["video_url"] is None and ".mp4" in url:
            result["video_url"] = url
            done_event.set()
            return

        if result["cover_url"] is None and (".jpg" in url or ".jpeg" in url) and "/artifacts/" in url:
            result["cover_url"] = url

        if result["video_url"] is not None:
            return

        if "application/json" not in (ct or ""):
            return

        if rt not in ("fetch", "xhr"):
            return

        try:
            text = await response.text()
        except Exception:
            return

        match = re.search(r"https?://[^\s\"']+?\.mp4", text)
        if match:
            result["video_url"] = match.group(0)
            result["matched_json_url"] = url
            result["matched_json_status"] = status
            cover_match = re.search(r"https?://[^\s\"']+?\.(jpg|jpeg)", text, flags=re.IGNORECASE)
            if cover_match:
                result["cover_url"] = result["cover_url"] or cover_match.group(0)
            done_event.set()

    context.on("request", _on_request)
    context.on("response", _on_response)

    await asyncio.sleep(5)

    generate_btn = page.get_by_test_id("generator-generate-button")
    await expect(generate_btn).to_be_visible(timeout=10000)

    click_ts = time.time()
    print(f"[lovart] click generate: {click_ts}")
    await generate_btn.click()
    try:
        await lovart_handle_security_verification(page, prefix=prefix)
    except Exception:
        pass

    try:
        await asyncio.wait_for(done_event.wait(), timeout=180)
    except asyncio.TimeoutError:
        return False, "未从网络捕获到本次生成视频地址", {
            "points": points,
            "duration": duration_label,
            "start_frame_image_path": start_frame_image_path,
            "current_url": page.url,
            "network_hits": result["network_hits"],
        }
    finally:
        try:
            context.off("request", _on_request)
        except Exception:
            try:
                context.remove_listener("request", _on_request)
            except Exception:
                pass
        try:
            context.off("response", _on_response)
        except Exception:
            try:
                context.remove_listener("response", _on_response)
            except Exception:
                pass

    return True, "视频生成完成", {
        "points": points,
        "duration": duration_label,
        "start_frame_image_path": start_frame_image_path,
        "video_url": result["video_url"],
        "cover_url": result["cover_url"],
        "matched_json_url": result["matched_json_url"],
        "matched_json_status": result["matched_json_status"],
    }

async def _lovart_get_points_async(page: Page) -> int:
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception:
        pass

    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass

    await asyncio.sleep(1)

    candidates = [
        page.locator('css=div.flex.min-w-10.items-center:has(svg[viewBox="0 0 16 24"]) span').first,
        page.locator('css=div:has(svg[viewBox="0 0 16 24"]) span').first,
        page.locator('xpath=//div[contains(@class,"min-w-10") and contains(@class,"items-center") and .//svg[@viewBox="0 0 16 24"]]//span').first,
        page.locator('xpath=//div[contains(@class,"min-w-10") and contains(@class,"items-center") and .//path[contains(@d,"M8.674 4.081")]]//span').first,
    ]

    last_seen_text = None
    for locator in candidates:
        try:
            if await locator.count() == 0:
                continue

            try:
                await expect(locator).to_be_visible(timeout=2500)
            except Exception:
                pass

            raw_text = (await locator.inner_text()) or ""
            last_seen_text = raw_text
            match = re.search(r"\d+", raw_text)
            if match:
                return int(match.group(0))
        except Exception:
            continue

    if last_seen_text is not None:
        raise ValueError(f"无法解析积分: {last_seen_text}")
    raise ValueError("未找到积分元素")

async def _lovart_generate_video_async(index: int, page: Page, duration_label: str, start_frame_image_path: str, prompt: str):
    if not page:
        return False, "没有可用的浏览器会话，请先调用/register登陆", {}

    success, message, data = await run_generate_video_on_page(
        page=page,
        duration_label=duration_label,
        start_frame_image_path=start_frame_image_path,
        prompt=prompt,
        session_index=index
    )
    if not success and data.get("low_points"):
        await _lovart_close_session_async(index)
        return success, message, data

    return success, message, data

def lovart_generate_video(index: int, duration_label: str, start_frame_image_path: str, prompt: str, timeout: float = 900.0):
    loop, page = lovart_get_session_by_index(index)
    if not loop or not page or loop.is_closed():
        return False, "没有可用的浏览器会话，请先调用/register登陆", {}
    
    future = asyncio.run_coroutine_threadsafe(
        _lovart_generate_video_async(
            index=index,
            page=page,
            duration_label=duration_label,
            start_frame_image_path=start_frame_image_path,
            prompt=prompt,
        ),
        loop,
    )
    return future.result(timeout=timeout)

# ================= Mail Configuration =================
import platform

# PROXY_HOST = "127.0.0.1"
# # Detect OS to set proxy port
# if platform.system().lower() == "darwin": # macOS
#     PROXY_PORT = 7898 # Clash Verge SOCKS port
# else: # Windows or others
#     PROXY_PORT = 10808 # Default Windows port
PROXY_HOST = "192.168.1.159"
PROXY_PORT = 7897 

PROXIES = {
    'http': f'socks5://{PROXY_HOST}:{PROXY_PORT}',
    'https': f'socks5://{PROXY_HOST}:{PROXY_PORT}'
}
MAILU_API_TOKEN = 'M9K175RXZDWJ0K3C7Y5R2W9FRH29SN0G'
MAILU_API_URL = 'https://mail.mx892.asia/api/v1'
BRIDGE_URL = 'http://130.94.41.184:5000/get_latest_email'
BRIDGE_SECRET = 'MySuperSecretKey123!'

# 4. 域名池配置 (在此处添加所有已在 Mailu 后台添加过的域名)
AVAILABLE_DOMAINS = [
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
def get_temp_email():
    """
    Create a new user via Mailu API
    Returns: (email_address, token) where token is "email|password"
    """
    print(f"{Fore.YELLOW}Creating new email user...{Style.RESET_ALL}")
    
    random_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=11))
    email = f'{random_id}@{random.choice(AVAILABLE_DOMAINS)}'
    password = 'StrongPassword123!'
    
    headers = {
        'Authorization': f'Bearer {MAILU_API_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'email': email,
        'raw_password': password,
        'comment': 'Python Auto Create',
        'quota': 1000000000,
        'enabled': True
    }
    
    try:
        response = requests.post(f'{MAILU_API_URL}/user', json=payload, headers=headers, proxies=PROXIES, timeout=15)
        
        # 200: OK, 409: Already exists (rare but handle as success for this context or retry?)
        # For simplicity, if it exists, we can try to use it.
        if response.status_code in [200, 201, 409]:
             print(f"{Fore.GREEN}Email obtained: {email}{Style.RESET_ALL}")
             token = f"{email}|{password}"
             return email, token
        else:
            print(f"{Fore.RED}Failed to create user: {response.status_code} - {response.text}{Style.RESET_ALL}")
            return None, None
            
    except Exception as e:
        print(f"{Fore.RED}Error getting email: {e}{Style.RESET_ALL}")
        return None, None

def get_email_code(token):
    """
    Check for verification code using the bridge API
    token is "email|password"
    """
    if not token or "|" not in token:
        return None
        
    email, password = token.split("|", 1)
    
    print(f"Checking email for code ({email})...")
    
    payload = {
        "api_secret": BRIDGE_SECRET,
        "email": email,
        "password": password
    }
    
    try:
        resp = requests.post(BRIDGE_URL, json=payload, proxies=PROXIES, timeout=10)
        
        if resp.status_code != 200:
            # print(f"Bridge API error: {resp.status_code}")
            return None

        data = resp.json()
        
        if data.get("status") == "success":
            subject = data.get('subject', '')
            content = data.get('content', '')
            
            # Prefer body or subject
            text_content = f"{subject} {content}"
            
            # Look for 6 digit code
            match = re.search(r'\b\d{6}\b', text_content)
            if match:
                return match.group(0)
        # elif data.get("status") == "empty":
        #    pass
            
    except Exception as e:
        print(f"Error checking email: {e}")
        
    return None

async def close_google_popup(page: Page):
    """
    Check for Google Sign-in iframe and close it if present.
    """
    try:
        # Google One Tap iframe
        # The src contains "accounts.google.com/gsi/iframe"
        iframe_selector = 'iframe[src*="accounts.google.com/gsi/iframe"]'
        if await page.locator(iframe_selector).count() > 0:
            google_iframe = page.frame_locator(iframe_selector)
            close_btn = google_iframe.locator('#close')
            
            if await close_btn.is_visible(timeout=2000):
                print(f"{Fore.RED}Google Sign-in popup detected (Iframe)! Closing...{Style.RESET_ALL}")
                await close_btn.click()
                # Wait for it to detach/hide
                try:
                    await expect(page.locator(iframe_selector)).to_be_hidden(timeout=5000)
                    print("Google popup closed.")
                except:
                    print("Google popup close button clicked, but iframe still visible (might be animating out).")
                return True
    except Exception as e:
        # Ignore if not found or error
        # print(f"Popup check debug: {e}")
        pass
    return False

async def register_lovart_account(keep_alive_after_code: bool = False, ready_event: Event = None, ready_payload: dict = None, session_index: int = 0):
    """
    Automate Lovart registration process using BitBrowser & Playwright
    """
    
    # Task Parameters
    # prompt = '...' 
    # image_path = ...
    # These are example placeholders in this function but not used directly in the API flow logic (except as default if not passed)
    
    # NOTE: image_path is passed as argument or extracted from payload, the hardcoded one below was for testing.
    # image_path = r'F:\完结文\天选种田\12月27日 (4)(1).png'

    # Loop for restart capability (Low points handling)
    # We use a loop to allow switching accounts if points are low, but we break on errors.
    retry_count = 0
    max_retries = 3
    
    while retry_count < max_retries:
        print(f"{Fore.GREEN}Starting Lovart automation with BitBrowser (Attempt {retry_count+1})...{Style.RESET_ALL}")

        # setup_playwright_env() # Not needed for Remote Connection

        # Determine Browser ID
        browser_id = None
        if BITBROWSER_IDS:
            if session_index < len(BITBROWSER_IDS):
                browser_id = BITBROWSER_IDS[session_index]
            else:
                browser_id = BITBROWSER_IDS[0]
                print(f"Warning: Session index {session_index} out of range. Using first ID.")
        else:
             print("Error: BITBROWSER_IDS not configured.")
             return False, "BitBrowser IDs not configured", {}

        # Auto-create if ID is None, placeholder or invalid format (simple heuristic)
        if not browser_id or (isinstance(browser_id, str) and (browser_id.startswith("browser_id_") or "你的窗口ID" in browser_id)):
            print(f"⚠️ Detected invalid or missing ID '{browser_id}'. Attempting to auto-create a new BitBrowser window...")
            new_id = create_bitbrowser_window(name_prefix=f"Lovart-Sess-{session_index}")
            if new_id:
                browser_id = new_id
                # Update the global list in memory so we reuse this ID for this session index in future retries
                if session_index < len(BITBROWSER_IDS):
                    BITBROWSER_IDS[session_index] = new_id
                print(f"✅ Updated session {session_index} to use new Browser ID: {new_id}")
            else:
                print("❌ Failed to auto-create browser window.")
                retry_count += 1
                await asyncio.sleep(5)
                continue

        # Open BitBrowser
        ws_endpoint = open_bitbrowser(browser_id)
        if not ws_endpoint:
             print("Failed to open BitBrowser. Retrying...")
             # If open failed, the ID might be deleted or invalid.
             # Try to delete it to ensure we don't leave a zombie record/window if it partially opened
             delete_bitbrowser_window(browser_id)
             
             # Clear ID to force creation next time
             if session_index < len(BITBROWSER_IDS):
                 BITBROWSER_IDS[session_index] = None
             retry_count += 1
             await asyncio.sleep(5)
             continue
        
        # Launch Playwright and Connect
        async with async_playwright() as p:
            browser = None
            try:
                browser = await p.chromium.connect_over_cdp(ws_endpoint)
                
                # Use existing context/page
                default_context = browser.contexts[0]
                page = default_context.pages[0] if default_context.pages else await default_context.new_page()
                context = default_context
                
                await lovart_ensure_viewport(page, width=_LOVART_VIEWPORT["width"], height=_LOVART_VIEWPORT["height"])
                
                try:
                    # 1. Go to https://www.lovart.ai/zh
                    print(f"{Fore.YELLOW}Navigating to Lovart...{Style.RESET_ALL}")
                    await page.goto('https://www.lovart.ai/zh', timeout=60000)
                    
                    # Check for Cloudflare/Verify (Camoufox should handle, but just in case)
                    title = await page.title()
                    if "Just a moment" in title or "Verify" in title:
                        print("Cloudflare detected, waiting...")
                        await asyncio.sleep(5)
                    

                    
                    points_container = page.locator(r'div.bg-\[\#262626\]').first
                    has_points_ui = await points_container.is_visible()
                    
                    if has_points_ui:
                        print(f"{Fore.YELLOW}Already logged in. Checking points...{Style.RESET_ALL}")
                        points = 0
                        try:
                            points = await _lovart_get_points_async(page)
                        except:
                            pass
                        
                        if points < 20:
                            print(f"{Fore.YELLOW}Points insufficient ({points}). Clearing cookies and restarting...{Style.RESET_ALL}")
                            await context.clear_cookies()
                            try:
                                await page.evaluate("window.localStorage.clear(); window.sessionStorage.clear();")
                            except:
                                pass
                            print("Restarting browser session...")
                            retry_count += 1
                            # Close this session attempt properly
                            close_bitbrowser_api(browser_id)
                            delete_bitbrowser_window(browser_id) # Free up quota
                            if session_index < len(BITBROWSER_IDS):
                                BITBROWSER_IDS[session_index] = None # Clear ID to force new creation
                            continue 
                        else:
                            print(f"Points sufficient ({points}). Reusing session.")
                            if keep_alive_after_code:
                                print(f"登陆成功 (Session {session_index})，浏览器保持存活。")
                                with _lovart_sessions_lock:
                                    if session_index < len(_lovart_sessions):
                                        sess = _lovart_sessions[session_index]
                                        busy_lock = sess.get("busy_lock")
                                        _lovart_sessions[session_index] = {
                                            "thread": threading.current_thread(),
                                            "loop": asyncio.get_running_loop(),
                                            "browser": browser,
                                            "context": context,
                                            "page": page,
                                            "busy_lock": busy_lock if busy_lock else Lock(),
                                            "bitbrowser_id": browser_id,
                                        }
                                if ready_event is not None:
                                    ready_event.set()
                                while True:
                                    await asyncio.sleep(3600)
                            return True, "Login Reused", {"email": "existing"}
                    

                    
                    # Define email input locator early to check if modal is already open
                    # The placeholder might be different or dynamic
                    # Updated based on user feedback: placeholder="电子邮箱"
                    email_input = page.get_by_placeholder("电子邮箱")
                    if await email_input.count() == 0:
                         email_input = page.get_by_placeholder("请输入邮箱")
                    if await email_input.count() == 0:
                         email_input = page.locator('input[type="email"]')
                    if await email_input.count() == 0:
                         # Fallback using class and partial placeholder match
                         email_input = page.locator('input.mantine-TextInput-input').filter(has=page.locator('xpath=self::*[contains(@placeholder, "邮箱")]'))

                    # Check if Email Input is ALREADY visible (e.g. auto-popup)
                    if await email_input.first.is_visible():
                         print("Email input already visible. Skipping Register button click.")
                    else:
                        # Click Register
                        print(f"{Fore.YELLOW}Waiting for Register button...{Style.RESET_ALL}")
                        
                        # Strategies
                        # Use a more generic selector and force click if necessary
                        # The log says "element is outside of the viewport", so we might need to force click or scroll
                        register_btn = page.locator('.mantine-Button-label', has_text='注册').or_(page.locator('button', has_text='注册')).first

                        # Check for popup BEFORE trying to click Register (it might auto-show)
                        if await close_google_popup(page):
                            print("Popup closed initially.")
                            await asyncio.sleep(1)

                        # Check visibility again after closing popup
                        if await email_input.first.is_visible():
                            print("Email input visible after closing popup. Skipping Register click.")
                        else:
                            try:
                                await expect(register_btn).to_be_visible(timeout=10000)
                                
                                # Try regular click first
                                try:
                                    await register_btn.scroll_into_view_if_needed()
                                    await register_btn.click(timeout=2000)
                                except:
                                    print("Regular click failed, trying JS click...")
                                    # Use JS click which is most reliable for stubborn elements
                                    await register_btn.evaluate("element => element.click()")
                                    
                                print("Clicked Register.")

                                # Check for Google Sign-in popup AGAIN (if triggered by click)
                                await asyncio.sleep(1)
                                if await close_google_popup(page):
                                    print("Popup closed.")
                                    await asyncio.sleep(1)
                                    
                                    # Only click again if input is STILL not visible
                                    if not await email_input.first.is_visible():
                                        print("Email input not visible. Clicking Register again...")
                                        try:
                                            await register_btn.click()
                                            print("Clicked Register again.")
                                        except Exception as e:
                                             print(f"Failed to click Register again (maybe obscured?): {e}")

                            except Exception as e:
                                print(f"Register button not found or interaction failed: {e}")
                                # Don't return False yet, check if input appeared anyway
                                await page.screenshot(path="register_fail.png")
                                # return False, f"Register button fail: {e}", {}  <-- Removed return to allow falling through to check email input

                    # Fill Email
                    print("Waiting for email input...")
                    
                    # Check if we are still on the landing page (Register didn't open modal)
                    # Maybe JS click triggered the event but the UI didn't react fast enough
                    # Or maybe we need to click the 'Register' tab inside a login modal?
                    
                    try:
                        await expect(email_input.first).to_be_visible(timeout=10000)
                    except:
                        print("Email input not found immediately. Diagnosing...")
                        
                        # 1. Check if we need to click "Continue with Email" or similar
                        # Sometimes the modal shows Social Login buttons first
                        email_btn = page.locator('button').filter(has_text='邮箱').or_(page.locator('button').filter(has_text='Email'))
                        if await email_btn.count() > 0 and await email_btn.first.is_visible():
                            # Check if enabled to avoid TimeoutError
                            if await email_btn.first.is_enabled():
                                print("Found enabled 'Email' button. Clicking it...")
                                await email_btn.first.click()
                                await asyncio.sleep(1)
                            else:
                                print("Found 'Email' button but it is disabled. Skipping click.")

                        # 2. Check if we are in Login mode instead of Register
                        # Look for "Sign up" or "注册" switch in the modal
                        switch_to_register = page.locator('.mantine-Text-root').filter(has_text='去注册').or_(page.locator('div').filter(has_text='去注册'))
                        if await switch_to_register.count() > 0 and await switch_to_register.first.is_visible():
                            print("Found switch to Register. Clicking...")
                            await switch_to_register.first.click()
                            await asyncio.sleep(1)
                        
                        # 3. Try clicking Register button again (maybe first click missed)
                        modal = page.locator('.mantine-Modal-content')
                        if await modal.count() == 0:
                            print("Modal did not open. Trying to click Register button again...")
                            try:
                                await register_btn.evaluate("element => element.click()")
                            except:
                                pass
                            await asyncio.sleep(2)
                        
                        # 4. Final attempt to find input
                        # Try finding generic input again with updated selectors
                        email_input = page.get_by_placeholder("电子邮箱")
                        if await email_input.count() == 0:
                            email_input = page.locator('input[type="text"]').or_(page.locator('input[type="email"]')).first
                        
                        try:
                            await expect(email_input.first).to_be_visible(timeout=5000)
                        except:
                             print("Still cannot find email input. Dumping page state...")
                             # Dump buttons to see what IS there
                             try:
                                 buttons = await page.locator('button').all_inner_texts()
                                 print(f"Buttons found: {buttons[:20]}...") 
                             except:
                                 print("Could not list buttons.")
                             await page.screenshot(path="debug_final_fail.png")
                             close_bitbrowser_api(browser_id)
                             delete_bitbrowser_window(browser_id)
                             return False, "Could not find email input", {}

                    try:
                        print("Email input found. Fetching email...")
                        
                        # Get Email NOW (after confirming input exists)
                        email, token = get_temp_email()
                        if not email:
                            print("Could not get email. Retrying...")
                            
                            # Cleanup before retry
                            close_bitbrowser_api(browser_id)
                            delete_bitbrowser_window(browser_id)
                            if session_index < len(BITBROWSER_IDS):
                                BITBROWSER_IDS[session_index] = None
                                
                            retry_count += 1
                            continue
                        
                        print(f"Token: {token}")
                        await email_input.first.fill(email)
                        print("Email filled.")
                        
                        # Click Get Code
                        
                        # Try updated selector strategies for "Get Code"
                        # It might be "获取验证码" or "Get Code" or "使用邮箱继续"
                        # User confirmed: "使用邮箱继续" (id="emailLogin") triggers the email.
                        get_code_btn = page.locator('button').filter(has_text='获取验证码') \
                            .or_(page.locator('button').filter(has_text='Get Code')) \
                            .or_(page.locator('button').filter(has_text='使用邮箱继续')) \
                            .or_(page.locator('#emailLogin'))
                        
                        # If not found, try finding the button next to the email input
                        if await get_code_btn.count() == 0:
                             # Sometimes it's a sibling of the input
                             get_code_btn = page.locator('.mantine-Input-wrapper').locator('..').locator('button')

                        if await get_code_btn.count() > 0:
                            # Ensure we click the visible one
                            if await get_code_btn.first.is_visible():
                                 await get_code_btn.first.click()
                                 print("Clicked Get Code.")
                            else:
                                 print("Get Code button found but not visible.")
                                 # Dump buttons for debugging
                                 buttons = await page.locator('button').all_inner_texts()
                                 print(f"All buttons: {buttons}")
                                 await page.screenshot(path="debug_get_code_fail.png")
                                 close_bitbrowser_api(browser_id)
                                 delete_bitbrowser_window(browser_id)
                                 return False, "Get Code button not visible", {}
                        else:
                            print("Get Code button not found.")
                            # Dump buttons for debugging
                            buttons = await page.locator('button').all_inner_texts()
                            print(f"All buttons: {buttons}")
                            await page.screenshot(path="debug_get_code_fail.png")
                            close_bitbrowser_api(browser_id)
                            delete_bitbrowser_window(browser_id)
                            return False, "Get Code button not found", {}
                            
                        # Wait and Poll for Code
                        print(f"{Fore.YELLOW}Waiting for verification code...{Style.RESET_ALL}")
                        verification_code = None
                        for i in range(20): # 60 seconds approx (20 * 3)
                            await asyncio.sleep(3)
                            verification_code = get_email_code(token)
                            if verification_code:
                                print(f"{Fore.GREEN}Code received: {verification_code}{Style.RESET_ALL}")
                                break
                            print(f"Waiting for code... ({i+1}/20)")
                        
                        if verification_code:
                            # Input Code
                            # Usually 6 inputs
                            print("Inputting code...")
                            # Try finding inputs by index or class
                            # Selector from original: @data-testid=undefined-input-{idx}
                            
                            for idx, digit in enumerate(verification_code):
                                input_box = page.get_by_test_id(f'undefined-input-{idx}')
                                if await input_box.count() > 0:
                                    await input_box.fill(digit)
                                else:
                                    # Fallback: try finding all inputs in the verification container
                                    inputs = page.locator('.mantine-PinInput-input')
                                    if await inputs.count() >= 6:
                                        await inputs.nth(idx).fill(digit)
                            
                            print("Code entered.")
                            
                            await asyncio.sleep(2)
                            
                            if ready_payload is not None:
                                ready_payload["email"] = email

                            try:
                                await lovart_prepare_canvas_page(page, timeout_ms=25000)
                            except Exception as e:
                                msg = f"登陆后页面初始化失败: {e}"
                                print(f"{msg}. Retrying...")
                                
                                # Cleanup before retry
                                close_bitbrowser_api(browser_id)
                                delete_bitbrowser_window(browser_id)
                                if session_index < len(BITBROWSER_IDS):
                                    BITBROWSER_IDS[session_index] = None
                                    
                                retry_count += 1
                                continue
                                # if ready_payload is not None:
                                #     ready_payload["error"] = msg
                                # if ready_event is not None:
                                #     ready_event.set()
                                # return False, msg, {}

                            if keep_alive_after_code:
                                print(f"登陆成功 (Session {session_index})，浏览器保持存活。")
                                with _lovart_sessions_lock:
                                    if session_index < len(_lovart_sessions):
                                        sess = _lovart_sessions[session_index]
                                        busy_lock = sess.get("busy_lock")
                                        _lovart_sessions[session_index] = {
                                            "thread": threading.current_thread(),
                                            "loop": asyncio.get_running_loop(),
                                            "browser": browser,
                                            "context": context,
                                            "page": page,
                                            "busy_lock": busy_lock if busy_lock else Lock(),
                                            "bitbrowser_id": browser_id,
                                        }
                                if ready_event is not None:
                                    ready_event.set()
                                while True:
                                    await asyncio.sleep(3600)

                            if ready_event is not None:
                                ready_event.set()
                            print("登陆成功。")
                            return True, "登陆成功", {"email": email}
                       
                                
                        else:
                            print("Failed to receive code.")
                            close_bitbrowser_api(browser_id)
                            delete_bitbrowser_window(browser_id)
                            return False, "Failed to receive code", {}
                            
                    except Exception as e:
                        print(f"Email input interaction failed: {e}")
                        close_bitbrowser_api(browser_id)
                        delete_bitbrowser_window(browser_id)
                        return False, f"Email input interaction failed: {e}", {}
                except Exception as e:
                     print(f"Inner loop exception: {e}")
                     import traceback
                     traceback.print_exc()
                     
                     # Cleanup before retry
                     close_bitbrowser_api(browser_id)
                     delete_bitbrowser_window(browser_id)
                     if session_index < len(BITBROWSER_IDS):
                         BITBROWSER_IDS[session_index] = None
                         
                     retry_count += 1
                     continue

            except Exception as e:
                print(f"{Fore.RED}Error in automation loop: {e}{Style.RESET_ALL}")
                import traceback
                traceback.print_exc()
                
                # Cleanup before retry
                close_bitbrowser_api(browser_id)
                delete_bitbrowser_window(browser_id)
                if session_index < len(BITBROWSER_IDS):
                    BITBROWSER_IDS[session_index] = None
                    
                retry_count += 1
                continue
            
            # If we reach here, successful execution usually returns earlier or loop continues
            print("Session ended.")
            # If we are here, we are not keeping alive.
            if not keep_alive_after_code:
                close_bitbrowser_api(browser_id)
                delete_bitbrowser_window(browser_id) # Free up quota
            break
            
    return False, "Max retries exceeded or unknown error", {}

async def run_generate_image_on_page(page: Page, start_frame_image_path: str, prompt: str, resolution: str = "2K", ratio: str = "16:9", session_index: int = -1, image_paths: list = None):
    prefix = f"[Session {session_index}] [lovart]" if session_index >= 0 else "[lovart]"
    await lovart_ensure_viewport(page, width=_LOVART_VIEWPORT["width"], height=_LOVART_VIEWPORT["height"])
    if not page.url.startswith("https://www.lovart.ai/canvas"):
        await page.goto("https://www.lovart.ai/canvas", timeout=60000)

    points = await _lovart_get_points_async(page)
    # Check if points are sufficient (assume same requirement as video or similar)
    if points < 10: # Image generation might be cheaper
         # Return error if points are too low, similar to video generation
         return False, "积分低于10", {"points": points, "low_points": True} 

    # Check for limited-time offer pop-up and skip (User request)
    try:
        skip_btn = page.locator("button:has-text('Skip for now')").first
        if await skip_btn.is_visible():
            print(f"{prefix} Found 'Skip for now' pop-up button. Clicking...")
            await skip_btn.click()
            await asyncio.sleep(1)
    except Exception as e:
        print(f"{prefix} Error checking pop-up: {e}")

    # 1. Switch to Image Mode
    print(f"{prefix} Switching to image mode...")
    image_menu_btn = page.get_by_test_id("generate-menu-image")
    
    if not await image_menu_btn.is_visible():
        # Image Icon contains a circle: M7.499 6a1.5 1.5
        image_path_fragment = "M7.499 6a1.5 1.5"
        fallback_btn = page.locator(f'button:has(svg path[d*="{image_path_fragment}"])').first
        if await fallback_btn.is_visible():
            print(f"{prefix} Using fallback menu button (Image)...")
            image_menu_btn = fallback_btn
            
    await expect(image_menu_btn).to_be_visible(timeout=10000)
    await image_menu_btn.click()
    await asyncio.sleep(1)

    await lovart_close_right_bottom_popup(page)
    await lovart_scroll_canvas_up(page, pixels=100)

    # 2. Upload Image(s)
    # Combine start_frame_image_path into image_paths if not present
    all_images = []
    if image_paths:
        all_images.extend(image_paths)
    if start_frame_image_path and start_frame_image_path not in all_images:
        all_images.insert(0, start_frame_image_path)
    
    if all_images:
        print(f"{prefix} Uploading {len(all_images)} reference images...")
        ref_btn = page.get_by_test_id("generator-image-reference-button")
        
        # Fallback: SVG Path for Upload Button (from user report)
        if not await ref_btn.is_visible():
            # Use XPath to find button with specific SVG path
            # Path fragment: M10.866 8.662
            # Also check for class 'reset-svg' to ensure it's a button
            fallback_ref_btn = page.locator('xpath=//button[contains(@class, "reset-svg") and .//path[starts-with(@d, "M10.866 8.662")]]').first
            if await fallback_ref_btn.is_visible():
                 print(f"{prefix} Using fallback upload button (XPath)...")
                 ref_btn = fallback_ref_btn
            else:
                # Try generic SVG path fragment match as last resort
                upload_path_fragment = "M10.866 8.662"
                fallback_ref_btn_2 = page.locator(f'button:has(svg path[d*="{upload_path_fragment}"])').first
                if await fallback_ref_btn_2.is_visible():
                     print(f"{prefix} Using fallback upload button (Generic SVG)...")
                     ref_btn = fallback_ref_btn_2

        await expect(ref_btn).to_be_visible(timeout=10000)
        
        # Debug: Print what button we are clicking
        try:
            btn_html = await ref_btn.evaluate("el => el.outerHTML")
            print(f"{prefix} Clicking upload button: {btn_html[:300]}...") 
        except Exception as e:
            print(f"{prefix} Could not print upload button HTML: {e}")

        # Robust click logic
        upload_option = None
        for attempt in range(3):
            print(f"{prefix} Clicking upload button (attempt {attempt+1})...")
            try:
                await ref_btn.hover()
                await asyncio.sleep(0.2)
                await ref_btn.click(force=True)
            except Exception as e:
                print(f"{prefix} Standard click failed: {e}. Trying JS click.")
                try:
                    await ref_btn.evaluate("el => el.click()")
                except Exception as e2:
                    print(f"{prefix} JS click also failed: {e2}")
            
            await asyncio.sleep(1)

            # Check if menu opened
            opt1 = page.get_by_test_id("generator-image-reference-option-uploadImageFromLocal")
            if await opt1.is_visible():
                upload_option = opt1
                print(f"{prefix} Upload menu opened (found test-id).")
                break
            
            # Fallback option check
            opt2 = page.locator('div[role="menuitem"], button[role="menuitem"]').filter(has_text=re.compile(r"上传|Upload")).first
            if await opt2.is_visible():
                upload_option = opt2
                print(f"{prefix} Upload menu opened (found text fallback).")
                break
        
        if not upload_option:
             print("[lovart] Upload menu did not open after retries.")
             # Define it anyway so expect() fails with a clear timeout error
             upload_option = page.get_by_test_id("generator-image-reference-option-uploadImageFromLocal")

        await expect(upload_option).to_be_visible(timeout=5000)

        async with page.expect_file_chooser() as fc_info:
            await upload_option.hover()
            await asyncio.sleep(0.2)
            await upload_option.evaluate("(el) => el.click()")
        file_chooser = await fc_info.value
        
        # Upload multiple files at once if supported, or verify if Lovart supports multiple selection
        # Assuming set_files supports list for multiple files
        await file_chooser.set_files(all_images)
        
        # Wait for upload to complete (simple delay + network idle check)
        print(f"{prefix} Waiting for image upload to complete...")
        await asyncio.sleep(5)
        try:
             await page.wait_for_load_state("networkidle", timeout=3000)
        except:
             pass

    # ---------------------------------------------------------
    # NEW: Reverse Engineering API Implementation
    # ---------------------------------------------------------
    
    # Init result container (Same as old code)
    result = {
        "image_url": None,
        "cover_url": None,
        "network_hits": [],
    }
    
    print(f"{prefix} [API MODE] Starting direct API generation...")

    # 1. Get Project ID
    import urllib.parse
    project_id = None
    try:
        parsed = urllib.parse.urlparse(page.url)
        project_id = urllib.parse.parse_qs(parsed.query).get('projectId', [None])[0]
    except Exception as e:
        print(f"{prefix} Failed to parse URL for projectId: {e}")

    # 2. Get Token
    cookies = await page.context.cookies()
    token = next((c['value'] for c in cookies if c['name'] == 'usertoken'), None)
    
    if not project_id:
        print(f"{prefix} ⚠️ Project ID not found in URL. Attempting to fetch from local storage or wait...")
        # Fallback: could try to execute script to get it
    
    # 3. Get Uploaded Image URL
    # We uploaded images using UI above. Now we need to find their URLs in the DOM.
    target_image_url = None
    if start_frame_image_path or image_paths:
        print(f"{prefix} Searching for uploaded image URL in DOM...")
        for _ in range(15):
             # Look for images in artifacts/user path
             imgs = await page.locator('img[src*="/artifacts/user/"]').all()
             if imgs:
                 # Get the last one as it's likely the one we just uploaded
                 target_image_url = await imgs[-1].get_attribute("src")
                 print(f"{prefix} Found uploaded image: {target_image_url}")
                 break
             await asyncio.sleep(1)
        
        if not target_image_url:
            print(f"{prefix} ⚠️ Could not find uploaded image URL. Proceeding without reference image (might fail if required).")

    # ---------------------------------------------------------
    # PROBE: Search for Signature Generation Logic
    # ---------------------------------------------------------
    print(f"{prefix} Probing for X-Client-Signature logic in loaded scripts...")
    signature_info = await page.evaluate("""async () => {
        const scripts = Array.from(document.querySelectorAll('script[src]'));
        for (const script of scripts) {
            // Filter for likely candidates
            if (script.src.includes('lovart') || script.src.includes('index') || script.src.includes('app') || script.src.includes('umi') || script.src.includes('pages')) {
                try {
                    const resp = await fetch(script.src);
                    const text = await resp.text();
                    // Search for the header string
                    const idx = text.toLowerCase().indexOf('x-client-signature');
                    if (idx !== -1) {
                        const start = Math.max(0, idx - 800);
                        const end = Math.min(text.length, idx + 1200);
                        return { src: script.src, snippet: text.substring(start, end) };
                    }
                } catch (e) {}
            }
        }
        return null;
    }""")

    if signature_info:
        print(f"{prefix} ✅ Found signature code in {signature_info['src']}")
        # Clean up snippet for printing
        snippet = signature_info['snippet'].replace('\n', ' ').replace('\r', '')
        print(f"{prefix} Snippet: {snippet[:2000]}...") # Limit length
    else:
        print(f"{prefix} ⚠️ Signature code not found in scripts.")
    
    # 4. Send API Request
    if token and project_id:
        api_url = "https://lgw.lovart.ai/v1/generator/tasks"
        
        # Clean the image URL (remove query params like ?x-oss-process...)
        clean_image_url = None
        if target_image_url:
             clean_image_url = target_image_url.split('?')[0]
             print(f"{prefix} Cleaned image URL: {clean_image_url}")

        api_images_list = []
        if clean_image_url:
            api_images_list.append(clean_image_url)
            
        payload = {
            "project_id": project_id,
            "generator_name": "vertex/anon-bob",
            "input_args": {
                "prompt": prompt,
                "aspect_ratio": ratio if ratio else "1:1",
                "resolution": resolution if resolution else "2K",
                "image": api_images_list
            }
        }
        
        # Use page.evaluate to execute fetch in the browser context.

        # This ensures we share the exact network stack/proxy/cookies of the page.
        # We also attempt to mock some headers.
        try:
            print(f"{prefix} Sending POST to {api_url} via page.evaluate (fetch)...")
            
            # We inject a small script to perform the fetch
            # Note: We now inject the signature generation logic via Webpack hook
            fetch_result = await page.evaluate("""async ({url, payload, token}) => {
                try {
                    // 1. Define Helper to get Signature via Webpack Hook
                    const getSignature = async (timestamp, uuid) => {
                         return new Promise((resolve, reject) => {
                            // Find the global webpack chunk array
                            // Name might vary, but user logs showed 'webpackChunk_shakkerai_web_pro'
                            const chunkName = 'webpackChunk_shakkerai_web_pro';
                            if (!window[chunkName]) {
                                reject("Webpack chunk global " + chunkName + " not found");
                                return;
                            }
                            
                            // Hook into Webpack to steal the require function
                            window[chunkName].push([
                                [Symbol("stealer")], 
                                {}, 
                                (r) => {
                                    try {
                                        // Module 72736 is the one exporting 'H' (signature function)
                                        // based on our analysis of common.98186913.js
                                        const mod = r(72736);
                                        if (mod && mod.H) {
                                            // H(timestamp, uuid, param3, param4)
                                            // param3 and param4 appear to be empty strings in usage
                                            const sig = mod.H(timestamp, uuid, "", "");
                                            resolve(sig);
                                        } else {
                                            reject("Module 72736 or function H not found in webpack require");
                                        }
                                    } catch(e) {
                                        reject(e);
                                    }
                                }
                            ]);
                         });
                    };

                    // 2. Prepare Data
                    // Generate UUID without dashes
                    const uuid = (crypto.randomUUID ? crypto.randomUUID() : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
                        var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
                        return v.toString(16);
                    })).replace(/-/g, '');
                    
                    const ts = Date.now().toString();

                    // 3. Generate Signature
                    let signature = "";
                    try {
                        console.log("[In-Page] Attempting to generate signature...");
                        signature = await getSignature(ts, uuid);
                        console.log("[In-Page] Signature generated: " + signature);
                    } catch(e) {
                        console.error("[In-Page] Signature generation failed:", e);
                        return { error: "Signature generation failed: " + e.toString() };
                    }

                    // 4. Send Request
                    console.log("[In-Page] Sending fetch request...");
                    const resp = await fetch(url, {
                        method: 'POST',
                        credentials: 'include', // IMPORTANT: Send cookies
                        headers: {
                            'Content-Type': 'application/json',
                            'token': token,
                            'Accept': 'application/json, text/plain, */*',
                            'x-req-uuid': uuid,
                            'x-send-timestamp': ts,
                            'x-client-signature': signature
                        },
                        body: JSON.stringify(payload)
                    });
                    
                    const text = await resp.text();
                    let json = null;
                    try {
                        json = JSON.parse(text);
                    } catch(e) {}
                    
                    return {
                        status: resp.status,
                        statusText: resp.statusText,
                        data: json,
                        text: text
                    };
                } catch (e) {
                    return { error: e.toString() };
                }
            }""", {"url": api_url, "payload": payload, "token": token})
            
            if fetch_result.get("error"):
                 print(f"{prefix} ❌ Fetch Error inside browser: {fetch_result['error']}")
            elif fetch_result.get("status") == 200:
                resp_data = fetch_result.get("data", {})
                task_id = resp_data.get("data", {}).get("generator_task_id")
                
                if task_id:
                    print(f"{prefix} ✅ Task created: {task_id}. Polling for result...")
                    
                    # Poll using fetch loop as well to be safe
                    poll_url = f"https://lgw.lovart.ai/v1/generator/tasks?task_id={task_id}"
                    
                    for i in range(100): # 5 minutes
                        await asyncio.sleep(3)
                        
                        poll_res = await page.evaluate("""async ({url, token}) => {
                             try {
                                const resp = await fetch(url, {
                                    credentials: 'include',
                                    headers: { 'token': token }
                                });
                                return await resp.json();
                             } catch(e) { return null; }
                        }""", {"url": poll_url, "token": token})
                        
                        if poll_res:
                            status = poll_res.get("data", {}).get("status")
                            
                            if status == "completed":
                                artifacts = poll_res.get("data", {}).get("artifacts", [])
                                if artifacts:
                                    final_url = artifacts[0].get("content")
                                    print(f"{prefix} ✅ Generation Completed: {final_url}")
                                    result["image_url"] = final_url
                                    break
                            elif status == "failed":
                                print(f"{prefix} ❌ Task Failed: {poll_res}")
                                break
                            else:
                                if i % 5 == 0:
                                    print(f"{prefix} Task status: {status}...")
                        else:
                            print(f"{prefix} Poll failed (network error?)")
                else:
                    print(f"{prefix} ❌ Failed to get task_id. Response: {resp_data}")
            else:
                print(f"{prefix} ❌ API Request failed: {fetch_result.get('status')} {fetch_result.get('text')}")
                
        except Exception as e:
            print(f"{prefix} API Exception: {e}")
    else:
        print(f"{prefix} ❌ Cannot use API mode: Missing token or project_id.")

    # ---------------------------------------------------------
    # END API IMPLEMENTATION
    # ---------------------------------------------------------

    """
    # 3. Resolution & Ratio
    print(f"[lovart] Setting Resolution={resolution}, Ratio={ratio}...")
    
    # --- Resolution ---
    # Find button containing "1K", "2K", "4K" text in a span
    # Pattern: span with text matching /^[124]K$/
    # User HTML: <span ...><div ...><span ...>2K</span></div></span>
    # We look for a button containing a span with text "1K", "2K", or "4K"
    res_btn = page.locator('button').filter(has=page.locator('span', has_text=re.compile(r"^[124]K$"))).first
    
    if await res_btn.is_visible():
        current_res = await res_btn.text_content()
        # Clean up text content to check if match
        if resolution not in current_res: 
             print("[lovart] Opening Resolution menu...")
             await res_btn.click()
             await asyncio.sleep(0.5)
             
             # Find menu item
             # Structure: div[role="menuitem"] containing text resolution
             target_res_item = page.locator('div[role="menuitem"]').filter(has=page.locator('span', has_text=resolution)).first
             if await target_res_item.is_visible():
                 await target_res_item.click()
                 print(f"[lovart] Selected resolution: {resolution}")
             else:
                 print(f"[lovart] Resolution option {resolution} not found. Closing menu.")
                 await page.mouse.click(0,0)
             await asyncio.sleep(0.5)
        else:
            print(f"[lovart] Resolution already {resolution}.")
    else:
        print("[lovart] Resolution button not found.")

    # --- Ratio ---
    # Find button containing ratio text "1:1", "16:9", etc.
    # Pattern: div with text matching /^\d+:\d+$/
    # User HTML: <div class="flex items-center gap-1">1:1</div>
    ratio_btn = page.locator('button').filter(has=page.locator('div', has_text=re.compile(r"^\d+:\d+$"))).first
    
    if await ratio_btn.is_visible():
         current_ratio = await ratio_btn.text_content()
         if ratio not in current_ratio:
             print("[lovart] Opening Ratio menu...")
             await ratio_btn.click()
             await asyncio.sleep(0.5)
             
             # Find menu item
             # Structure: div[role="menuitem"] containing text ratio
             target_ratio_item = page.locator('div[role="menuitem"]').filter(has_text=ratio).first
             if await target_ratio_item.is_visible():
                 await target_ratio_item.click()
                 print(f"[lovart] Selected ratio: {ratio}")
             else:
                 print(f"[lovart] Ratio option {ratio} not found. Closing menu.")
                 await page.mouse.click(0,0)
             await asyncio.sleep(0.5)
         else:
             print(f"[lovart] Ratio already {ratio}.")
    else:
        print("[lovart] Ratio button not found.")

    # 4. Prompt
    print("[lovart] Entering prompt...")
    prompt_input = page.get_by_test_id("generator-prompt-input").first
    
    if not await prompt_input.is_visible():
        # Fallback: Textarea with specific placeholder or class
        # User provided: textarea with placeholder="今天我们要创作什么"
        print("[lovart] Using fallback prompt input (textarea)...")
        prompt_input = page.locator('textarea[placeholder="今天我们要创作什么"]').first
        
        if not await prompt_input.is_visible():
             # Fallback 2: Any textarea in the main area?
             prompt_input = page.locator('textarea.ant-input').first
    
    await expect(prompt_input).to_be_visible(timeout=10000)
    await prompt_input.fill(prompt)
    await lovart_scroll_canvas_up(page, pixels=100)

    # 5. Generate & Listen
    context = page.context
    done_event = asyncio.Event()
    click_ts = None
    result = {
        "image_url": None,
        "cover_url": None, # Might not be applicable for image, but keep for consistency
        "network_hits": [],
    }

    import json
    log_file = "lovart_api_logs.jsonl"
    print(f"{prefix} Network logging enabled. Saving to {log_file}")

    async def _on_request(request):
        try:
            # Capture all requests to lovart or api
            if "lovart" in request.url or "api" in request.url:
                req_data = {
                    "type": "request",
                    "url": request.url,
                    "method": request.method,
                    "headers": await request.all_headers(),
                    "post_data": request.post_data,
                    "timestamp": time.time()
                }
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(req_data, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _maybe_add_hit(hit: dict):
        if len(result["network_hits"]) >= 120:
            return
        result["network_hits"].append(hit)

    async def _on_response(response):
        # Log response
        try:
            if "lovart" in response.url or "api" in response.url:
                resp_data = {
                    "type": "response",
                    "url": response.url,
                    "status": response.status,
                    "headers": await response.all_headers(),
                    "timestamp": time.time()
                }
                
                # Try to get body for text/json
                ct = resp_data["headers"].get("content-type", "")
                if "json" in ct or "text" in ct:
                    try:
                        resp_data["body"] = await response.text()
                    except:
                        pass
                
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(resp_data, ensure_ascii=False) + "\n")
        except Exception:
            pass

        nonlocal click_ts
        if click_ts is None:
            return

        try:
            url = response.url or ""
            # Debug: Check for task_id in URL to track progress
            if "task_id=" in url and "lovart" in url:
                print(f"[lovart] Saw request with task_id: {url}")

            rt = response.request.resource_type
            ct = (response.headers or {}).get("content-type", "")
        except Exception:
            return

        # Listen for image results
        if rt in ("fetch", "xhr"):
             try:
                # Need to use json() to parse structured data
                try:
                    data = await response.json()
                except Exception as e:
                    # print(f"[lovart] JSON parse failed for {url}: {e}")
                    data = None

                if data:
                    # Check for "artifacts" in response data
                    # Response structure provided by user:
                    # { "data": { "artifacts": [ { "content": "url...", "type": "image" } ] } }
                    if isinstance(data, dict) and "data" in data:
                        inner_data = data["data"]
                        if isinstance(inner_data, dict) and "artifacts" in inner_data:
                            artifacts = inner_data["artifacts"]
                            print(f"[lovart] Found artifacts in {url}: {len(artifacts) if isinstance(artifacts, list) else 'not list'}")
                            if isinstance(artifacts, list) and len(artifacts) > 0:
                                first_artifact = artifacts[0]
                                if isinstance(first_artifact, dict) and first_artifact.get("type") == "image":
                                    found_url = first_artifact.get("content")
                                    if found_url:
                                        print(f"[lovart] Found image URL in API response (JSON): {found_url}")
                                        result["image_url"] = found_url
                                        done_event.set()
                                        return
                        else:
                            # print(f"[lovart] No artifacts in data for {url}")
                            pass

                # Fallback: Simple regex for image url in JSON text if structure match fails
                # (Keep this as backup or remove if strict JSON parsing is preferred)
                try:
                    text = await response.text()
                except:
                    text = ""
                
                if "lovart" in url or "api" in url:
                     # print(f"[lovart] Checking regex for {url}...")
                     match = re.search(r"https?://[^\s\"']+?\.png", text) or re.search(r"https?://[^\s\"']+?\.jpg", text)
                     if match:
                         # Ensure it's not a thumbnail or icon if possible
                         found_url = match.group(0)
                         # We might need better filtering, but for now let's capture the first likely candidate
                         # after click.
                         # A better way is if the user knows the API endpoint.
                         # Assuming standard behavior: POST -> returns task or result.
                         if "/generate" in url or "/task" in url:
                             print(f"[lovart] Regex matched URL in {url}: {found_url}")
                             # Don't overwrite if we found a better structured one
                             if not result["image_url"]:
                                 # CAUTION: Regex might match input args first!
                                 # User reported getting wrong image. 
                                 # We should check if this URL looks like an artifact or user upload.
                                 if "artifacts/user" in found_url:
                                     print(f"[lovart] Ignoring user artifact URL: {found_url}")
                                 elif "artifacts/generator" in found_url:
                                     print(f"[lovart] Regex found generator artifact: {found_url}")
                                     result["image_url"] = found_url
                                     done_event.set()
                                 else:
                                     print(f"[lovart] Regex found other URL (using as fallback): {found_url}")
                                     result["image_url"] = found_url
                                     done_event.set()
             except Exception as e:
                print(f"[lovart] Error in _on_response processing: {e}")
                pass
        
        # Also check for direct image loading if the UI loads it
        if (".png" in url or ".jpg" in url) and rt == "image":
            # If a large image is loaded after generation
            # This is heuristic.
            pass

    # Better strategy: Wait for the result in the UI or a specific network call.
    # Since we don't know the exact API, let's rely on finding a new image in the UI or network.
    # For now, let's add a basic listener.
    
    # Actually, looking at video generation, it parses JSON for mp4.
    # I'll parse JSON for png/jpg.
    
    # Ensure no stale listeners from previous calls (crucial for correct image detection)
    try:
        context.remove_listener("response", _on_response)
        context.remove_listener("request", _on_request)
    except:
        pass
    context.on("response", _on_response)
    context.on("request", _on_request)
    
    await asyncio.sleep(2)
    generate_btn = page.get_by_test_id("generator-generate-button")
    
    if not await generate_btn.is_visible():
        # Fallback: XPath locator for Generate button (with cost display)
        # User provided: //button[contains(@class, 'reset-svg') and contains(@class, 'min-w-12') and .//div[translate(text(), '0123456789', '') != text()]]
        # Explanation: Checks for button with specific classes and a div child containing digits (points cost)
        # Note: XPath translate check logic provided by user checks if removing digits makes text different (meaning digits exist).
        # We can also use regex in locator or just this xpath.
        print("[lovart] Using fallback generate button (XPath)...")
        generate_btn = page.locator("xpath=//button[contains(@class, 'reset-svg') and contains(@class, 'min-w-12') and .//div[string-length(translate(text(), '0123456789', '')) < string-length(text())]]").first
        
        if not await generate_btn.is_visible():
             # Try simpler check: button with svg and div with text (points)
             # Usually the generate button is the main action button
             generate_btn = page.locator('button.reset-svg.min-w-12').first

    await expect(generate_btn).to_be_visible(timeout=10000)

    click_ts = time.time()
    print(f"{prefix} click generate image: {click_ts}")
    await generate_btn.click()
    
    print(f"{prefix} 🛑 Auto-verification DISABLED. Please resolve the captcha manually in the browser window!")
    print(f"{prefix} ⏳ Waiting up to 5 minutes for manual interaction and image generation...")
    
    # try:
    #     await lovart_handle_security_verification(page, prefix=prefix)
    # except Exception:
    #     pass

    try:
        # Wait for network response (timeout 300s)
        await asyncio.wait_for(done_event.wait(), timeout=300)
    except asyncio.TimeoutError:
        # Fallback: Check UI for result?
        # Maybe the user wants us to just return success if clicked.
        # But obtaining the URL is better.
        pass
    finally:
        context.remove_listener("response", _on_response)
        context.remove_listener("request", _on_request)
    """

    if not result["image_url"]:
         # Try to find the latest image on canvas?
         # This might be complex without specific selectors.
         pass
    
    # Upload to Qiniu if we have a URL
    final_url = result["image_url"]
    if final_url:
        print(f"{prefix} Found image URL, uploading to Qiniu...")
        cdn_url = upload_image_to_qiniu(final_url)
        if cdn_url:
            final_url = cdn_url
            
    return True, "图片生成完成", {
        "points": points,
        "start_frame_image_path": start_frame_image_path,
        "image_url": final_url
    }

async def _lovart_generate_image_async(index: int, page: Page, start_frame_image_path: str, prompt: str, resolution: str = "2K", ratio: str = "16:9", image_paths: list = None):
    if not page:
        return False, "没有可用的浏览器会话，请先调用/register登陆", {}

    success, message, data = await run_generate_image_on_page(
        page=page,
        start_frame_image_path=start_frame_image_path,
        image_paths=image_paths,
        prompt=prompt,
        resolution=resolution,
        ratio=ratio,
        session_index=index
    )
    if not success and data.get("low_points"):
        await _lovart_close_session_async(index)
        return success, message, data

    return success, message, data

def lovart_generate_image(index: int, start_frame_image_path: str, prompt: str, resolution: str = "2K", ratio: str = "16:9", timeout: float = 900.0, image_paths: list = None):
    loop, page = lovart_get_session_by_index(index)
    if not loop or not page or loop.is_closed():
        return False, "没有可用的浏览器会话，请先调用/register登陆", {}
    future = asyncio.run_coroutine_threadsafe(
        _lovart_generate_image_async(
            index=index,
            page=page,
            start_frame_image_path=start_frame_image_path,
            image_paths=image_paths,
            prompt=prompt,
            resolution=resolution,
            ratio=ratio
        ),
        loop,
    )
    return future.result(timeout=timeout)
