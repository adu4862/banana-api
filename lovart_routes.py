# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request
import asyncio
import threading
import os
import time
import json
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
openai_bp = Blueprint('openai', __name__, url_prefix='/v1')

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

def _truncate_str(value, limit: int = 200):
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    if len(value) <= limit:
        return value
    return value[:limit] + f"...(truncated,{len(value)})"

def _safe_int(value):
    try:
        return int(value)
    except Exception:
        return None

def _sanitize_payload(obj):
    sensitive_keys = {
        "authorization",
        "cookie",
        "set-cookie",
        "password",
        "passwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "apikey",
    }

    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            lk = str(k).lower()
            if lk in sensitive_keys or any(s in lk for s in ("token", "secret", "password", "cookie", "authorization", "key")):
                out[k] = "***"
            else:
                out[k] = _sanitize_payload(v)
        return out
    if isinstance(obj, list):
        return [_sanitize_payload(x) for x in obj[:50]]
    if isinstance(obj, str):
        return _truncate_str(obj, 400)
    return obj

def _log_generate_image_request(route_name: str, payload: dict):
    try:
        ip = request.headers.get("X-Forwarded-For") or request.remote_addr
        ua = request.headers.get("User-Agent", "")

        if not isinstance(payload, dict):
            payload = {"_raw": _truncate_str(payload, 400)}

        start_b64 = payload.get("start_frame_image_base64")
        user_field = payload.get("user")
        assets = payload.get("image_assets")
        if not isinstance(assets, list):
            assets = []

        summarized = {
            "prompt": _truncate_str((payload.get("prompt") or "").strip(), 400),
            "resolution": _truncate_str((payload.get("resolution") or "").strip(), 50),
            "ratio": _truncate_str((payload.get("ratio") or "").strip(), 20),
            "start_frame_image_path": _truncate_str((payload.get("start_frame_image_path") or "").strip(), 260),
            "start_frame_image_base64_len": len(start_b64) if isinstance(start_b64, str) else 0,
            "user_len": len(user_field) if isinstance(user_field, str) else 0,
            "image_assets_count": len(assets),
            "image_assets_lens": [len(x) for x in assets[:20] if isinstance(x, str)],
        }
        summarized = _sanitize_payload(summarized)

        print(
            f"[lovart_routes] {route_name} ip={_truncate_str(ip, 120)} ua={_truncate_str(ua, 160)} "
            f"params={json.dumps(summarized, ensure_ascii=False)}"
        )
    except Exception as e:
        print(f"[lovart_routes] {route_name} param log failed: {e}")

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

def _run_generate_image(index: int, start_frame_image_path: str, prompt: str, resolution: str = "2K", ratio: str = "16:9", image_paths: list = None):
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
                image_paths=image_paths,
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
        ratio=ratio,
        image_paths=image_paths
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
    temp_file_paths = []
    try:
        # with _lovart_generate_lock: # Removed global lock
        payload = request.get_json(silent=True) or {}
        _log_generate_image_request("/api/lovart/generate_image", payload)
        start_frame_image_path = (payload.get("start_frame_image_path") or "").strip()
        start_frame_image_base64 = (payload.get("start_frame_image_base64") or "").strip()
        image_assets = payload.get("image_assets") or []
        
        prompt = (payload.get("prompt") or "").strip()
        resolution = (payload.get("resolution") or "2K").strip()
        ratio = (payload.get("ratio") or "16:9").strip()

        missing = []
        if not prompt:
            missing.append("prompt")
        if missing:
            return jsonify({"status": "error", "message": f"缺少参数: {', '.join(missing)}", "data": {}}), 400

        # Handle Images
        # Priority: image_assets > start_frame_image_base64 > start_frame_image_path
        # We consolidate everything into final_image_paths list
        
        final_image_paths = []
        
        # 1. start_frame_image_path (Legacy, local path)
        if start_frame_image_path:
             final_image_paths.append(start_frame_image_path)

        import base64
        import tempfile
        import uuid
        temp_dir = tempfile.gettempdir()

        # 2. start_frame_image_base64 (Single)
        if start_frame_image_base64:
             try:
                 if "," in start_frame_image_base64:
                     start_frame_image_base64 = start_frame_image_base64.split(",", 1)[1]
                 image_data = base64.b64decode(start_frame_image_base64)
                 temp_filename = f"lovart_upload_legacy_{uuid.uuid4()}.png"
                 t_path = os.path.join(temp_dir, temp_filename)
                 with open(t_path, "wb") as f:
                     f.write(image_data)
                 temp_file_paths.append(t_path)
                 final_image_paths.append(t_path)
             except Exception as e:
                 return jsonify({"status": "error", "message": f"Base64解码失败: {str(e)}", "data": {}}), 400

        # 3. image_assets (Multiple Base64)
        if image_assets and isinstance(image_assets, list):
            for i, b64_str in enumerate(image_assets):
                if not b64_str or not isinstance(b64_str, str):
                    continue
                try:
                    if "," in b64_str:
                        b64_str = b64_str.split(",", 1)[1]
                    image_data = base64.b64decode(b64_str)
                    temp_filename = f"lovart_upload_asset_{uuid.uuid4()}_{i}.png"
                    t_path = os.path.join(temp_dir, temp_filename)
                    with open(t_path, "wb") as f:
                        f.write(image_data)
                    temp_file_paths.append(t_path)
                    final_image_paths.append(t_path)
                except Exception as e:
                    return jsonify({"status": "error", "message": f"image_assets[{i}] Base64解码失败: {str(e)}", "data": {}}), 400
        
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
                    start_frame_image_path=final_image_paths[0] if final_image_paths else "",
                    image_paths=final_image_paths, # Pass full list
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
        for p in temp_file_paths:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except:
                    pass

