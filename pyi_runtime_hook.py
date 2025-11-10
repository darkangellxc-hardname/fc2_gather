import os
import sys
import shutil


def _copy_from_meipass(filename: str) -> None:
    try:
        base = getattr(sys, "_MEIPASS", None)
        if not base:
            return
        src = os.path.join(base, filename)
        if not os.path.exists(src):
            return
        dst = os.path.join(os.getcwd(), filename)
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
    except Exception:
        pass


for _name in ["ico.ico", "README.md", "fc2_core.py"]:
    _copy_from_meipass(_name)