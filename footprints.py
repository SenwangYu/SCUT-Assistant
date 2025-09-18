import os
import json


def generate_footprint_summary(footprints_dir):
    summary = {}

    # 遍历footprints目录
    for lib_dir in os.listdir(footprints_dir):
        lib_path = os.path.join(footprints_dir, lib_dir)

        # 检查是否为.pretty目录
        if os.path.isdir(lib_path) and lib_dir.endswith('.pretty'):
            lib_name = lib_dir[:-7]  # 移除".pretty"后缀
            footprints = []

            # 遍历库目录中的文件
            for file in os.listdir(lib_path):
                if file.endswith('.kicad_mod'):
                    # 移除文件扩展名作为封装名
                    footprint_name = file[:-11]
                    footprints.append(footprint_name)

            summary[lib_name] = footprints

    return summary


if __name__ == "__main__":
    footprints_dir = 'D://Kicad//9.0//share//kicad//footprints'  # 修改为你的实际路径
    summary = generate_footprint_summary(footprints_dir)

    # 输出JSON格式结果
    print(json.dumps(summary, indent=2))

    # # 可选：输出人类可读格式
    # print("\nHuman-readable summary:")
    # for lib, footprints in summary.items():
    #     print(f"\n{lib}:")
    #     for fp in footprints:
    #         print(f"  - {fp}")