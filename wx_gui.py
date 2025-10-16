# kicad_complex_framework/wx_gui.py

import wx
import wx.html2
import sys
import os
import time
import json
import html
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
    "put_next_to": pcb_assistant_utils.put_next_to,
    "create_minimum_board_outline": pcb_assistant_utils.create_minimum_board_outline
}


class DeepSeekWorker:
    def __init__(self, api_key, window):
        self.api_key = api_key
        self.window = window
        self.client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        self._is_running = True

    def run_query(self, message):
        """修改后的处理流式请求的线程函数"""
        self.window.log_debug("进入run_query")
        full_response = []
        json_started = False
        self._is_running = True
        assistant_message_head_added = False

        # 批量处理缓存
        chunk_buffer = []
        last_update_time = time.time()
        update_interval = 0.2  # 每0.2秒更新一次UI

        try:
            response_stream = self.client.chat.completions.create(
                model="deepseek/deepseek-chat-v3.1",
                messages=message,
                stream=True
            )

            for chunk in response_stream:
                if not self._is_running:
                    self.window.log_debug("用户取消请求")
                    break

                text_chunk = chunk.choices[0].delta.content
                if text_chunk:
                    full_response.append(text_chunk)

                    if not json_started:
                        if '§' in text_chunk:
                            json_started = True
                            before_json_part, _, _ = text_chunk.partition('§')
                            if before_json_part:
                                chunk_buffer.append(before_json_part)

                            # 立即输出缓存的内容
                            if chunk_buffer:
                                batched_text = ''.join(chunk_buffer)
                                wx.CallAfter(self.window.update_response, batched_text)
                                chunk_buffer.clear()

                            self.window.log_debug("检测到 '§', 停止流式输出到UI")
                            # 启动等待动画
                            wx.CallAfter(self.window.start_planning_animation)

                        else:
                            # 添加助手消息头（只添加一次）
                            if not assistant_message_head_added:
                                wx.CallAfter(self.window.append_message, "assistant", "SCUT助手", "")
                                assistant_message_head_added = True

                            # 缓存chunk
                            chunk_buffer.append(text_chunk)

                            # 定时批量更新UI
                            current_time = time.time()
                            if current_time - last_update_time >= update_interval:
                                if chunk_buffer:
                                    batched_text = ''.join(chunk_buffer)
                                    wx.CallAfter(self.window.update_response, batched_text)
                                    chunk_buffer.clear()
                                    last_update_time = current_time

            # 输出剩余的chunk
            if chunk_buffer and not json_started:
                batched_text = ''.join(chunk_buffer)
                wx.CallAfter(self.window.update_response, batched_text)
                chunk_buffer.clear()

            # 用户取消请求就退出
            if not self._is_running:
                wx.CallAfter(self.window.on_request_finished)
                return

            # 拼接完整响应
            full_response_str = ''.join(full_response)

            # 保存到历史记录
            self.window.conversation_history.append({"role": "assistant", "content": full_response_str})

            # 尝试解析并执行操作
            json_match = self.extract_json(full_response_str)
            actions = []
            if json_match is not None:
                actions = json_match.get("actions", [])
            if not actions:  # 没有动作需要执行
                # 停止动画,没有动作就延迟停止动画，让动画播放完整
                wx.CallLater(1000, self.window.stop_planning_animation)
                wx.CallAfter(self.window.on_request_finished)
                return
            else:
                self.execute_actions(actions)

        except Exception as e:
            # 停止动画
            wx.CallAfter(self.window.stop_planning_animation)
            error_msg = f"\n\n【错误】: {str(e)}"
            self.window.log_debug(f"请求异常: {str(e)}", level="ERROR")
            wx.CallAfter(self.window.update_response, error_msg)
            wx.CallAfter(self.window.on_request_finished)

    def execute_actions(self, actions):
        """解析JSON结构并执行操作"""
        # 动画停止
        wx.CallAfter(self.window.stop_planning_animation)
        try:
            action_feedback = []

            # 执行动作
            for idx, action in enumerate(actions):
                self.window.log_debug(f"执行第 {idx + 1} 个动作")
                func_name = action.get("function")
                params = action.get("parameters", {})

                if func_name in AVAILABLE_ACTIONS:
                    try:
                        result = AVAILABLE_ACTIONS[func_name](**params)
                        feedback = f"{func_name} 执行成功，返回: {result}"
                        self.window.log_debug(feedback)
                    except Exception as e:
                        feedback = f"{func_name} 执行失败: {str(e)}"
                        self.window.log_debug(feedback, level="ERROR")
                else:
                    feedback = f"未知操作: {func_name}"
                    self.window.log_debug(feedback, level="WARNING")

                wx.CallAfter(self.window.append_message, "system", "执行反馈", feedback)
                action_feedback.append(feedback)

            # 核心改动：将后续请求的启动延迟到主线程
            if action_feedback:
                feedback_text = json.dumps(
                    {"上次动作已执行完毕,执行结果如下，请不要重复执行上面已经执行过的动作": action_feedback},
                    ensure_ascii=False
                )
                # 先结束当前请求
                wx.CallAfter(self.window.on_request_finished)
                # 延迟100ms后在主线程中启动新请求
                wx.CallLater(100, self.window.start_follow_up_request, feedback_text)
            else:
                wx.CallAfter(self.window.on_request_finished)

        except Exception as e:
            error_msg = f"解析错误: {str(e)}"
            self.window.log_debug(error_msg, level="ERROR")
            wx.CallAfter(self.window.append_message, "system", "错误", error_msg)
            wx.CallAfter(self.window.on_request_finished)

    def extract_json(self, response_content: str):
        """
        从 response_content 中提取第一个完整 JSON 对象并返回 Python 字典
        如果无法找到或解析，返回 None
        """
        start = response_content.find("{")
        if start == -1:
            return None

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
                        except json.JSONDecodeError as e:
                            self.window.log_debug(f"JSON解析失败: {str(e)}", level="ERROR")
                            return None

        return None

    def cancel(self):
        """取消当前请求"""
        self.window.log_debug("取消请求被调用")
        self._is_running = False


