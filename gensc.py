import os
import binascii
import glob

excluded = [".DS_Store", "gensc.py", "xpdepot.py", "docs", "mkdocs.yml"]


def is_excluded(f):
    return f in excluded or "__pycache__" in f or "skunkcrafts_" in f or f.startswith("docs")


files = {}
for f in glob.glob("**", recursive=True):
    if os.path.isfile(f) and not is_excluded(f):
        buf = open(f, "rb").read()
        crc = binascii.crc32(buf) & 0xFFFFFFFF
        files[f] = {"size": os.path.getsize(f), "crc32": f"{crc:d}"}

files = dict(sorted(files.items()))


def out(what):
    for f, v in files.items():
        print(f"{f}|{v[what]}")

# out("size")
out("size")
