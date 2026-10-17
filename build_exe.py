"""build_exe.py - 双轨独立桌面 EXE 极速打包与编译引擎。"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_CSC_PATH = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")


def build_native_launcher() -> str:
    """使用 Win11 原生 csc.exe 编译 40KB 零报毒极速启动器。"""
    cs_file = _ROOT / "launcher.cs"
    out_exe = _ROOT / "个体户填报.exe"

    if not _CSC_PATH.exists():
        print(f"[-] 未找到系统 csc.exe: {_CSC_PATH}")
        return ""

    ico_file = _ROOT / "assets" / "app.ico"
    cmd = [
        str(_CSC_PATH),
        "/target:winexe",
        "/optimize+",
        "/platform:anycpu",
        f"/out:{out_exe}",
    ]
    if ico_file.exists():
        cmd.append(f"/win32icon:{ico_file}")
    cmd.append(str(cs_file))

    print("[*] 正在编译原生极速启动器（嵌入专属 Neo-Brutalist 图标）...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and out_exe.exists():
        size_kb = out_exe.stat().st_size / 1024
        print(f"[+] 原生启动器编译成功：{out_exe} (体积: {size_kb:.1f} KB)")
        return str(out_exe)
    else:
        print(f"[-] 编译失败: {res.stderr}")
        return ""


def build_pyinstaller_bundle() -> str:
    """使用 PyInstaller 构建独立分发目录/单文件包。"""
    print("[*] 正在执行 PyInstaller 轻量化独立打包...")
    entry = _ROOT / "app_main.py"
    dist_dir = _ROOT / "dist"
    work_dir = _ROOT / "build"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", "个体户填报工作台",
        f"--distpath={dist_dir}",
        f"--workpath={work_dir}",
        "--add-data", f"{_ROOT / 'ui'};ui",
        "--add-data", f"{_ROOT / 'config'};config",
        str(entry)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    out_dir = dist_dir / "个体户填报工作台"
    if res.returncode == 0 and out_dir.exists():
        print(f"[+] PyInstaller 打包成功：{out_dir}")
        return str(out_dir)
    else:
        print(f"[-] PyInstaller 打包警告: {res.stderr[:300]}")
        return ""


def create_desktop_shortcut(target_exe: str | Path | None = None) -> str:
    """创建或更新桌面快捷方式。"""
    try:
        import win32com.client
        desktop = Path.home() / "Desktop"
        shortcut_path = desktop / "个体户填报.lnk"
        exe = Path(target_exe) if target_exe else _ROOT / "个体户填报.exe"
        if not exe.exists():
            return ""
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(str(shortcut_path))
        shortcut.TargetPath = str(exe.resolve())
        shortcut.WorkingDirectory = str(_ROOT.resolve())
        shortcut.Description = "山东政务（一窗通）个体户 RPA 极速填报工作台"
        ico_file = _ROOT / "assets" / "app.ico"
        if ico_file.exists():
            shortcut.IconLocation = f"{ico_file.resolve()},0"
        shortcut.Save()
        print(f"[+] 桌面快捷方式同步就绪（专属高颜值图标）：{shortcut_path}")
        return str(shortcut_path)
    except Exception as e:
        print(f"[-] 创建桌面快捷方式跳过: {e}")
        return ""


if __name__ == "__main__":
    print("=== 开始构建桌面独立交付物 ===")
    native_exe = build_native_launcher()
    if native_exe:
        print(f"[OK] 极速免重编启动器交付就绪：{native_exe}")
        create_desktop_shortcut(native_exe)
