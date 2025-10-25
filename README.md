# SCUT PCB Assistant (KiCad AI Agent)

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Version](https://img.shields.io/badge/python-3.8+-brightgreen.svg)
![KiCad Version](https://img.shields.io/badge/KiCad-7.0+-blue.svg)
![Framework](https://img.shields.io/badge/Framework-wxPython-lightgrey.svg)

一个强大的、基于大语言模型（LLM）的PCB设计智能体，专为KiCad打造。它允许您通过自然语言对话，将复杂的设计意图直接转化为电路板上的精确操作，旨在成为工程师最高效的“执行副驾”，从而颠覆传统PCB设计工作流。



## 目录

- [核心特性](#核心特性)
- [架构设计](#架构设计)
- [演示：效率提升](#演示效率提升)
- [环境配置与安装](#环境配置与安装)
- [如何使用](#如何使用)
- [工作原理解析](#工作原理解析)
- [许可协议](#许可协议)

## 核心特性

*   **自然语言驱动**: 告别繁琐的菜单和点击，像与真人助手对话一样，用自然语言完成专业设计任务（例如，“将C1放在R1右边，间距20mil”）。
*   **自主任务规划**: 能够理解宏观设计目标（如“为电路初步布局”），并自主将其分解为一系列逻辑连贯的、可执行的子任务序列。
*   **智能布局与避障**: 具备高级布局能力，如`put_next_to`。在放置元件时，能够主动进行碰撞检测，并以螺旋式或迭代方式智能搜寻无冲突的最佳位置。
*   **闭环自我纠错**: 内置“执行-观察-反思”循环，能自动发现并修正执行过程中的错误（如API调用失败），极大降低人工干愈。
*   **外部工具集成**: 成功集成了外部`freerouting.jar`，实现了全自动布线的一键启动。
*   **实时流式反馈**: AI的思考与执行过程以流式文本实时展现，杜绝未知等待，整个交互过程高度透明、可追溯。
*   **非阻塞式UI**: 采用多线程异步架构，即使在执行自动布线等耗时任务时，界面也保持100%流畅响应。
*   **易于扩展的工具集**: 所有PCB操作均被封装为原子化的工具函数（见`pcb_assistant_utils.py`），可以轻松地为智能体添加新的设计能力。

## 架构设计


1.  **智能交互层 (`pcb_assistant_action.py`, `wx_gui.py`)**: 基于`wxPython`构建的图形用户界面。`pcb_assistant_action.py`作为KiCad插件入口，负责启动和管理UI窗口。UI层负责接收用户输入，并实时、异步地展示智能体的思考和执行过程。

2.  **决策生成层 (后台工作线程)**: 项目的“大脑”。它在独立的线程中运行，负责与大语言模型（如DeepSeek）进行通信，根据用户指令和上下文生成决策，并调用下层工具来执行。

3.  **执行控制层 (`pcb_assistant_utils.py`)**: 项目的“双手”。它将KiCad复杂、过程化的Python API封装成一系列功能明确、原子化的“工具函数”（如`move_footprint`, `put_next_to`, `create_zone`等），供决策层调用。

## 演示：效率提升

为了量化本助手带来的效率提升，我们进行了一项对比测试：

**任务**: 对一块**交错并联BUCK变换器**的PCB进行初步布局，包含核心功率器件的放置、高频环路优化、电源与地平面敷铜等操作。

*   **传统手动设计**: 一名熟练工程师在KiCad中完成该任务，平均耗时约 **30分钟**。
*   **智能体辅助设计**: 工程师通过本助手下达数个高级指令，在 **5分钟以内** 完成了同等质量的布局。

**结论**: 在此典型场景下，本智能体可将设计效率提升 **500%** 以上。

## 环境配置与安装

请确保您的环境中已安装 **Python 3.8+**、**KiCad (版本 >= 7.0)** 和 **Java Runtime Environment (JRE)**。

1.  **克隆项目仓库**
    ```bash
    git clone https://github.com/YOUR_USERNAME/kicad_complex_framework.git
    cd kicad_complex_framework
    ```
    *(请将 `YOUR_USERNAME` 替换为您的Github用户名)*

2.  **安装Python依赖**
    项目依赖项已在`requirements.txt`中列出。
    ```bash
    pip install -r requirements.txt
    ```
    *如果您尚未创建`requirements.txt`，请包含`deepseek`或`requests`以及`wxPython`（如果KiCad的Python环境未包含）。*

3.  **配置API密钥**
    请在项目根目录下创建一个名为 `config.ini` 的文件，并填入您的大语言模型API密钥。
    ```ini
    [api]
    api_key = sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    ```
    *注意：您需要修改 `pcb_assistant_action.py` 中的代码，使其从 `config.ini` 读取API密钥，而不是硬编码。*

4.  **放置插件**
    将整个`kicad_complex_framework`文件夹复制到KiCad的插件目录中。您可以在KiCad的 "工具" -> "插件和内容管理器" -> "打开插件目录" 中找到此路径。

5.  **刷新插件**
    重启KiCad，或在 "工具" -> "外部插件" 中选择 "刷新插件"。

## 如何使用

1.  **启动助手**
    在KiCad的Pcbnew编辑器中，点击顶部工具栏的 "SCUT助手" 图标，或通过菜单 "工具" -> "外部插件" -> "SCUT助手" 启动。

2.  **开始对话**
    在应用界面的输入框中，用自然语言描述您的设计需求。

    **简单指令示例:**
    > 将封装 `U1` 移动到坐标 `(101.6, 76.2)`。
    >
    > 查询板上所有封装的信息。
    >
    > 删除所有走线并重新进行自动布线。

    **复杂布局指令示例:**
    > 将 `C1` 放置在 `U1` 的右侧，间距20mil。

    **连锁任务示例:**
    > 1. 先帮我查一下板子上所有的网络名。
    > 2. 好的，现在为`GND`网络创建敷铜。

## 工作原理解析

当用户输入指令后，主UI线程会将其传递给后台的工作线程，启动一个“决策-执行”循环：

1.  **推理与规划**: 工作线程将用户指令、对话历史以及预设的系统提示（System Prompt，其中包含了所有可用工具的定义）一同发送给大语言模型。
2.  **流式响应**: LLM以流式（Streaming）方式返回其思考过程和决策。UI层捕获这些数据流，并以200ms的间隔批量刷新界面，实现文字的实时“打字机”效果。
3.  **工具调用**: 当LLM的回复中包含特定的工具调用指令时（例如，`tool_code: put_next_to("C1", "U1", direction=3, clearance=20)`），程序会解析该指令并调用`pcb_assistant_utils.py`中对应的Python函数。所有对KiCad的操作都通过`wx.CallAfter`安全地在主线程中执行。
4.  **观察与反馈**: 工具函数的执行结果（无论成功或失败）都会被格式化后，作为一条“执行反馈”消息追加到对话历史中。
5.  **反思与迭代**: 这条反馈会立即作为新的上下文信息，再次提交给LLM。如果上一步出错了，LLM会“观察”到错误信息，并进行“反思”，尝试修正指令后重新执行，或向用户提问，形成一个完整的自主纠错闭环。


## 许可协议

本项目基于 [MIT License](LICENSE.md) 授权。
