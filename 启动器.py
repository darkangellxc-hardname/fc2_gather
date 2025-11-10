# -*- coding:utf-8 -*-
"""
FC2资源收集器启动器
双击运行此文件启动GUI界面
"""

import subprocess
import sys
import os

def main():
    """启动GUI应用"""
    try:
        # 确保在正确的目录下
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        
        # 启动GUI应用
        subprocess.run([sys.executable, 'fc2_gui.py'])
    except Exception as e:
        print(f"启动失败: {str(e)}")
        input("按回车键退出...")

if __name__ == "__main__":
    main()