# kicad_complex_framework/__main__.py
# 在插件入口文件的最顶部添加


import wx  # KiCad 使用 wxPython 作为其 GUI 工具包

# 从我们自己的工具模块中导入辅助函数
import wx_gui


def run_standalone():
    """
      当用户点击工具栏按钮或菜单项时，此方法被调用.
      这是插件在 KiCad 环境内的主要入口点.
      """
    app = wx.App()

    # 替换为您的DeepSeek API密钥
    # API_KEY = "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"  # 0528
    API_KEY = "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"  # v3.1

    frame = wx_gui.ChatWindow(API_KEY)
    frame.Show()
    app.MainLoop()

if __name__ == "__main__":
    run_standalone()
