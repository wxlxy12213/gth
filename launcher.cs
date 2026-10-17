using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

namespace GthDesktopLauncher
{
    static class Program
    {
        [STAThread]
        static void Main()
        {
            try
            {
                string appDir = AppDomain.CurrentDomain.BaseDirectory;
                string scriptPath = Path.Combine(appDir, "app_main.py");
                
                if (!File.Exists(scriptPath))
                {
                    MessageBox.Show("找不到主程序脚本：" + scriptPath, "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }

                // 优先寻找免黑窗 pythonw.exe，若无则使用 python.exe
                string pythonExe = "pythonw.exe";
                ProcessStartInfo psi = new ProcessStartInfo
                {
                    FileName = pythonExe,
                    Arguments = "\"" + scriptPath + "\"",
                    WorkingDirectory = appDir,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };

                try
                {
                    Process.Start(psi);
                }
                catch
                {
                    // 若 pythonw 未在系统 PATH 中，回退尝试 python.exe
                    psi.FileName = "python.exe";
                    Process.Start(psi);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show("启动工作台失败：" + ex.Message, "启动错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
    }
}
