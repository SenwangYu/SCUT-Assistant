# kicad_complex_framework/__init__.py

# 使用相对导入，从同一个包内的 pcb_assistant_action.py 文件中导入我们的动作类.
from .pcb_assistant_action import ComplexFrameworkAction

# 实例化动作类，并调用 register() 方法将其注册到 Pcbnew.
# KiCad 在启动时会自动执行这个操作.
ComplexFrameworkAction().register()