class ChatWindow(wx.Frame):
    def __init__(self, api_key, parent=None):
        super(ChatWindow, self).__init__(parent, title='SCUTChat', size=(900, 800))
        self.api_key = api_key
        self.worker = None
        self.worker_thread = None
        self.conversation_history = system_prompt.SYSTEM_PROMPT
        self.chat_html = "<html><head><style>body { font-family: Arial; background-color: #f0f0f0; }</style></head><body></body></html>"

        # 请求状态标志
        self.is_requesting = False

        # 等待动画标记
        self.planning_timer = None  # 添加定时器
        self.planning_dots = 0  # 用于动画的点数计数

        # 初始消息发送标记
        self.flag_initial_message_sent = False

        self.init_ui()

    def init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # 创建HTML窗口用于富文本显示
        self.chat_display = wx.html2.WebView.New(panel)
        self.chat_display.SetPage(self.chat_html, "")

        # 输入区域
        self.message_input = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.message_input.SetHint("输入您的问题...")

        # 按钮
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.send_btn = wx.Button(panel, label="发送")
        self.stop_btn = wx.Button(panel, label="停止响应")
        self.test_btn = wx.Button(panel, label="test")
        self.debug_btn = wx.Button(panel, label="调试")
        self.stop_btn.Disable()

        btn_sizer.Add(self.send_btn, 1, wx.EXPAND)
        btn_sizer.Add(self.stop_btn, 1, wx.EXPAND)
        btn_sizer.Add(self.test_btn, 1, wx.EXPAND)
        btn_sizer.Add(self.debug_btn, 1, wx.EXPAND)

        # Debug窗口
        debug_sizer = wx.StaticBoxSizer(wx.VERTICAL, panel, "Debug Window")
        self.debug_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        self.debug_text.SetMinSize((-1, 150))
        debug_sizer.Add(self.debug_text, 1, wx.EXPAND | wx.ALL, 5)

        # 布局
        vbox.Add(self.chat_display, 1, wx.EXPAND | wx.ALL, 5)
        vbox.Add(self.message_input, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        vbox.Add(btn_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        vbox.Add(debug_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        panel.SetSizer(vbox)

        # 事件绑定
        self.send_btn.Bind(wx.EVT_BUTTON, self.send_message)
        self.stop_btn.Bind(wx.EVT_BUTTON, self.cancel_request)
        self.test_btn.Bind(wx.EVT_BUTTON, self.on_test)
        self.message_input.Bind(wx.EVT_TEXT_ENTER, self.send_message)

        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Bind(wx.html2.EVT_WEBVIEW_LOADED, self.on_webview_loaded, self.chat_display)

    def append_message(self, role, name, message):
        """添加消息到对话框"""
        if role == "user":
            color = "#0066cc"
        elif role == "assistant":
            color = "#009933"
        elif role == "system":
            color = "#ff6600"
        else:
            color = "#666666"

        timestamp = time.strftime("%H:%M:%S")
        escaped_message = html.escape(message).replace('\n', '<br>')

        html_message_block = f"""
            <div class='message-block' style='margin:10px 0;'>
                <div>
                    <span style='font-weight:bold;color:{color}'>{name}</span>
                    <span style='color:#999;font-size:0.8em'> ({timestamp})</span>
                </div>
                <div class='message-content' style='margin-top:5px;'>{escaped_message}</div>
            </div>
        """

        html_json = json.dumps(html_message_block)
        js_inject = f"""
            document.body.insertAdjacentHTML('beforeend', {html_json});
            window.scrollTo(0, document.body.scrollHeight);
        """
        self.chat_display.RunScript(js_inject)

        # 保存到历史记录
        if role == "user":
            self.conversation_history.append({"role": "user", "content": message})

    def update_response(self, text_chunk):
        """实时更新流式响应"""
        chunk_for_js = json.dumps(text_chunk.replace("\n", "<br>"))

        js_update = f"""
            try {{
                var contentDiv = document.querySelector('.message-block:last-child .message-content');
                if (contentDiv) {{
                    contentDiv.insertAdjacentHTML('beforeend', {chunk_for_js});
                    window.scrollTo(0, document.body.scrollHeight);
                }}
            }} catch(e) {{
                console.error('Error updating response:', e);
            }}
        """
        self.chat_display.RunScript(js_update)

    def send_message(self, event):
        """用户发送消息"""
        message = self.message_input.GetValue().strip()
        if not message:
            return

        # 如果正在处理请求，忽略
        if self.is_requesting:
            self.log_debug("已有请求正在处理中", level="WARNING")
            return

        self.append_message("user", "用户", message)
        self.message_input.Clear()

        # 启动新请求
        self._start_request()

    def start_follow_up_request(self, feedback_text):
        """
        启动后续请求（在主线程中调用）
        """
        self.log_debug("准备启动后续请求")

        # 检查是否正在处理请求
        if self.is_requesting:
            self.log_debug("已有请求正在处理中，等待...", level="WARNING")
            # 延迟重试
            wx.CallLater(200, self.start_follow_up_request, feedback_text)
            return

        # 添加反馈到历史记录
        self.conversation_history.append({"role": "user", "content": feedback_text})

        # 启动新请求
        self._start_request()

    def _start_request(self):
        """
        内部方法：启动新请求
        必须在主线程中调用
        """
        # 设置请求状态
        self.is_requesting = True

        # 禁用发送按钮
        self.send_btn.Disable()
        self.stop_btn.Enable()

        # 启动新的工作线程
        self.worker = DeepSeekWorker(self.api_key, self)
        self.worker_thread = threading.Thread(
            target=self.worker.run_query,
            args=(self.conversation_history,)
        )
        self.worker_thread.daemon = True
        self.worker_thread.start()
        self.log_debug("新请求线程已启动")

    def cancel_request(self, event):
        """取消当前响应"""
        if self.worker:
            self.worker.cancel()
            self.append_message("system", "系统", "【响应已取消】")

    def on_request_finished(self):
        """请求完成清理"""
        self.log_debug("请求完成，清理资源")
        self.send_btn.Enable()
        self.stop_btn.Disable()
        self.is_requesting = False
        self.worker = None
        self.worker_thread = None

    def on_test(self, event):
        self.log_debug("test_btn 被点击")
        pcb_assistant_utils.remove_all_tracks()

    def on_webview_loaded(self, event):
        """WebView加载完成后的初始化"""
        self.log_debug("WebView 已加载完成。")

        if not self.flag_initial_message_sent:
            self.append_message("assistant", "SCUT助手", "您好！我是来自SCUT的PCB助手。请问有什么可以帮您？")
            self.flag_initial_message_sent = True

    def on_close(self, event):
        """窗口关闭时确保停止所有线程"""
        self.log_debug("窗口正在关闭，停止所有线程")

        if self.worker:
            self.worker.cancel()

        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)

        self.Destroy()

    def log_debug(self, message, level="INFO"):
        """
        在调试窗口打印信息
        可以安全地在任何线程中调用
        """
        if not hasattr(self, 'debug_text'):
            return

        timestamp = time.strftime("%H:%M:%S")

        level_prefixes = {
            "INFO": "[INFO]",
            "DEBUG": "[DEBUG]",
            "WARNING": "[WARNING]",
            "ERROR": "[ERROR]"
        }

        prefix = level_prefixes.get(level, "[UNKNOWN]")
        formatted_msg = f"[{timestamp}] {prefix} {message}\n"

        # 直接在当前线程追加（wxPython的TextCtrl是线程安全的）
        try:
            self.debug_text.AppendText(formatted_msg)
            self.debug_text.ShowPosition(self.debug_text.GetLastPosition())
        except:
            pass  # 如果失败就忽略

    def start_planning_animation(self):
        """启动规划动作的动画"""
        self.planning_dots = 0
        # 先显示初始状态
        self.update_planning_animation()
        # 启动定时器，每500ms更新一次
        self.planning_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_planning_timer, self.planning_timer)
        self.planning_timer.Start(500)

    def on_planning_timer(self, event):
        """定时器回调，更新动画"""
        self.planning_dots = (self.planning_dots + 1) % 6  # 0,1,2,3循环
        self.update_planning_animation()

    def update_planning_animation(self):
        """更新规划动作的显示"""
        dots = "." * self.planning_dots
        text = f"思考中{dots}"

        # 注入HTML，居中显示，大字体，好看的颜色
        html_content = f"""
            <div id='planning-animation' style='text-align:left; margin:15px 0; font-size:1em; color:#6B4FBB; font-weight:bold;'>
                {text}
            </div>
        """

        js_code = f"""
            var existing = document.getElementById('planning-animation');
            if (existing) {{
                existing.remove();
            }}
            document.body.insertAdjacentHTML('beforeend', {json.dumps(html_content)});
            window.scrollTo(0, document.body.scrollHeight);
        """
        self.chat_display.RunScript(js_code)

    def stop_planning_animation(self):
        """停止并移除规划动画"""
        if self.planning_timer:
            self.planning_timer.Stop()
            self.planning_timer = None

        # 移除动画元素
        js_code = """
            var existing = document.getElementById('planning-animation');
            if (existing) {
                existing.remove();
            }
        """
        self.chat_display.RunScript(js_code)
