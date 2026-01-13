# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request
import asyncio
import threading
import os
import time
import importlib.util
import sys

# Try to import from backend package first, then fallback to local/root import
try:
    from backend.lovart_login import (
        register_lovart_account, 
        lovart_generate_video, 
        lovart_generate_image, 
        lovart_has_session, 
        lovart_close_session, 
        lovart_get_session_by_index,
        lovart_acquire_session,
        lovart_release_session,
        lovart_get_pool_size,
        lovart_cleanup_idle_sessions
    )
    _lovart_login_module_name = "backend.lovart_login"
except ImportError:
    from lovart_login import (
        register_lovart_account, 
        lovart_generate_video, 
        lovart_generate_image, 
        lovart_has_session, 
        lovart_close_session, 
        lovart_get_session_by_index,
        lovart_acquire_session,
        lovart_release_session,
        lovart_get_pool_size,
        lovart_cleanup_idle_sessions
    )
    _lovart_login_module_name = "lovart_login"

# Create Blueprint
lovart_bp = Blueprint('lovart', __name__, url_prefix='/api/lovart')

# _lovart_generate_lock removed
_lovart_init_lock = threading.Lock()

# Background cleanup thread
def _idle_cleanup_loop():
    while True:
        try:
            lovart_cleanup_idle_sessions(max_idle_seconds=600)
        except Exception as e:
            print(f"[lovart] Idle cleanup error: {e}")
        time.sleep(60)

threading.Thread(target=_idle_cleanup_loop, daemon=True).start()

def _normalize_duration_label(duration) -> str:
    if duration is None:
        return ""
    if isinstance(duration, (int, float)):
        duration = int(duration)
        return f"{duration}s"
    if isinstance(duration, str):
        raw = duration.strip()
        if raw.endswith("s"):
            return raw
        if raw.isdigit():
            return f"{raw}s"
        return raw
    return str(duration)

def _is_lovart_hot_reload_enabled() -> bool:
    return os.environ.get('SHUKE_DEV_RELOAD', '').strip().lower() in ('1', 'true', 'yes', 'on')

def _load_lovart_login_dynamic():
    stable_mod = sys.modules.get(_lovart_login_module_name)
    if not stable_mod:
        # Fallback reload
        if _lovart_login_module_name == "backend.lovart_login":
             import backend.lovart_login as stable_mod
        else:
             import lovart_login as stable_mod
             
    module_path = stable_mod.__file__
    module_name = f"{_lovart_login_module_name}_dynamic_{time.time_ns()}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def _ensure_lovart_session():
    # Only ensure at least ONE session is available initially or if all are dead.
    # The pool will grow on demand if we implement that logic, 
    # but for now user requested: "Come 1 request -> init 1 session. Come 2 -> init 2."
    # AND "If not 3 instances, init up to 3".
    # Actually user said: "Don't init 3 at once. One by one as needed."
    
    # Check if we have ANY active session.
    if lovart_has_session():
        return None
        
    # If no session, launch just ONE to start with.
    # Future requests will trigger more launches if they wait too long? 
    # Or should we check pool size vs active count?
    
    # User requirement: "No init 3 browsers. Init according to situation."
    # Since this function is called at start of request, if no session exists, we must launch at least one.
    
    with _lovart_init_lock:
        # Double check inside lock
        if lovart_has_session():
            return None
            
        # Find first empty slot
        target_idx = -1
        pool_size = lovart_get_pool_size()
        for i in range(pool_size):
            if not lovart_has_session(i):
                target_idx = i
                break
        
        if target_idx == -1:
             # Should not happen if lovart_has_session() returned False
             return None

        print(f"[lovart] Initializing session {target_idx} (On Demand)...")
        
        ready_event = threading.Event()
        ready_payload = {}
        
        def run_login():
            try:
                ok, msg, data = asyncio.run(
                    register_lovart_account(
                        keep_alive_after_code=True,
                        ready_event=ready_event,
                        ready_payload=ready_payload,
                        session_index=target_idx
                    )
                )
                if not ok:
                    ready_payload["error"] = msg
                    if not ready_event.is_set():
                        ready_event.set()
            except Exception as e:
                ready_payload["error"] = str(e)
                ready_event.set()

        threading.Thread(target=run_login, daemon=True).start()
        
        if not ready_event.wait(timeout=600):
            return jsonify({"status": "error", "message": "自动登陆超时", "data": {}}), 504
            
        if ready_payload.get("error"):
            return jsonify({"status": "error", "message": ready_payload["error"], "data": {}}), 500
            
        return None

