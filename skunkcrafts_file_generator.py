import os
import binascii
import glob

from PI_FollowTheGreens import __VERSION__, __NAME__

WRITE_FILE = True

excluded = [".DS_Store", "gensc.py", "xpdepot.py", "docs", "mkdocs.yml", "ftg_log.txt", "PI_test.py"]
starts_with = ["docs", "out", "temp"]
contains = ["skunkcrafts_", "ftgprefs", "globals-"]


def is_excluded(f):
    return f in excluded or any([c in f for c in contains]) or any([f.startswith(w) for w in starts_with])


candidates = []
if os.path.exists("skunkcrafts_updater_sizeslist.txt"):
    with open("skunkcrafts_updater_sizeslist.txt", "r") as fp:
        candidates = [f.strip().split("|")[0] for f in fp.readlines()]
    print("using sizelist file, to add a file, add it to the sizelist file with size 0")
elif os.path.exists("skunkcrafts_updater_files.txt"):
    with open("skunkcrafts_updater_files.txt", "r") as fp:
        candidates = [f.strip() for f in fp.readlines()]
    print("using file list, to add a file, add its name to the file")
else:
    candidates = glob.glob("**", recursive=True)
    print("using glob")

files = {}
black_list = []
for f in candidates:
    if os.path.isfile(f) and not is_excluded(f):
        buf = open(f, "rb").read()
        crc = binascii.crc32(buf) & 0xFFFFFFFF
        files[f] = {"size": os.path.getsize(f), "crc32": f"{crc:d}"}
    else:
        black_list.append(f)

files = dict(sorted(files.items()))


def out(what):
    for f, v in files.items():
        print(f"{f}|{v[what]}")


r = f"""module|https://raw.githubusercontent.com/devleaks/followthegreens/refs/heads/main
name|{__NAME__}
version|{__VERSION__}
disabled|false
locked|false
zone|custom
"""

print(f"{len(files)} files")
print("--- sizes")
out("size")
print("--- crc32")
out("crc32")
print(f"---\n{r}")

if WRITE_FILE:
    with open("skunkcrafts_updater_sizeslist.txt", "w") as fp:
        for f, v in files.items():
            print(f"{f}|{v["size"]}", file=fp)
    with open("skunkcrafts_updater_whitelist.txt", "w") as fp:
        for f, v in files.items():
            print(f"{f}|{v["crc32"]}", file=fp)
    with open("skunkcrafts_updater.cfg", "w") as fp:  # Changes BETA only
        print(r, file=fp)
