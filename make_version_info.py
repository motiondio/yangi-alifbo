#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Versiya fayllarini yaratadi:
  * version_info.txt – Windows .exe uchun (Properties → Details), PyInstaller --version-file
  * app_version.txt  – dastur ichiga (--add-data): sozlamalar oynasi, tray menyusi, macOS Info.plist

    python make_version_info.py 1.0.4
"""
import re
import sys

TEMPLATE = """\
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={nums},
    prodvers={nums},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', 'Yangi Alifbo'),
        StringStruct('FileDescription', "Yangi o'zbek lotin alifbosi uchun avtomatik harf to'g'irlagich"),
        StringStruct('FileVersion', '{version}'),
        StringStruct('InternalName', 'YangiAlifbo'),
        StringStruct('LegalCopyright', 'Yangi Alifbo'),
        StringStruct('OriginalFilename', 'YangiAlifbo.exe'),
        StringStruct('ProductName', 'Yangi Alifbo'),
        StringStruct('ProductVersion', '{version}'),
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])]),
  ]
)
"""


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    version = (argv[0] if argv else "") or "0.0.0"
    # "1.0.4" → (1, 0, 4, 0);  raqam boʻlmagan qismlar ("1.0.4-beta") tashlab yuboriladi
    nums = [int(n) for n in re.findall(r"\d+", version)[:4]]
    nums += [0] * (4 - len(nums))
    with open("version_info.txt", "w", encoding="utf-8") as fh:
        fh.write(TEMPLATE.format(nums=tuple(nums), version=version))
    with open("app_version.txt", "w", encoding="utf-8") as fh:
        fh.write(version + "\n")
    print(f"version_info.txt, app_version.txt yaratildi: {version} {tuple(nums)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