def _ensure_more_sessions_if_needed():
    """
    Check if we need to scale up.
    Called when we successfully acquired a session or are waiting?
    Actually, user wants "Come 2 -> Init 2".
    So if we have 1 active session and it is BUSY, and we have empty slots, we should launch another one.
    """
    pool_size = lovart_get_pool_size()
    
    # Count active and busy
    active_count = 0
    busy_count = 0
    first_empty_idx = -1
    
    # We need to access internal state or expose a helper
    # lovart_has_session checks if thread is alive.
    # We need to know if it is locked.
    
    # Let's trust lovart_acquire_session to handle distribution, 
    # but here we need to trigger launch if we are saturated.
    
    # Simple logic: If all current active sessions are busy, and we have room, launch one more.
    # This requires checking lock status without acquiring.
    
    # But _ensure_lovart_session is called BEFORE acquire.
    # So we should modify _ensure_lovart_session to be "Ensure we have capacity".
    pass

def _ensure_capacity():
    """
    Ensures there is at least one available (not busy) session, OR launches a new one if possible.
    """
    pool_size = lovart_get_pool_size()
    
    # 1. Check current state
    active_indices = []
    busy_indices = []
    empty_indices = []
    
    for i in range(pool_size):
        if lovart_has_session(i):
            active_indices.append(i)
            # Check if busy (this is a bit hacky, accessing private lock, but we need it)
            # Or we add a helper in lovart_login
            # For now, let's assume if we can't acquire immediately, it might be busy.
        else:
            empty_indices.append(i)
            
    if not empty_indices:
        return # Max capacity reached
        
    # If we have empty slots, we should check if we need to launch.
    # User logic: "Come 2 requests -> Init 2".
    # This implies if current active sessions are likely to be busy, launch a new one.
    # Since we are about to process a request, we effectively need 1 slot.
    # If all active slots are busy, we launch a new one.
    
    # We need a way to know if active sessions are busy.
    # Let's try to acquire non-blocking on all active sessions.
    # If we find one free, good. If not, launch new.
    
    idx, loop, page = lovart_acquire_session(timeout=0.1)
    if idx is not None:
        # We found a free one! Release it immediately.
        lovart_release_session(idx)
        return # We have capacity
        
    # If we reached here, all active sessions are busy (or there are none).
    # And we know we have empty_indices.
    # So Launch one!
    
    target_idx = empty_indices[0]
    
    # Check lock to avoid race condition where another thread is already launching this index
    # We use _lovart_init_lock for launching.
    
    # We launch asynchronously to not block the current request too much?
    # No, the current request needs a session. If we launch async, it will wait in acquire().
    # So we should launch and wait for it.
    
    print(f"[lovart] All active sessions busy. Scaling up: Initializing session {target_idx}...")
    
    with _lovart_init_lock:
        # Re-check inside lock
        if lovart_has_session(target_idx):
            return
            
        ready_event = threading.Event()
        ready_payload = {}
        
        def run_login():
            try:
                ok, msg, data = asyncio.run(
                    register_lovart_account(
                        keep_alive_after_code=True,
                        ready_event=ready_event,
                        ready_payload=ready_payload,
                        session_index=target_idx
                    )
                )
                if not ok:
                    ready_payload["error"] = msg
                    if not ready_event.is_set():
                        ready_event.set()
            except Exception as e:
                ready_payload["error"] = str(e)
                ready_event.set()

        threading.Thread(target=run_login, daemon=True).start()
        
        if not ready_event.wait(timeout=600):
             print(f"[lovart] Scale up failed for session {target_idx}: Timeout")
             return
            
        if ready_payload.get("error"):
             print(f"[lovart] Scale up failed for session {target_idx}: {ready_payload['error']}")
             return
             
    return

def _run_generate_video(index: int, duration_label: str, start_frame_image_path: str, prompt: str):
    if _is_lovart_hot_reload_enabled():
        loop, page = lovart_get_session_by_index(index)
        if not loop or not page:
            return False, "没有可用的浏览器会话，请先调用/register登陆", {}

        dynamic_mod = _load_lovart_login_dynamic()
        run_fn = getattr(dynamic_mod, "run_generate_video_on_page", None)
        if not run_fn:
            return False, "热加载失败: 缺少 run_generate_video_on_page", {}

        future = asyncio.run_coroutine_threadsafe(
            run_fn(
                page=page,
                duration_label=duration_label,
                start_frame_image_path=start_frame_image_path,
                prompt=prompt,
                session_index=index
            ),
            loop,
        )
        return future.result(timeout=900)

    return lovart_generate_video(
        index=index,
        duration_label=duration_label,
        start_frame_image_path=start_frame_image_path,
        prompt=prompt,
    )

