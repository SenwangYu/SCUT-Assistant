# kicad_complex_framework/pcb_assistant_action.py

import os
import wx
import pcbnew

# 从我们自己的工具模块中导入辅助函数
from . import wx_gui

_chat_window_instance = None


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
        当用户点击工具栏按钮或菜单项时，此方法被调用.这是插件在 KiCad 环境内的主要入口点.
        """

        global _chat_window_instance

        # KiCad 已经在运行 wx 主循环，不需要再创建 wx.App()
        app = wx.App.Get() or wx.App(False)

        # 如果窗口存在且显示中，就直接激活它
        if _chat_window_instance and _chat_window_instance.IsShownOnScreen():
            _chat_window_instance.Raise()
            _chat_window_instance.RequestUserAttention(wx.USER_ATTENTION_INFO)
            return

        # 否则新建窗口
        API_KEY = "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"
        _chat_window_instance = wx_gui.ChatWindow(API_KEY)

        # 绑定关闭事件
        def on_close(event):
            global _chat_window_instance
            _chat_window_instance = None
            event.Skip()

        _chat_window_instance.Bind(wx.EVT_CLOSE, on_close)
        _chat_window_instance.Show()