@openai_bp.route('/images/generations', methods=['POST'])
def api_generate_image_openai():
    """
    OpenAI 兼容的生图接口
    映射逻辑:
    - prompt -> prompt
    - size -> ratio (1024x1024->1:1, 1792x1024->16:9, 1024x1792->9:16)
    - n -> 忽略，默认生成1张
    - response_format -> 仅支持 url
    """
    temp_file_paths = []
    try:
        payload = request.get_json(silent=True) or {}
        _log_generate_image_request("/v1/images/generations", payload)
        
        # 1. 解析 OpenAI 参数
        prompt = (payload.get("prompt") or "").strip()
        size = (payload.get("size") or "1024x1024").strip()
        quality = (payload.get("quality") or "").strip()
        
        # 扩展参数：支持多图上传
        # 兼容 start_frame_image_base64 (单图) 和 image_assets (多图数组)
        start_frame_image_base64 = (payload.get("start_frame_image_base64") or "").strip()
        image_assets = payload.get("image_assets") or []
        user_field = payload.get("user")
        
        # 如果提供了单图字段，且没有提供数组，则将其放入数组
        if start_frame_image_base64 and not image_assets:
            image_assets = [start_frame_image_base64]
            
        # 确保 image_assets 是列表
        if not isinstance(image_assets, list):
            image_assets = []

        if not image_assets and isinstance(user_field, str):
            uf = user_field.strip()
            if uf.startswith("{") or uf.startswith("["):
                try:
                    parsed = json.loads(uf)
                    if isinstance(parsed, dict):
                        parsed_assets = parsed.get("image_assets")
                        parsed_b64 = parsed.get("start_frame_image_base64")
                        if isinstance(parsed_assets, list) and parsed_assets:
                            image_assets = parsed_assets
                        elif isinstance(parsed_b64, str) and parsed_b64.strip():
                            image_assets = [parsed_b64.strip()]
                    elif isinstance(parsed, list) and parsed:
                        image_assets = parsed
                except Exception:
                    pass
            if not image_assets and len(uf) >= 200:
                image_assets = [uf]
        
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
        if quality:
            q = quality.strip().upper()
            if q in ("1K", "2K", "4K"):
                resolution = q

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

        # Handle Base64 Images (Multiple)
        import base64
        import tempfile
        import uuid
        
        final_image_paths = []
        
        if image_assets:
            temp_dir = tempfile.gettempdir()
            for i, b64_str in enumerate(image_assets):
                if not b64_str or not isinstance(b64_str, str):
                    continue
                try:
                    if "," in b64_str:
                        b64_str = b64_str.split(",", 1)[1]
                    
                    image_data = base64.b64decode(b64_str)
                    
                    temp_filename = f"lovart_upload_openai_{uuid.uuid4()}_{i}.png"
                    t_path = os.path.join(temp_dir, temp_filename)
                    
                    with open(t_path, "wb") as f:
                        f.write(image_data)
                    
                    temp_file_paths.append(t_path)
                    final_image_paths.append(t_path)
                except Exception as e:
                    return jsonify({
                        "error": {
                            "code": "invalid_parameter",
                            "message": f"Base64 decode failed for image {i}: {str(e)}",
                            "type": "invalid_request_error",
                            "param": "image_assets"
                        }
                    }), 400

        ensure_err = _ensure_lovart_session()
        if ensure_err:
             # _ensure_lovart_session returns (response, status_code)
             resp, _ = ensure_err
             msg = "Session init failed"
             try:
                 data = resp.get_json()
                 if data and "message" in data:
                     msg = data["message"]
             except:
                 pass

             # 将原有错误格式转换为 OpenAI 格式
             return jsonify({
                "error": {
                    "code": "server_error",
                    "message": msg,
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
                    start_frame_image_path=final_image_paths[0] if final_image_paths else "",
                    image_paths=final_image_paths, # 新增参数
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
                "message": "Request timed out or too many retries (Max retries exceeded)",
                "type": "server_error",
                "param": None
            }
        }), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": {
                "code": "internal_error",
                "message": str(e),
                "type": "server_error",
                "param": None
            }
        }), 500
    finally:
        # Cleanup temp files
        for p in temp_file_paths:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except:
                    pass
