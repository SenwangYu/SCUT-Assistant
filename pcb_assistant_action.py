# kicad_complex_framework/pcb_assistant_action.py

import os

import pcbnew
import wx  # KiCad 使用 wxPython 作为其 GUI 工具包

# 从我们自己的工具模块中导入辅助函数
from .import wx_gui


class ComplexFrameworkAction(pcbnew.ActionPlugin):
    """
    ActionPlugin 派生类.
    这个类定义了插件的行为和元数据.
    """

    def defaults(self):
        self.name = "SCUT助手"
        self.category = "pcb助手"
        self.description = "一个由AI来帮助实现PCB设计的插件"
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(os.path.dirname(__file__), 'icon.png')

    def Run(self):
        """
        当用户点击工具栏按钮或菜单项时，此方法被调用.
        这是插件在 KiCad 环境内的主要入口点.
        """


        # app = wx.App()

        # 替换为您的DeepSeek API密钥
        API_KEY = "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"

        frame = wx_gui.ChatWindow(API_KEY)
        frame.Show()
        # app.MainLoop()
