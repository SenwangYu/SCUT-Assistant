# kicad_complex_framework/pcb_assistant_utils.py

import pcbnew
import wx
import os
import subprocess
import pyautogui

'''
TODO:增加

'''

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
    footprint = board.FindFootprintByReference(ref)
    if footprint:
        footprint.SetPosition(pcbnew.VECTOR2I_Mils(xmils, ymils))

    wx.CallAfter(pcbnew.Refresh)
    return True


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


def query_board_footprints():
    """
    查询当前 PCB 板子上的所有封装信息
    :return: list[dict]，每个字典包含 ref, value, footprint_name, position(mm)
    """
    def query():
        board = pcbnew.GetBoard()
        result = []
        for fp in board.GetFootprints():
            ref = fp.GetReference()
            value = fp.GetValue()

            # 获取封装名
            fp_id = fp.GetFPID()
            if fp_id.IsValid():
                lib_name = fp_id.GetLibNickname()
                item_name = fp_id.GetLibItemName()
                fp_name = f"{lib_name}:{item_name}" if lib_name else item_name
            else:
                fp_name = "<未链接库>"

            # 尺寸和几何中心
            bbox = get_courtyard_bbox(fp)
            center = bbox.Centre()
            size = bbox.GetSize()

            # 获取焊盘信息
            pad_list = []
            for pad in fp.Pads():
                pad_list.append({
                    "pad编号": pad.GetPadName(),
                    "网络名": pad.GetNetname(),
                    "网络号": pad.GetNet().GetNetCode() if pad.GetNet() else None
                })

            result.append({
                "位号ref": ref,
                "值value": value,
                "库名:封装名": fp_name,
                "封装x方向长度(mils)": pcbnew.ToMils(size.x),
                "封装y方向宽度(mils)": pcbnew.ToMils(size.y),
                "位置(几何中心)": {
                    "x_mil": pcbnew.ToMils(center.x),
                    "y_mil": pcbnew.ToMils(center.y)
                },
                "pads总数": len(pad_list),
                "pads": pad_list
            })
        return result
    info = wx.CallAfter(query)
    return info


def create_board_outline(start_x_mm, start_y_mm, width_mm, height_mm, line_width_mm=0.1):
    """
    在 Edge.Cuts 层创建矩形板框
    :param start_x_mm: 左上角 X 坐标（mm）
    :param start_y_mm: 左上角 Y 坐标（mm）
    :param width_mm: 板子宽度（mm）
    :param height_mm: 板子高度（mm）
    :param line_width_mm: 线宽（mm）
    """

    def _create_outline(sub_start_x_mm, sub_start_y_mm, sub_width_mm, sub_height_mm):
        board = pcbnew.GetBoard()

        # 创建一个新的线段对象
        rect = pcbnew.PCB_SHAPE(board)
        rect.SetShape(pcbnew.SHAPE_T_RECT)  # 设置为线段类型
        rect.SetStart(pcbnew.VECTOR2I_MM(sub_start_x_mm, sub_start_y_mm))  # 设置左上角坐标 (毫米单位)
        rect.SetEnd(pcbnew.VECTOR2I_MM(sub_start_x_mm + sub_width_mm, sub_start_y_mm + sub_height_mm))  # 设置终点坐标
        rect.SetLayer(pcbnew.Edge_Cuts)  # 设置图层为 “Edge_Cuts”
        rect.SetWidth(int(line_width_mm * pcbnew.PCB_IU_PER_MM))  # 设置线宽

        board.Add(rect)  # 将线段添加到板子上
        pcbnew.Refresh()

    # 使用 wx.CallAfter 确保在主线程执行
    wx.CallAfter(_create_outline, start_x_mm, start_y_mm, width_mm, height_mm)