def _run_generate_image(index: int, start_frame_image_path: str, prompt: str, resolution: str = "2K", ratio: str = "16:9"):
    if _is_lovart_hot_reload_enabled():
        loop, page = lovart_get_session_by_index(index)
        if not loop or not page:
            return False, "没有可用的浏览器会话，请先调用/register登陆", {}

        dynamic_mod = _load_lovart_login_dynamic()
        run_fn = getattr(dynamic_mod, "run_generate_image_on_page", None)
        if not run_fn:
            return False, "热加载失败: 缺少 run_generate_image_on_page", {}

        future = asyncio.run_coroutine_threadsafe(
            run_fn(
                page=page,
                start_frame_image_path=start_frame_image_path,
                prompt=prompt,
                resolution=resolution,
                ratio=ratio,
                session_index=index
            ),
            loop,
        )
        return future.result(timeout=900)

    return lovart_generate_image(
        index=index,
        start_frame_image_path=start_frame_image_path,
        prompt=prompt,
        resolution=resolution,
        ratio=ratio
    )

@lovart_bp.route('/register', methods=['POST'])
def api_register_lovart():
    try:
        ready_event = threading.Event()
        ready_payload = {}

        def run_login():
            try:
                ok, msg, data = asyncio.run(
                    register_lovart_account(
                        keep_alive_after_code=True,
                        ready_event=ready_event,
                        ready_payload=ready_payload,
                    )
                )
                if not ok:
                    ready_payload["error"] = msg
                    if not ready_event.is_set():
                        ready_event.set()
            except Exception as e:
                ready_payload["error"] = str(e)
                ready_event.set()

        threading.Thread(target=run_login, daemon=True).start()

        if not ready_event.wait(timeout=600):
            return jsonify({"status": "error", "message": "等待验证码输入超时", "data": {}}), 504

        if ready_payload.get("error"):
            return jsonify({"status": "error", "message": ready_payload["error"], "data": {}}), 500

        return jsonify({"status": "success", "message": "登陆成功", "data": {"email": ready_payload.get("email")}}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@lovart_bp.route('/generate_video', methods=['POST'])
def api_generate_video():
    try:
        # with _lovart_generate_lock: # Removed global lock
        payload = request.get_json(silent=True) or {}
        duration_label = _normalize_duration_label(payload.get("duration"))
        start_frame_image_path = (payload.get("start_frame_image_path") or "").strip()
        prompt = (payload.get("prompt") or "").strip()

        missing = []
        if not duration_label:
            missing.append("duration")
        if not start_frame_image_path:
            missing.append("start_frame_image_path")
        if not prompt:
            missing.append("prompt")
        if missing:
            return jsonify({"status": "error", "message": f"缺少参数: {', '.join(missing)}", "data": {}}), 400

        ensure_err = _ensure_lovart_session()
        if ensure_err:
            return ensure_err
            
        # Ensure capacity (Scale up if needed)
        _ensure_capacity()
        
        # Retry loop for low points
        max_retries = 3
        idx = None
        
        for attempt in range(max_retries):
            # 1. Acquire Session
            idx, loop, page = lovart_acquire_session(timeout=600)
            if idx is None:
                 if not lovart_has_session():
                     return jsonify({"status": "error", "message": "会话已断开，请重试"}), 500
                 if attempt < max_retries - 1:
                     continue
                 return jsonify({"status": "error", "message": "系统繁忙，请稍后再试"}), 503

            # 2. Run Generation
            try:
                success, message, data = _run_generate_video(
                    index=idx,
                    duration_label=duration_label,
                    start_frame_image_path=start_frame_image_path,
                    prompt=prompt,
                )
                
                if (not success) and isinstance(data, dict) and data.get("low_points"):
                    # Session is already closed inside _run_generate_video if low points
                    # Release lock on this dead session slot
                    lovart_release_session(idx)
                    idx = None
                    
                    # Try to replenish pool (restart dead session)
                    ensure_err = _ensure_lovart_session()
                    if ensure_err:
                        # If we can't restart session, maybe abort or try another existing session?
                        # Let's abort this retry attempt but maybe next loop iteration finds another session?
                        # But ensure_err usually means something critical.
                        data.pop("low_points", None)
                        return ensure_err
                    
                    # Continue to next attempt to get a new session
                    continue

                if success:
                    if isinstance(data, dict) and data.get("low_points"):
                        data.pop("low_points", None)
                    return jsonify({"status": "success", "message": message, "data": data}), 200
                
                # Other error (not low points)
                if isinstance(data, dict) and data.get("low_points"):
                    data.pop("low_points", None)
                return jsonify({"status": "error", "message": message, "data": data}), 500

            finally:
                if idx is not None:
                    lovart_release_session(idx)
                    idx = None

        return jsonify({"status": "error", "message": "重试多次失败 (积分不足或系统繁忙)", "data": {}}), 500

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@lovart_bp.route('/generate_image', methods=['POST'])
def api_generate_image():
    temp_file_path = None
    try:
        # with _lovart_generate_lock: # Removed global lock
        payload = request.get_json(silent=True) or {}
        start_frame_image_path = (payload.get("start_frame_image_path") or "").strip()
        start_frame_image_base64 = (payload.get("start_frame_image_base64") or "").strip()
        prompt = (payload.get("prompt") or "").strip()
        resolution = (payload.get("resolution") or "2K").strip()
        ratio = (payload.get("ratio") or "16:9").strip()

        missing = []
        if not prompt:
            missing.append("prompt")
        if missing:
            return jsonify({"status": "error", "message": f"缺少参数: {', '.join(missing)}", "data": {}}), 400

        # Handle Base64 Image
        import base64
        import tempfile
        import uuid
        
        final_image_path = start_frame_image_path
        if start_frame_image_base64:
            try:
                # Remove header if present (e.g., data:image/png;base64,...)
                if "," in start_frame_image_base64:
                    start_frame_image_base64 = start_frame_image_base64.split(",", 1)[1]
                
                image_data = base64.b64decode(start_frame_image_base64)
                
                # Create temp file
                # Use absolute path for temp file to avoid issues
                temp_dir = tempfile.gettempdir()
                temp_filename = f"lovart_upload_{uuid.uuid4()}.png"
                temp_file_path = os.path.join(temp_dir, temp_filename)
                
                with open(temp_file_path, "wb") as f:
                    f.write(image_data)
                
                final_image_path = temp_file_path
            except Exception as e:
                return jsonify({"status": "error", "message": f"Base64解码失败: {str(e)}", "data": {}}), 400

        ensure_err = _ensure_lovart_session()
        if ensure_err:
            return ensure_err

        # Ensure capacity (Scale up if needed)
        _ensure_capacity()
        
        # Retry loop for low points
        max_retries = 3
        idx = None
        
        for attempt in range(max_retries):
            # 1. Acquire Session
            idx, loop, page = lovart_acquire_session(timeout=600)
            if idx is None:
                 if not lovart_has_session():
                     return jsonify({"status": "error", "message": "会话已断开，请重试"}), 500
                 if attempt < max_retries - 1:
                     continue
                 return jsonify({"status": "error", "message": "系统繁忙，请稍后再试"}), 503
            
            # 2. Run Generation
            try:
                success, message, data = _run_generate_image(
                    index=idx,
                    start_frame_image_path=final_image_path,
                    prompt=prompt,
                    resolution=resolution,
                    ratio=ratio
                )
                
                if (not success) and isinstance(data, dict) and data.get("low_points"):
                    # Session is already closed inside _run_generate_image if low points
                    # Release lock on this dead session slot
                    lovart_release_session(idx)
                    idx = None

                    # Try to replenish pool (restart dead session)
                    ensure_err = _ensure_lovart_session()
                    if ensure_err:
                        data.pop("low_points", None)
                        return ensure_err

                    # Continue to next attempt
                    continue

                if success:
                    if isinstance(data, dict) and data.get("low_points"):
                        data.pop("low_points", None)
                    return jsonify({"status": "success", "message": message, "data": data}), 200
                
                # Other error
                if isinstance(data, dict) and data.get("low_points"):
                    data.pop("low_points", None)
                return jsonify({"status": "error", "message": message, "data": data}), 500

            finally:
                if idx is not None:
                    lovart_release_session(idx)
                    idx = None
                    
        return jsonify({"status": "error", "message": "重试多次失败 (积分不足或系统繁忙)", "data": {}}), 500

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        # Cleanup temp file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except:
                pass

@lovart_bp.route('/v1/images/generations', methods=['POST'])
def api_generate_image_openai():
    """
    OpenAI 兼容的生图接口
    映射逻辑:
    - prompt -> prompt
    - size -> ratio (1024x1024->1:1, 1792x1024->16:9, 1024x1792->9:16)
    - n -> 忽略，默认生成1张
    - response_format -> 仅支持 url
    """
    temp_file_path = None
    try:
        payload = request.get_json(silent=True) or {}
        
        # 1. 解析 OpenAI 参数
        prompt = (payload.get("prompt") or "").strip()
        size = (payload.get("size") or "1024x1024").strip()
        
        # 扩展参数：支持通过 prompt 或额外字段传递 Base64 参考图
        # 虽然 OpenAI 标准不支持参考图，但为了兼容性，我们允许在 extra_body 或特定字段传递
        start_frame_image_base64 = (payload.get("start_frame_image_base64") or "").strip()
        
        # 映射 Size 到 Ratio
        ratio = "1:1" # 默认 1024x1024
        if size == "1792x1024":
            ratio = "16:9"
        elif size == "1024x1792":
            ratio = "9:16"
        elif size == "1024x768":
            ratio = "4:3"
        elif size == "768x1024":
            ratio = "3:4"
        
        # 固定分辨率为 2K (Lovart 默认质量较高)
        resolution = "2K"

        missing = []
        if not prompt:
            missing.append("prompt")
        if missing:
            return jsonify({
                "error": {
                    "code": "invalid_parameter",
                    "message": f"Missing required parameters: {', '.join(missing)}",
                    "type": "invalid_request_error",
                    "param": None
                }
            }), 400

        # Handle Base64 Image (复用原有逻辑)
        import base64
        import tempfile
        import uuid
        
        final_image_path = ""
        if start_frame_image_base64:
            try:
                if "," in start_frame_image_base64:
                    start_frame_image_base64 = start_frame_image_base64.split(",", 1)[1]
                
                image_data = base64.b64decode(start_frame_image_base64)
                
                temp_dir = tempfile.gettempdir()
                temp_filename = f"lovart_upload_openai_{uuid.uuid4()}.png"
                temp_file_path = os.path.join(temp_dir, temp_filename)
                
                with open(temp_file_path, "wb") as f:
                    f.write(image_data)
                
                final_image_path = temp_file_path
            except Exception as e:
                return jsonify({
                    "error": {
                        "code": "invalid_parameter",
                        "message": f"Base64 decode failed: {str(e)}",
                        "type": "invalid_request_error",
                        "param": "start_frame_image_base64"
                    }
                }), 400

        ensure_err = _ensure_lovart_session()
        if ensure_err:
             # 将原有错误格式转换为 OpenAI 格式
             return jsonify({
                "error": {
                    "code": "server_error",
                    "message": ensure_err.json.get("message", "Session init failed"),
                    "type": "server_error",
                    "param": None
                }
            }), 500

        _ensure_capacity()
        
        max_retries = 3
        idx = None
        
        for attempt in range(max_retries):
            idx, loop, page = lovart_acquire_session(timeout=600)
            if idx is None:
                 if not lovart_has_session():
                     return jsonify({
                        "error": {
                            "code": "server_error",
                            "message": "Session disconnected",
                            "type": "server_error",
                            "param": None
                        }
                    }), 500
                 if attempt < max_retries - 1:
                     continue
                 return jsonify({
                    "error": {
                        "code": "server_busy",
                        "message": "System busy, please try again later",
                        "type": "server_error",
                        "param": None
                    }
                }), 503
            
            try:
                success, message, data = _run_generate_image(
                    index=idx,
                    start_frame_image_path=final_image_path,
                    prompt=prompt,
                    resolution=resolution,
                    ratio=ratio
                )
                
                if (not success) and isinstance(data, dict) and data.get("low_points"):
                    lovart_release_session(idx)
                    idx = None
                    ensure_err = _ensure_lovart_session()
                    if ensure_err:
                         return jsonify({
                            "error": {
                                "code": "server_error",
                                "message": "Failed to recover session",
                                "type": "server_error",
                                "param": None
                            }
                        }), 500
                    continue

                if success:
                    image_url = data.get("image_url")
                    return jsonify({
                        "created": int(time.time()),
                        "data": [
                            {
                                "url": image_url
                            }
                        ]
                    }), 200
                
                # Failed
                return jsonify({
                    "error": {
                        "code": "generation_failed",
                        "message": message,
                        "type": "api_error",
                        "param": None
                    }
                }), 500

            finally:
                if idx is not None:
                    lovart_release_session(idx)
                    idx = None
                    
        return jsonify({
            "error": {
                "code": "timeout",
                "message": "Request timed out or too many retries",
                "type": "server_error",
                "param": None
            }
        }), 500

    except Exception as e:
        return jsonify({
            "error": {
                "code": "internal_error",
                "message": str(e),
                "type": "server_error",
                "param": None
            }
        }), 500
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except:
                pass
