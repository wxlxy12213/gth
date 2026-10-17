"""app_main.py - 桌面独立窗口宿主入口（支持 --debug 开发者热刷新模式）。"""
from __future__ import annotations

import ctypes
import sys
import threading
import time
from pathlib import Path

# 1. 优先挂载 hotfix 热补丁目录（支持免重编覆盖升级）
_APP_ROOT = Path(__file__).resolve().parent
_HOTFIX_DIR = _APP_ROOT / "hotfix"
if _HOTFIX_DIR.is_dir():
    sys.path.insert(0, str(_HOTFIX_DIR))
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

# 2. 开启 Windows 11 高分屏 DPI Per-Monitor 锐利渲染
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import webview
from ui.api_bridge import ApiBridge


def _apply_win32_icon(title: str, ico_path: Path) -> None:
    """使用 Win32 消息为窗口注入原生大/小图标。"""
    time.sleep(0.15)
    try:
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010

        hwnd = ctypes.windll.user32.FindWindowW(None, title)
        if hwnd and ico_path.exists():
            h_sm = ctypes.windll.user32.LoadImageW(None, str(ico_path), IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
            h_lg = ctypes.windll.user32.LoadImageW(None, str(ico_path), IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
            if h_sm:
                ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, h_sm)
            if h_lg:
                ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, h_lg)
    except Exception:
        pass


def main() -> None:
    html_path = _APP_ROOT / "ui" / "workbench.html"
    if not html_path.exists():
        print(f"[ERROR] UI 页面缺失：{html_path}")
        sys.exit(1)

    is_debug = "--debug" in sys.argv
    ico_path = _APP_ROOT / "assets" / "app.ico"
    storage_dir = _APP_ROOT / ".cache" / "webview2"
    storage_dir.mkdir(parents=True, exist_ok=True)

    # 启动时自动剔除 WebView2 Disk Cache，防止本地文件被旧缓存锁死
    cache_data_dir = storage_dir / "EBWebView" / "Default" / "Cache"
    if cache_data_dir.exists():
        try:
            import shutil
            shutil.rmtree(cache_data_dir, ignore_errors=True)
        except Exception:
            pass

    app_title = "个体户填报工作台"
    bridge = ApiBridge()
    window = webview.create_window(
        title=app_title,
        url=str(html_path.resolve()),
        js_api=bridge,
        width=1280,
        height=820,
        min_size=(380, 140),
        background_color="#ffffff",
        text_select=True,
        hidden=True,
    )
    bridge.set_app_window(window)

    def _fast_exit(*args, **kwargs) -> None:
        try:
            if hasattr(window, "native") and window.native:
                hwnd = int(window.native.Handle)
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception:
            pass
        try:
            hwnd = ctypes.windll.user32.FindWindowW(None, app_title)
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception:
            pass
        ctypes.windll.kernel32.ExitProcess(0)

    window.events.closed += _fast_exit
    try:
        window.events.closing += _fast_exit
    except Exception:
        pass

    def _reveal_fallback() -> None:
        time.sleep(0.4)
        try:
            window.show()
        except Exception:
            pass
        _apply_win32_icon(app_title, ico_path)

    threading.Thread(target=_reveal_fallback, daemon=True).start()

    webview.start(
        gui="edgechromium",
        debug=is_debug,
        icon=str(ico_path) if ico_path.exists() else None,
        storage_path=str(storage_dir),
        private_mode=False,
    )


if __name__ == "__main__":
    main()
