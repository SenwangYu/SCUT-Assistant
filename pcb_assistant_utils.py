# kicad_complex_framework/pcb_assistant_utils.py

import pcbnew
import wx
import os
import subprocess
import time

'''
TODO:增加板框绘制,绘制最小板框 ✔

10.7
TODO:新对话让view在最下面 ✔
TODO:开新窗口把旧窗口关闭，同时考虑历史是否清除 ✔    历史记录的事情再说
TODO:启动布线前需要先把现有的线删除 ✔
TODO:对话增加流式输出功能
TODO:增加元件库查询，RAG或者其它

TODO:查询函数中查询库名错误

TODO:用户历史记录管理



'''


def test():
    wx.MessageBox("TEST")
    board = pcbnew.GetBoard()
    board.ClearSelected()
    wx.CallAfter(pcbnew.Refresh)


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

    remove_all_tracks()  # 先把已经有的线删除了
    create_minimum_board_outline()

    def routing():
        current_script_dir = os.path.dirname(os.path.abspath(__file__))
        freerouting_path = os.path.join(current_script_dir, "freerouting", "freerouting-2.1.0.jar")
        # freerouting_path =
        # "D:/Kicad/9.0/share/kicad/scripting/plugins/kicad_complex_framework/freerouting/freerouting-2.1.0.jar"
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

            # sub_foot_print_name += ".kicad_mod"
            # wx.MessageBox(lib_path + "\n" + sub_foot_print_name)
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
            wx.MessageBox("????" + str(e))
            return None

    wx.CallAfter(pf, lib_name, foot_print_name, x_mm, y_mm, ref, value, pad_net_map, rotation_deg)
    return True


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


def create_board_outline(start_x_mil, start_y_mil, width_mil, height_mil, line_width_mil=2):
    """
    在 Edge.Cuts 层创建一个矩形板框
    :param start_x_mil: 左上角 X 坐标（mil）
    :param start_y_mil: 左上角 Y 坐标（mil）
    :param width_mil: 板子宽度（mil）
    :param height_mil: 板子高度（mil）
    :param line_width_mil: 线宽（mil）
    """

    board = pcbnew.GetBoard()
    # 创建一个新的线段对象
    rect = pcbnew.PCB_SHAPE()
    rect.SetShape(pcbnew.SHAPE_T_RECT)  # 设置为线段类型
    rect.SetStart(pcbnew.VECTOR2I_Mils(start_x_mil, start_y_mil))  # 设置左上角坐标 (毫米单位)
    rect.SetEnd(pcbnew.VECTOR2I_Mils(start_x_mil + width_mil, start_y_mil + height_mil))  # 设置终点坐标
    rect.SetWidth(pcbnew.FromMils(line_width_mil))  # 设置线宽
    rect.SetLayer(pcbnew.Edge_Cuts)  # 设置图层为 “Edge_Cuts”
    board.Add(rect)  # 将线段添加到板子上
    wx.CallAfter(pcbnew.Refresh)


def create_minimum_board_outline(line_width_mil=2):
    """
    删除目前Edge.Cuts层上的图形，并创建一个最小板框
    :param line_width_mil:线宽，默认为2mil
    :return:bool
    """
    remove_board_outline()

    result = record_all_bbox()
    # 如果没有封装，返回空值
    if not result:
        return False

    # 使用列表推导式提取所有边界值
    lefts = [item['left'] for item in result]
    rights = [item['right'] for item in result]
    tops = [item['top'] for item in result]
    bottoms = [item['bottom'] for item in result]

    # 计算最小/最大值
    min_left = min(lefts)
    max_right = max(rights)
    min_top = min(tops)
    max_bottom = max(bottoms)

    create_board_outline(min_left, min_top, max_right - min_left, max_bottom - min_top, line_width_mil)

    return True


def remove_board_outline():
    """
    删除edge.cuts中的所有items
    """
    try:
        board = pcbnew.GetBoard()
        # board.ClearSelected()
        # pcbnew.Refresh()

        drawings_to_delete = [d for d in list(board.GetDrawings()) if d.GetLayer() == pcbnew.Edge_Cuts]
        # time.sleep(0.05)  # 不加这个延时会闪退 再注释：修改成RemoveNative就行了

        if drawings_to_delete:
            for d in drawings_to_delete:
                # d.ClearSelected()
                board.RemoveNative(d)

        wx.CallAfter(pcbnew.Refresh)

    except Exception as e:
        wx.MessageBox(f"发生异常: {str(e)}")


