# kicad_complex_framework/pcb_assistant_utils.py

import pcbnew
import wx
import os
import subprocess


def test():
    libname = "Resistor_SMD"
    board = pcbnew.GetBoard()
    board_path = board.GetFileName()
    dir1 = os.path.dirname(os.path.abspath(__file__))
    dir2 = os.path.dirname(os.path.dirname(os.path.dirname(dir1)))
    lib_path = dir2 + "\\footprints\\" + libname + ".pretty"
    # wx.MessageBox(lib_path)

    try:
        # 加载封装
        footprint = pcbnew.FootprintLoad(lib_path, "R_0603_1608Metric")
    except Exception as e:
        print(f"放置封装失败: {str(e)}")
        wx.MessageBox(str(e))
        return None

    # 设置位置 (单位: mm)
    footprint.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(50), pcbnew.FromMM(80)))
    footprint.SetOrientationDegrees(0)
    # 添加到 PCB
    board.Add(footprint)
    pcbnew.Refresh()


def move_footprint_by_ref(ref, xmils, ymils):
    board = pcbnew.GetBoard()
    if not board:
        return "错误: 无法加载电路板对象. 请在 Pcbnew 中运行."

    footprint = board.FindFootprintByReference(ref)
    if footprint:
        # 使用 wx.CallAfter 将设置位置的操作放入主线程队列
        # 注意：这里需要将操作封装在一个函数中，并传递必要的参数。这是为了避免线程阻塞
        def _set_position():
            footprint.SetPosition(pcbnew.VECTOR2I_Mils(xmils, ymils))
            pcbnew.Refresh()

        wx.CallAfter(_set_position)
        return True
    return False


def launch_freerouting():
    """
    启动自动布线工具
    :return:
    """

    def routing():
        current_script_dir = os.path.dirname(os.path.abspath(__file__))
        freerouting_path = os.path.join(current_script_dir, "freerouting", "freerouting-2.1.0.jar")
        # freerouting_path = "D:/Kicad/9.0/share/kicad/scripting/plugins/kicad_complex_framework/freerouting/freerouting-2.1.0.jar"
        board = pcbnew.GetBoard()
        board_path = board.GetFileName()
        base_name = os.path.splitext(board_path)[0]
        dsn_file = base_name + ".dsn"
        ses_file = base_name + ".ses"
        pcbnew.ExportSpecctraDSN(board, dsn_file)
        command = ["java", "-jar", freerouting_path, "-de", dsn_file, "-do", ses_file]
        subprocess.run(command, check=True)
        pcbnew.ImportSpecctraSES(board, ses_file)
        pcbnew.Refresh()

    wx.CallAfter(routing)


def place_footprint(lib_name, foot_print_name, x_mm, y_mm, ref, value, pad_net_map=None, rotation_deg=0):
    """
        在电路板上放置一个封装

        :param pad_net_map: 焊盘网络映射表 (可选)
        :param lib_name: 库名
        :param foot_print_name: 封装名
        :param x_mm: 放置位置 X (mm)
        :param y_mm: 放置位置 Y (mm)
        :param ref: 封装位号
        :param value: 封装数值
        :param rotation_deg: 旋转角度 (度)
        :return: footprint 对象 或 None
        """

    def pf(sub_lib_name, sub_foot_print_name, sub_x_mm, sub_y_mm, sub_ref, sub_value, sub_pad_net_map,
           sub_rotation_deg):
        try:

            board = pcbnew.GetBoard()
            dir1 = os.path.dirname(os.path.abspath(__file__))
            dir2 = os.path.dirname(os.path.dirname(os.path.dirname(dir1)))
            lib_path = dir2 + "\\footprints\\" + sub_lib_name + ".pretty"
            # wx.MessageBox(lib_path)

            try:
                # 加载封装
                footprint = pcbnew.FootprintLoad(lib_path, sub_foot_print_name)
            except Exception as e:
                wx.MessageBox("封装放置失败：" + str(e))
                return None

            # 设置位置 (单位: mm)
            footprint.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(sub_x_mm), pcbnew.FromMM(sub_y_mm)))
            footprint.SetOrientationDegrees(sub_rotation_deg)

            # 设置ref和value
            footprint.SetReference(sub_ref)
            footprint.SetValue(sub_value)

            if sub_pad_net_map is not None:
                connect_pads_to_nets(footprint, sub_pad_net_map)

            # 添加到 PCB
            board.Add(footprint)
            pcbnew.Refresh()

        except Exception as e:
            wx.MessageBox(str(e))
            return None

    result = wx.CallAfter(pf, lib_name, foot_print_name, x_mm, y_mm, ref, value, pad_net_map, rotation_deg)
    return result


def connect_pads_to_nets(target, pad_net_map):
    """
    将 footprint 中的 pad 绑定到指定网络

    :param target: pcbnew.FOOTPRINT 对象 或 footprint 的 reference 字符串
    :param pad_net_map: dict，key=pad名/编号，value=net名
                        例如 {"1": "VCC", "2": "GND"}
    """

    def sub_connect_pads_to_nets(sub_target, sub_pad_net_map):
        board = pcbnew.GetBoard()

        # 判断 target 类型
        if isinstance(target, pcbnew.FOOTPRINT):
            footprint = target
        elif isinstance(target, str):
            footprint = board.FindFootprintByReference(target)
            if footprint is None:
                raise ValueError(f"找不到参考标号 {target}")
        else:
            raise TypeError("target 必须是 pcbnew.FOOTPRINT 或 str")

        # 遍历并绑定
        for pad in footprint.Pads():
            pad_name = pad.GetName()

            if pad_name in pad_net_map:
                net_name = pad_net_map[pad_name]

                # 查找 Net，不存在则新建
                net = board.FindNet(net_name)
                if net is None:
                    net = pcbnew.NETINFO_ITEM(board, net_name)
                    board.Add(net)

                pad.SetNet(net)
                print(f"{footprint.GetReference()} - Pad {pad_name} -> Net {net_name}")

        pcbnew.Refresh()
        return True

    result = wx.CallAfter(sub_connect_pads_to_nets, target, pad_net_map)
    return result


def get_board_info():
    board = pcbnew.GetBoard()
    return board

