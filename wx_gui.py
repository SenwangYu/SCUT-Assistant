# kicad_complex_framework/wx_gui.py

import wx
import wx.html2
import sys
import os
import time
import json
import re
import threading
from openai import OpenAI
import subprocess
import pcbnew

#  作为kicad插件需要相对导入，独立运行需要绝对导入
from . import pcb_assistant_utils
from . import system_prompt

# import pcb_assistant_utils
# import system_prompt

AVAILABLE_ACTIONS = {
    "move_footprint": pcb_assistant_utils.move_footprint,
    "launch_freerouting": pcb_assistant_utils.launch_freerouting,
    "place_footprint": pcb_assistant_utils.place_footprint,
    "connect_pads_to_nets": pcb_assistant_utils.connect_pads_to_nets,
    "query_board_footprints": pcb_assistant_utils.query_board_footprints,
    "create_board_outline": pcb_assistant_utils.create_board_outline,
    "put_next_to": pcb_assistant_utils.put_next_to,
    "minimum_board_outline": pcb_assistant_utils.minimum_board_outline
}


class DeepSeekWorker:
    def __init__(self, api_key, window):
        self.api_key = api_key
        self.window = window
        self.client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        self._is_running = True

    def run_query(self, message):
        """修改后的处理流式请求的线程函数"""
        # 更新UI显示助手消息头
        # wx.CallAfter(self.window.append_message, "assistant", "DeepSeek 助手", "")
        ChatWindow.debug_print(self.window, "进入run_query")
        full_response = []
        json_detected = False  # 检测JSON结构标志位

        try:
            response_stream = self.client.chat.completions.create(
                model="deepseek/deepseek-chat-v3.1:free",
                messages=message,
                stream=True
            )

            for chunk in response_stream:
                if not self._is_running:  # 用户取消请求
                    break

                if chunk.choices[0].delta.content:
                    text_chunk = chunk.choices[0].delta.content
                    full_response.append(text_chunk)

                    # 尝试检测JSON结构的开始
                    if not json_detected and any(brace in text_chunk for brace in ['{', '}']):
                        json_detected = True

                    if json_detected:
                        # JSON模式下只收集文本，不更新UI
                        continue
                    # else:
                    # 非JSON模式下实时更新
                    # wx.CallAfter(self.window.update_response, text_chunk)
                    # time.sleep(0.05)  # 模拟真实打字效果

            # 拼接完整响应
            full_response_str = ''.join(full_response)

            # 保存到历史记录
            self.window.conversation_history.append({"role": "assistant", "content": full_response_str})

            ChatWindow.debug_print(self.window, self.window.conversation_history)

            # 尝试解析并执行操作
            if not self.parse_and_execute_actions(full_response_str):
                # 如果解析失败，直接显示原始内容
                wx.CallAfter(self.window.append_message, "assistant",
                             "SCUT助手", full_response_str)

        except Exception as e:
            error_msg = f"\n\n【错误】: {str(e)}"
            wx.CallAfter(self.window.update_response, error_msg)
        finally:
            wx.CallAfter(self.window.on_request_finished)

    # def parse_and_execute_actions(self, response_content):
    #     """解析JSON结构并执行操作"""
    #     # wx.CallAfter(self.window.append_message, "system", "执行器", "开始解析操作指令...")
    #     ChatWindow.debug_print(self.window, response_content)
    #     try:
    #         # 提取可能的JSON结构
    #         # json_match = re.search(r'(\{(?:[^{}]|(?:\{(?:[^{}]|(?:\{[^{}]*\}))*\}))*\})', response_content)
    #         # if not json_match:
    #         #     raise ValueError("未找到有效JSON结构")
    #
    #         start = response_content.find('{')
    #         end = response_content.rfind('}')
    #         if start == -1 or end == -1 or end < start:
    #             raise ValueError("未找到有效JSON结构")
    #         json_str = response_content[start:end + 1]
    #
    #         # ChatWindow.debug_print(self.window, json_match)
    #
    #         # json_str = json_match.group(0)
    #         ChatWindow.debug_print(self.window, json_str)
    #         action_plan = json.loads(json_str)
    #
    #         ChatWindow.debug_print(self.window, action_plan)
    #
    #         explanation = action_plan.get("explanation", "")
    #         actions = action_plan.get("actions", [])
    #
    #         ChatWindow.debug_print(self.window, explanation)
    #         ChatWindow.debug_print(self.window, actions)
    #         wx.CallAfter(self.window.append_message, "assistant", "SCUT助手", explanation)
    #
    #         # 执行每个动作
    #         for i, action in enumerate(actions):
    #             func_name = action.get("function")
    #             params = action.get("parameters", {})
    #
    #             # 分离长字符串的构建
    #             params_str = ', '.join(f"{k}={v}" for k, v in params.items())
    #             message = f"准备执行: {func_name}({params_str})"
    #             wx.CallAfter(self.window.append_message, "system", "执行", message)
    #
    #             # 修复缩进问题
    #             if func_name in AVAILABLE_ACTIONS:
    #                 try:
    #                     result = AVAILABLE_ACTIONS[func_name](**params)
    #                     wx.CallAfter(self.window.append_message, "system", "结果",
    #                                  f"操作成功: {func_name} 返回 {result}")
    #                 except Exception as e:
    #                     wx.CallAfter(self.window.append_message, "system", "错误",
    #                                  f"执行失败: {str(e)}")
    #             else:
    #                 wx.CallAfter(self.window.append_message, "system", "警告",
    #                              f"未知操作: {func_name}")
    #
    #         return True
    #     except Exception as e:
    #         wx.CallAfter(self.window.append_message, "system", "错误",
    #                      f"解析错误: {str(e)}")
    #         return False

    def parse_and_execute_actions(self, response_content):
        """解析JSON结构并执行操作"""
        # ChatWindow.debug_print(self.window, response_content)
        ChatWindow.debug_print(self.window, "进入parse_and_execute_actions")
        try:
            # 提取可能的JSON结构
            ChatWindow.debug_print(self.window, "开始提取JSON")

            # json_match = re.search(r'(\{(?:[^{}]|(?:\{(?:[^{}]|(?:\{[^{}]*\}))*\}))*\})', response_content)
            json_match = self.extract_json(response_content)
            if not json_match:
                ChatWindow.debug_print(self.window, "未找到有效JSON结构")
                raise ValueError("未找到有效JSON结构")
            # extract_json() 返回的是一个 Python 字典,所以不用group也不用loads了
            # json_str = json_match.group(0)
            # action_plan = json.loads(json_str)
            action_plan = json_match
            explanation = action_plan.get("explanation", "")
            actions = action_plan.get("actions", [])

            # ChatWindow.debug_print(self.window, "json_str:\n" + json_str)
            ChatWindow.debug_print(self.window, action_plan)
            ChatWindow.debug_print(self.window, explanation)
            ChatWindow.debug_print(self.window, actions)

            wx.CallAfter(self.window.append_message, "assistant", "SCUT助手", explanation)

            action_feedback = []

            # 执行动作
            for action in actions:
                ChatWindow.debug_print(self.window, "执行动作一次")
                func_name = action.get("function")
                params = action.get("parameters", {})

                if func_name in AVAILABLE_ACTIONS:
                    try:
                        result = AVAILABLE_ACTIONS[func_name](**params)
                        feedback = f"{func_name} 执行成功，返回: {result}"
                    except Exception as e:
                        feedback = f"{func_name} 执行失败: {str(e)}"
                else:
                    feedback = f"未知操作: {func_name}"

                wx.CallAfter(self.window.append_message, "system", "执行反馈", feedback)
                action_feedback.append(feedback)

            # === 核心改动：动作执行完后，继续交给大模型 ===
            if action_feedback:
                feedback_text = json.dumps(
                    {"上次动作已执行完毕,执行结果如下，请不要重复执行上面已经执行过的动作": action_feedback},
                    ensure_ascii=False
                )
                # 把动作结果交给大模型，让它决定下一步
                wx.CallAfter(self.window.conversation_history.append,
                             {"role": "user", "content": feedback_text})

                wx.CallAfter(self.run_query, self.window.conversation_history)
                ChatWindow.debug_print(self.window, "反馈完成一次")

            return True

        except Exception as e:
            wx.CallAfter(self.window.append_message, "system", "错误", f"解析错误: {str(e)}")
            return False

    import json

    def extract_json(self, response_content: str):
        """
        用GPT写的提取JSON的函数
        从 response_content 中提取第一个完整 JSON 对象并返回 Python 字典
        如果无法找到或解析，返回 None
        """
        start = response_content.find("{")
        if start == -1:
            return None  # 没有左大括号，直接返回

        count = 0
        in_string = False
        escape = False
        candidate = []

        for ch in response_content[start:]:
            candidate.append(ch)

            # 处理字符串里的括号，避免被计数
            if ch == '"' and not escape:
                in_string = not in_string
            elif ch == '\\' and not escape:
                escape = True
                continue
            escape = False

            if not in_string:
                if ch == '{':
                    count += 1
                elif ch == '}':
                    count -= 1
                    if count == 0:
                        # 找到完整 JSON 块
                        json_str = ''.join(candidate)
                        try:
                            return json.loads(json_str)
                        except json.JSONDecodeError:
                            return None

        return None  # 没有匹配成功

    def cancel(self):
        """取消当前请求"""
        self._is_running = False