def remove_all_tracks():
    """
    删除当前 PCB 板上的所有走线（包括 Tracks 和 Vias）
    """
    try:
        board = pcbnew.GetBoard()
        tracks = board.GetTracks()

        # 必须先转为独立 Python list（彻底断开 SWIG 容器引用），不然remove会把board给销毁，导致无法获取board，要彻底重启kicad才行
        tracks_to_delete = [d for d in list(tracks)]

        if tracks_to_delete:
            for d in tracks_to_delete:
                # 再逐个删除
                board.RemoveNative(d)

        wx.CallAfter(pcbnew.Refresh)

    except Exception as e:
        wx.MessageBox(f"发生异常: {str(e)}")


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

        # wx.MessageBox("x:" + str(pcbnew.ToMils(center.x)) + " y:" + str(pcbnew.ToMils(center.y)) + "\n"
        #               + "Ox:" + str(pcbnew.ToMils(origin.x)) + "y:" + str(pcbnew.ToMils(origin.y)) + "\n"
        #               + "newx:" + str(pcbnew.ToMils(new_x)) + "newy:" + str(pcbnew.ToMils(new_y))
        #               )

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


def put_next_to(ref_mobile, ref_stationary, direction, clearance=10, step=5, max_shift=1500, mode=True):
    """
    将位号为mobile_ref的封装移动到位号为stationary_ref的封装的旁边，可以是上下左右，用direction表示
    :param mode: 布局模式，mode==False表示紧凑模式，mode==True表示正常模式（默认）。用户要求布局紧凑的时候用紧凑模式
    :param step: 如过目标位置有碰撞发生，迭代平移直到不碰撞的步长
    :param max_shift: 迭代平移的最大偏移量，默认1500mil
    :param clearance: 安全间距，默认10mil
    :param ref_mobile: 要移动的封装位号
    :param ref_stationary: 锚定的封装位号
    :param direction:要移动到的位置
    :return bool
    """
    board = pcbnew.GetBoard()
    # 首先获取两个封装的庭院层大小，再获取锚定封装的几何中心坐标
    fp_mobile = board.FindFootprintByReference(ref_mobile)
    fp_stationary = board.FindFootprintByReference(ref_stationary)
    bbox_mobile = get_courtyard_bbox(fp_mobile)
    bbox_stationary = get_courtyard_bbox(fp_stationary)
    center_stationary = bbox_stationary.Centre()
    size_mobile = bbox_mobile.GetSize()
    size_stationary = bbox_stationary.GetSize()
    # 待移动封装的长宽(mils) 
    length_mobile = pcbnew.ToMils(size_mobile.x)
    width_mobile = pcbnew.ToMils(size_mobile.y)

    # 锚定封装的长宽(mils) 
    length_stationary = pcbnew.ToMils(size_stationary.x)
    width_stationary = pcbnew.ToMils(size_stationary.y)

    # 锚定封装的几何中心
    x_reference = pcbnew.ToMils(center_stationary.x)
    y_reference = pcbnew.ToMils(center_stationary.y)

    # 安全间距clearance
    # 步长

    # 通过direction的值来决定怎么放，0到3分别对应上下左右
    # 初始目标位置
    if direction == 0:  # 上
        y_target = y_reference - (width_stationary / 2 + width_mobile / 2 + clearance)
        x_target = x_reference
        dx, dy = 0, -step
    elif direction == 1:  # 下
        y_target = y_reference + (width_stationary / 2 + width_mobile / 2 + clearance)
        x_target = x_reference
        dx, dy = 0, step
    elif direction == 2:  # 左
        x_target = x_reference - (length_stationary / 2 + length_mobile / 2 + clearance)
        y_target = y_reference
        dx, dy = -step, 0
    elif direction == 3:  # 右
        x_target = x_reference + (length_stationary / 2 + length_mobile / 2 + clearance)
        y_target = y_reference
        dx, dy = step, 0
    else:
        raise ValueError("direction 必须是 0~3 (0=上, 1=下, 2=左, 3=右)")

    # 迭代平移直到不碰撞或超出范围

    shift = 0
    while shift <= max_shift:
        if not check_collision(ref_mobile, x_target, y_target, mode):
            move_footprint(ref_mobile, x_target, y_target)
            return True
        x_target += dx
        y_target += dy
        shift += step

    return False  # 找不到合适位置