def get_courtyard_by_ref(ref):
    try:
        board = pcbnew.GetBoard()
        fp = board.FindFootprintByReference(ref)

        # 初始化边界框
        min_x = None
        min_y = None
        max_x = None
        max_y = None
        found_courtyard = False

        # 用item来遍历该封装的所有图形项
        # 如果遍历到的图形是在前或后courtyard，则找到了courtyard
        for item in fp.GraphicalItems():  # python中for循环中用于迭代的临时变量，会在每次迭代中自动被赋值为可迭代对象中的下一个元素，所以不需要定义。
            layer = item.GetLayer()
            if layer == pcbnew.F_CrtYd or layer == pcbnew.B_CrtYd:
                found_courtyard = True
                item_bbox = item.GetBoundingBox()

                # 更新边界框
                if min_x is None or item_bbox.GetX() < min_x:
                    min_x = item_bbox.GetX()
                if min_y is None or item_bbox.GetY() < min_y:
                    min_y = item_bbox.GetY()
                if max_x is None or (item_bbox.GetX() + item_bbox.GetWidth()) > max_x:
                    max_x = item_bbox.GetX() + item_bbox.GetWidth()
                if max_y is None or (item_bbox.GetY() + item_bbox.GetHeight()) > max_y:
                    max_y = item_bbox.GetY() + item_bbox.GetHeight()

        if not found_courtyard:
            wx.MessageBox(f"封装 '{fp.GetReference()}' 没有定义有效的前/后闭锁区 (Courtyard)。")
            return

        # 计算整体尺寸
        width_nm = max_x - min_x
        height_nm = max_y - min_y

        width_mm = pcbnew.ToMM(width_nm)
        height_mm = pcbnew.ToMM(height_nm)

        return

    except Exception as e:
        wx.MessageBox(f"发生异常: {str(e)}")


def move_footprint(ref, x_mils, y_mils):
    """把封装几何中心移动到指定坐标
    # mil单位是有边界的，最大不超过正负84545
    """
    try:
        board = pcbnew.GetBoard()
        footprint = board.FindFootprintByReference(ref)
        bbox = get_courtyard_bbox(footprint)
        center = bbox.Centre()

        # 获取原点位置
        origin = footprint.GetPosition()

        # 计算原点相对几何中心的偏移
        offset_x = center.x - origin.x
        offset_y = center.y - origin.y

        # 计算新原点位置
        new_x = int(mil2mm(x_mils) * pcbnew.PCB_IU_PER_MM - offset_x)
        new_y = int(mil2mm(y_mils) * pcbnew.PCB_IU_PER_MM - offset_y)

        wx.MessageBox("x:" + str(pcbnew.ToMils(center.x)) + " y:" + str(pcbnew.ToMils(center.y)) + "\n"
                      + "Ox:" + str(pcbnew.ToMils(origin.x)) + "y:" + str(pcbnew.ToMils(origin.y)) + "\n"
                      + "newx:" + str(pcbnew.ToMils(new_x)) + "newy:" + str(pcbnew.ToMils(new_y))
                      )

        footprint.SetPosition(pcbnew.VECTOR2I(new_x, new_y))
        wx.CallAfter(pcbnew.Refresh)
        return True
    except Exception as e:
        wx.MessageBox(f"发生异常: {str(e)}")
        return False


def get_courtyard_bbox(fp):
    """合并封装所有 Courtyard 元素的外接矩形，得到整体 bbox"""
    bbox = None
    for item in fp.GraphicalItems():
        layer = item.GetLayer()
        if layer == pcbnew.F_CrtYd or layer == pcbnew.B_CrtYd:
            item_box = item.GetBoundingBox()
            if bbox is None:
                bbox = item_box
            else:
                bbox.Merge(item_box)
    return bbox


# 先把mil转换成IU，再把IU转换成mm，来实现mil转mm
def mil2mm(mil_value):
    mm_value = pcbnew.ToMM(pcbnew.FromMils(mil_value))
    return mm_value


def mm2mil(mm_value):
    mil_value = pcbnew.ToMils(pcbnew.FromMM(mm_value))
    return mil_value
