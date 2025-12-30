import os
import datetime
from pathlib import Path


def count_pdfs_by_month(target_folder, target_year, target_month):
    count = 0
    pdf_files = []

    # 转换路径对象
    folder = Path(target_folder)

    if not folder.exists():
        print(f"❌ 错误：找不到路径 -> {target_folder}")
        return 0, []

    print(f"📂 正在扫描: {target_folder}")
    print(f"🔍 目标日期: {target_year}年 {target_month}月")

    try:
        # 遍历所有文件
        for file_path in folder.rglob('*'):
            # 1. 检查是否是 PDF
            if file_path.suffix.lower() == '.pdf' and file_path.is_file():

                # 2. 获取文件修改时间
                mtime = file_path.stat().st_mtime
                mod_time = datetime.datetime.fromtimestamp(mtime)

                # 3. 比对年份和月份
                if mod_time.year == target_year and mod_time.month == target_month:
                    count += 1
                    pdf_files.append(file_path.name)

    except Exception as e:
        print(f"⚠️ 扫描错误: {e}")

    return count, pdf_files


# --- 主程序入口 ---
if __name__ == "__main__":
    # ==========================================
    # 👇 这里是你修改参数的地方 (直接修改这里即可)
    # ==========================================

    # 注意：路径前面加 r 是为了防止 \ 被当成转义符
    input_path = r"D:\博士\文献"

    target_year = 2025
    target_month = 11
    # ==========================================

    print("-" * 30)

    # 开始统计
    total_count, file_list = count_pdfs_by_month(input_path, target_year, target_month)

    print("-" * 30)
    print(f"✅ 统计完成！")
    print(f"📄 符合条件的 PDF 总数: **{total_count}** 个")

    if total_count > 0:
        print("\n具体文件列表:")
        for name in file_list:
            print(f" - {name}")
    else:
        print("\n在该月份没有找到修改过的 PDF 文件。")

    # 防止运行完窗口直接闪退（如果是双击运行的话）
    input("\n按回车键退出...")