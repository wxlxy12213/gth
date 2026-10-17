# @AI-ANCHOR: [WIN-OS-SERVICE] Windows 原生系统调用封装层（剪贴板/坐标拾取/文件对话框/窗口句柄）
"""win_os_service.py - 操作系统原生交互服务层 (<200行微切片)。

职责：
将原本散落在 `ui/api_bridge.py` 中的 Win32 API、剪贴板操作、Tkinter 文件对话框、
资源管理器进程调起及窗口置顶/尺寸控制彻底解耦，确保 `api_bridge.py` 保持纯粹的 IPC 路由职责。
"""
from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("gth.win_os")


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


# @AI-ANCHOR: [WIN-CLIPBOARD-COORD] 剪贴板读写、CF_HDROP 文件路径提取与 3 秒屏幕坐标拾取
def pick_screen_coordinate(delay_sec: float = 3.0) -> dict[str, int]:
    """倒计时后拾取当前鼠标物理屏幕坐标。"""
    if delay_sec > 0:
        time.sleep(delay_sec)
    pt = POINT()
    try:
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return {"x": int(pt.x), "y": int(pt.y)}
    except Exception as exc:
        logger.warning("拾取屏幕坐标异常: %s", exc)
        return {"x": 0, "y": 0}


def read_clipboard_text() -> str:
    """读取 Windows 系统剪贴板纯文本。"""
    try:
        import win32clipboard
        import win32con
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT) or ""
        finally:
            win32clipboard.CloseClipboard()
    except Exception as exc:
        logger.debug("读取剪贴板文本异常: %s", exc)
    return ""


def write_clipboard_text(text: str) -> bool:
    """写入文本至 Windows 系统剪贴板。"""
    try:
        import win32clipboard
        import win32con
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
            return True
        finally:
            win32clipboard.CloseClipboard()
    except Exception as exc:
        logger.warning("写入剪贴板异常: %s", exc)
        return False


def get_clipboard_doc_path() -> str:
    """从 Windows 剪贴板提取复制的 Word 文件路径（优先 CF_HDROP，次选路径文本）。"""
    try:
        import win32clipboard
        import win32con
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_HDROP):
                files = win32clipboard.GetClipboardData(win32con.CF_HDROP)
                if files:
                    for f in files:
                        if str(f).lower().endswith((".doc", ".docx")):
                            return str(f)
                    return str(files[0])
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                text = (win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT) or "").strip()
                clean = text.strip('"\'“”‘’').strip()
                if clean.lower().endswith((".doc", ".docx")):
                    return clean
        finally:
            win32clipboard.CloseClipboard()
    except Exception as exc:
        logger.debug("读取剪贴板文件路径异常: %s", exc)
    return ""


# @AI-ANCHOR: [WIN-FILE-EXPLORER] 原生文件选择框、Word 启动与 Explorer 高亮定位
def browse_doc_file_dialog() -> str:
    """调起 Windows 原生文件对话框选择 .doc / .docx 文件。"""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askopenfilename(
            title="选择业务员进料文书 (.doc / .docx)",
            filetypes=[("Word 文档", "*.doc;*.docx"), ("所有文件", "*.*")],
        )
        root.destroy()
        return selected or ""
    except Exception as exc:
        logger.warning("文件选择对话框异常: %s", exc)
        return ""


def open_file_native(file_path: str | Path) -> bool:
    """调用系统默认程序（Word / WPS）打开指定文件（已修复原版缺失 import os 导致的 NameError）。"""
    try:
        clean_p = Path(file_path).resolve()
        if clean_p.exists():
            if hasattr(os, "startfile"):
                os.startfile(str(clean_p))
            else:
                subprocess.Popen(["xdg-open", str(clean_p)])
            return True
        return False
    except Exception as exc:
        logger.warning("打开文件失败 (%s): %s", file_path, exc)
        return False


def reveal_in_explorer(target_path_str: str = "") -> bool:
    """在 Windows 资源管理器中打开目录或高亮选中目标文件。"""
    try:
        target = Path(target_path_str).resolve() if target_path_str else None
        if target and target.exists():
            if target.is_file():
                subprocess.Popen(["explorer.exe", f"/select,{target}"])
            else:
                subprocess.Popen(["explorer.exe", str(target)])
            return True
        desk = (Path.home() / "Desktop").resolve()
        subprocess.Popen(["explorer.exe", str(desk)])
        return True
    except Exception as exc:
        logger.warning("打开资源管理器异常: %s", exc)
        return False


# @AI-ANCHOR: [WIN-HUD-WINDOW] 全景工作台与 380x140 悬浮 Mini-HUD 窗口句柄切换
def switch_window_hud_mode(
    app_window: Any,
    enable_hud: bool,
    app_title: str = "个体户填报工作台",
) -> dict[str, Any]:
    """切换窗口尺寸与 HWND_TOPMOST 置顶状态。"""
    SWP_SHOWWINDOW = 0x0040
    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2

    try:
        user32 = ctypes.windll.user32
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
    except Exception:
        screen_w, screen_h = 1920, 1080

    if enable_hud:
        target_w, target_h = 380, 140
        target_x = max(0, screen_w - 400)
        target_y = 24
        z_order = HWND_TOPMOST
        mode_name = "hud"
    else:
        target_w, target_h = 1360, 860
        target_x = max(0, (screen_w - target_w) // 2)
        target_y = max(0, (screen_h - target_h) // 2)
        z_order = HWND_NOTOPMOST
        mode_name = "workbench"

    if app_window:
        try:
            app_window.resize(target_w, target_h)
            app_window.move(target_x, target_y)
            app_window.on_top = bool(enable_hud)
        except Exception as exc:
            logger.debug("pywebview 窗口调整异常: %s", exc)

    try:
        hwnd = ctypes.windll.user32.FindWindowW(None, app_title)
        if hwnd:
            ctypes.windll.user32.SetWindowPos(
                hwnd, z_order, target_x, target_y, target_w, target_h, SWP_SHOWWINDOW
            )
    except Exception as exc:
        logger.debug("Win32 SetWindowPos 异常: %s", exc)

    return {"success": True, "mode": mode_name, "x": target_x, "y": target_y, "w": target_w, "h": target_h}


def force_exit_process(app_window: Any = None, app_title: str = "个体户填报工作台") -> None:
    """隐藏窗口并立即终止进程。"""
    try:
        if app_window and hasattr(app_window, "native") and app_window.native:
            hwnd = int(app_window.native.Handle)
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
    try:
        if app_window:
            app_window.destroy()
    except Exception:
        pass
    try:
        ctypes.windll.kernel32.ExitProcess(0)
    except Exception:
        os._exit(0)
