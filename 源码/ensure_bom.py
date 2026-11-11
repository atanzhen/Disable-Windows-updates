# -*- coding: utf-8 -*-
"""把 scripts/*.ps1 统一转成 UTF-8 带 BOM（PowerShell 5.1 必需）。"""
import glob
import os

BOM = b"\xef\xbb\xbf"

for f in sorted(glob.glob(os.path.join("scripts", "*.ps1"))):
    data = open(f, "rb").read()
    if not data.startswith(BOM):
        open(f, "wb").write(BOM + data)
        print("added BOM :", f)
    else:
        print("ok        :", f)