def check_collision(ref_mobile, x_target, y_target, mode):
    """
    检测是否有碰撞
    :param y_target: 目标y
    :param x_target: 目标x
    :param ref_mobile: 要移动的封装位号
    :param mode:检测模式，mode==False表示courtyard模式，mode==True表示boundingBox模式（会检测丝印等的重叠）
    :return bool
    """

    board = pcbnew.GetBoard()
    # 获取待检测封装的上下左右边界
    fp_check = board.FindFootprintByReference(ref_mobile)
    bbox_check = get_courtyard_bbox(fp_check)
    size_check = bbox_check.GetSize()
    # 上下左右边界
    check_left = x_target - pcbnew.ToMils(size_check.x) / 2
    check_top = y_target - pcbnew.ToMils(size_check.y) / 2
    check_right = x_target + pcbnew.ToMils(size_check.x) / 2
    check_bottom = y_target + pcbnew.ToMils(size_check.y) / 2
    # 要记录所有的封装的庭院层,遍历所有元件的位置，记录到dict中

    if not mode:
        result = record_all_courtyard()
    else:
        result = record_all_bbox()
    # 满足不重叠的条件是，上边界小于下边界或左边界小于有边界或右边界小于左边界或下边界小于上边界
    # 判断是否和其他元件重叠
    for item in result:
        # 跳过自己，避免和自己检测碰撞
        if item["ref"] == ref_mobile:
            continue
        # 只要不满足“不重叠”的任一条件，即重叠
        if not (
                check_right <= item["left"] or  # 在左边
                check_left >= item["right"] or  # 在右边
                check_bottom <= item["top"] or  # 在上面
                check_top >= item["bottom"]  # 在下面
        ):
            # 发生碰撞
            return True
    return False


def record_all_courtyard():
    """
    返回一个记录所有封装的courtyard的字典
    """
    board = pcbnew.GetBoard()
    result = []
    for fp in board.GetFootprints():
        courtyard = get_courtyard_bbox(fp)
        center_courtyard = courtyard.Centre()
        size_courtyard = courtyard.GetSize()
        courtyard_length = pcbnew.ToMils(size_courtyard.x)
        courtyard_width = pcbnew.ToMils(size_courtyard.y)
        x_mil = pcbnew.ToMils(center_courtyard.x)
        y_mil = pcbnew.ToMils(center_courtyard.y)
        # 上下左右边界
        boundary_left = x_mil - courtyard_length / 2
        boundary_top = y_mil - courtyard_width / 2
        boundary_right = x_mil + courtyard_length / 2
        boundary_bottom = y_mil + courtyard_width / 2
        result.append(
            {
                "ref": fp.GetReference(),
                'top': boundary_top,
                'bottom': boundary_bottom,
                'left': boundary_left,
                'right': boundary_right
            }
        )
    return result


def record_all_bbox():
    """
    返回一个记录所有封装的BoundingBox的字典
    """
    board = pcbnew.GetBoard()
    record_bbox = []
    for fp in board.GetFootprints():
        bbox = fp.GetBoundingBox()
        center_bbox = bbox.Centre()
        size_bbox = bbox.GetSize()
        bbox_width = pcbnew.ToMils(size_bbox.y)
        bbox_length = pcbnew.ToMils(size_bbox.x)
        x_mil = pcbnew.ToMils(center_bbox.x)
        y_mil = pcbnew.ToMils(center_bbox.y)
        # 上下左右边界
        boundary_left = x_mil - bbox_length / 2
        boundary_top = y_mil - bbox_width / 2
        boundary_right = x_mil + bbox_length / 2
        boundary_bottom = y_mil + bbox_width / 2
        record_bbox.append(
            {
                "ref": fp.GetReference(),
                'top': boundary_top,
                'bottom': boundary_bottom,
                'left': boundary_left,
                'right': boundary_right
            }
        )
    return record_bbox