class ChatWindow(wx.Frame):
    def __init__(self, api_key, parent=None):
        super(ChatWindow, self).__init__(parent, title='SCUTChat', size=(900, 800))
        self.api_key = api_key
        self.worker = None
        self.worker_thread = None
        self.conversation_history = system_prompt.SYSTEM_PROMPT
        self.chat_html = "<html><head><style>body { font-family: Arial; background-color: #f0f0f0; }</style></head><body></body></html>"
        self.init_ui()
        # 初始消息
        self.append_message("assistant", "SCUT助手", "您好！我是来自SCUT的PCB助手。请问有什么可以帮您？")

    def init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # 创建HTML窗口用于富文本显示
        self.chat_display = wx.html2.WebView.New(panel)
        self.chat_display.SetPage(self.chat_html, "")  # 初始化带样式的内容

        # 输入区域
        self.message_input = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.message_input.SetHint("输入您的问题...")

        # 按钮
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.send_btn = wx.Button(panel, label="发送")
        self.stop_btn = wx.Button(panel, label="停止响应")
        self.test_btn = wx.Button(panel, label="test")
        self.debug_btn = wx.Button(panel, label="调试")  # 新增调试按钮
        self.stop_btn.Disable()

        btn_sizer.Add(self.send_btn, 1, wx.EXPAND)
        btn_sizer.Add(self.stop_btn, 1, wx.EXPAND)
        btn_sizer.Add(self.test_btn, 1, wx.EXPAND)
        btn_sizer.Add(self.debug_btn, 1, wx.EXPAND)  # 添加调试按钮到布局

        # 加一个Debug窗口
        debug_sizer = wx.StaticBoxSizer(wx.VERTICAL, panel, "Debug Window")
        self.debug_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        self.debug_text.SetMinSize((-1, 150))  # 设置最小高度150像素
        debug_sizer.Add(self.debug_text, 1, wx.EXPAND | wx.ALL, 5)
        vbox.Add(debug_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        # 布局
        vbox.Add(self.chat_display, 1, wx.EXPAND | wx.ALL, 5)
        vbox.Add(self.message_input, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        vbox.Add(btn_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        panel.SetSizer(vbox)

        # 事件绑定
        self.send_btn.Bind(wx.EVT_BUTTON, self.send_message)
        self.stop_btn.Bind(wx.EVT_BUTTON, self.cancel_request)
        self.test_btn.Bind(wx.EVT_BUTTON, self.on_test)
        # self.debug_btn.Bind(wx.EVT_BUTTON, self.toggle_debug) # 绑定调试按钮事件
        self.message_input.Bind(wx.EVT_TEXT_ENTER, self.send_message)

        self.Bind(wx.EVT_CLOSE, self.on_close)

    def append_message(self, role, name, message):
        """添加消息到对话框"""
        if role == "user":
            color = "#0066cc"
        elif role == "assistant":
            color = "#009933"
        elif role == "system":
            color = "#ff6600"  # 橙色用于系统消息
        elif role == "execution":
            color = "#9933cc"  # 紫色用于执行消息
        else:
            color = "#666666"

        timestamp = time.strftime("%H:%M:%S")
        html_content = f"""
        <div style='margin:10px 0;'>
            <span style='font-weight:bold;color:{color}'>{name}</span>
            <span style='color:#999;font-size:0.8em'>({timestamp})</span>
            <div style='margin-top:5px;'>{message}</div>
        </div>
        """

        # 直接更新HTML字符串
        self.chat_html = self.chat_html.replace("</body>", f"{html_content}</body>")
        self.chat_display.SetPage(self.chat_html, "")
        self.scroll_to_bottom()

        # 保存到历史记录
        if role == "user":
            self.conversation_history.append({"role": "user", "content": message})
        # elif role == "assistant":
        #     self.conversation_history.append({"role": "assistant", "content": message})

    def update_response(self, text_chunk):
        """实时更新流式响应"""
        # 用正则处理粗体样式
        formatted_chunk = text_chunk.replace("\n", "<br>").replace('"', '\\"')

        # 使用JavaScript追加内容到最后一个消息框
        js = f"""
        var lastDiv = document.body.lastElementChild;
        var contentDiv = lastDiv.querySelector('div');
        contentDiv.innerHTML += "{formatted_chunk}";
        window.scrollTo(0, document.body.scrollHeight);
        """
        self.chat_display.RunScript(js)

    def send_message(self, event):
        """用户发送消息"""

        message = self.message_input.GetValue().strip()
        if not message:
            return

        self.append_message("user", "用户", message)
        self.message_input.Clear()

        # 禁用发送按钮直到完成
        self.send_btn.Disable()
        self.stop_btn.Enable()

        # 启动工作线程
        self.worker = DeepSeekWorker(self.api_key, self)
        self.worker_thread = threading.Thread(target=self.worker.run_query, args=(self.conversation_history,))
        self.worker_thread.daemon = True
        self.worker_thread.start()

    def cancel_request(self, event):
        """取消当前响应"""
        if self.worker:
            self.worker.cancel()
            self.append_message("system", "系统", "【响应已取消】")
            self.on_request_finished()

    def on_request_finished(self):
        """请求完成后的清理工作"""
        self.send_btn.Enable()
        self.stop_btn.Disable()
        self.worker = None
        self.worker_thread = None

    def on_test(self, event):
        # pcb_assistant_utils.test222()
        # pcb_assistant_utils.create_board_outline(1000, 1000, 1000, 1000)
        self.debug_print("test_bnt")
        # pcb_assistant_utils.test()
        pcb_assistant_utils.minimum_board_outline()
        # pcb_assistant_utils.record_of_courtyards()
        # pcb_assistant_utils.put_next_to("C4", "R2", 0, 10, 5, 500, True)
        # pcb_assistant_utils.put_next_to_v2("C4", "R2", 1)
        # pcb_assistant_utils.move_footprint("CV", 0, 0)
        # pcb_assistant_utils.place_footprint("Inductor_SMD", "L_01005_0402Metric", 0,
        #                                     0, "L1", "10µF",
        #                                     {"1": "SW", "2": "VOUT"},
        #                                     0
        #                                     )
        # pcb_assistant_utils.get_courtyard_by_ref("L2")
        # pcb_assistant_utils.get_courtyard()
        # wx.CallAfter(pcb_assistant_utils.create_board_outline, 50, 50, 100, 100)
        # pcb_assistant_utils.connect_pads_to_nets("LED1", {'1': 'PPP', '2': 'BBB'})
        # wx.MessageBox("BBB")
        # pcb_assistant_utils.connect_pads_to_nets("R22", {"1": "VCC", "2": "GND"})
        # pcb_assistant_utils.test()
        # pcb_assistant_utils.place_footprint("Display", "AG12864E", 100, 200, rotation_deg=0)
        # wx.MessageBox(pcb_assistant_utils.get_board_statistics())
        # print(1)
        # 先将工程文件导出为dsn,用freerouting打开后存为ses再加载

        # freerouting_path = "D:/Kicad/9.0/share/kicad/scripting/plugins/kicad_complex_framework/freerouting/freerouting-2.1.0.jar"
        # board = pcbnew.GetBoard()
        # board_path = board.GetFileName()
        # base_name = os.path.splitext(board_path)[0]
        # dsn_file = base_name + ".dsn"
        # ses_file = base_name + ".ses"
        # pcbnew.ExportSpecctraDSN(board, dsn_file)
        # command = ["java", "-jar", freerouting_path, "-de", dsn_file, "-do", ses_file]
        # subprocess.run(command, check=True)
        # pcbnew.ImportSpecctraSES(board, ses_file)
        # pcbnew.Refresh()
        # pcb_assistant_utils.move_footprint_by_ref("C1", 500, 500)
        # pcb_assistant_utils.get_board_statistics()

    def on_close(self, event):
        """窗口关闭时确保停止所有线程"""
        if self.worker:
            self.worker.cancel()
            if self.worker_thread and self.worker_thread.is_alive():
                self.worker_thread.join(timeout=1.0)
        self.Destroy()

    def debug_print(self, message, level="INFO"):
        """
        在调试窗口打印信息

        参数:
            message (str): 要显示的调试信息
            level (str): 信息级别，可选值: "INFO", "WARNING", "ERROR", "DEBUG"
        """
        # 如果调试窗口尚未初始化直接返回（避免异常）
        if not hasattr(self, 'debug_text'):
            return

        # 获取当前时间（精确到毫秒）
        timestamp = time.strftime("%H:%M:%S")

        # 为不同级别添加前缀
        level_prefixes = {
            "INFO": "[INFO]",
            "DEBUG": "[DEBUG]",
            "WARNING": "[WARNING]",
            "ERROR": "[ERROR]"
        }

        prefix = level_prefixes.get(level, "[UNKNOWN]")

        # 格式化输出
        formatted_msg = f"[{timestamp}] {prefix} {message}\n"

        # 向调试窗口添加信息（纯文本）
        self.debug_text.AppendText(formatted_msg)

        # 滚动到最新内容
        self.debug_text.ShowPosition(self.debug_text.GetLastPosition())

        # 立即刷新UI（如果需要在长任务中实时显示）
        wx.YieldIfNeeded()

    def scroll_to_bottom(self):
        """将滚动条移动到底部"""

        def _do_scroll(self):
            if self.chat_display:
                # 获取垂直滚动范围
                scroll_range = self.chat_display.GetScrollRange(wx.VERTICAL)
                # 设置滚动位置到底部
                self.chat_display.Scroll(0, scroll_range)
                # 强制刷新显示
                self.chat_display.Refresh()

        wx.CallAfter(_do_scroll, self)

# if __name__ == "__main__":
# app = wx.App()
#
# # 替换 API密钥
# API_KEY = "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"
#
# frame = ChatWindow(API_KEY)
# frame.Show()
# app.MainLoop()
