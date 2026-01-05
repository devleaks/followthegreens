#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# I indent with tabs (size 4) and this is not up for discussion. If unhappy with it, get a life.
# License: come on, these are only a few lines of code
# Do whatever you want with them, at your own risks, except saying you wrote them.
# v3

# begin of user config
# always use / (no backslash), even on windows.
# ftp servers must support MLSD command (RFC 3659)
zones = {
    "aerobask": {
        "local": "/data2/depots/aerobask",
        "ftp": "xxx.xxx.com",
        "base": "/",
        "user": "username",
        "pass": "password",
    },
    "skunkcrafts": {
        "local": "/data2/depots/skunkcrafts",
        "ftp": "xxx.xxx.com",
        "base": "/",
        "user": "username",
        "pass": "password",
    },
    "custom": {
        "local": "/data2/depots/custom",
        "ftp": "xxx.xxx.com",
        "base": "/",
        "user": "username",
        "pass": "password",
    },
}
# end of user config

import os, sys, glob, io
import binascii
import shutil
import ftplib

commands = ["lock", "unlock", "status", "check", "update", "deadmeat"]
notdeadmeat = [
    "skunkcrafts_updater_sizeslist.txt",
    "skunkcrafts_updater_whitelist.txt",
    "skunkcrafts_updater_blacklist.txt",
    "skunkcrafts_updater.cfg",
]
ignorelist = [
    "skunkcrafts_updater_sizeslist.txt",
    "skunkcrafts_updater_whitelist.txt",
    "skunkcrafts_updater_blacklist.txt",
    "skunkcrafts_updater_oncelist.txt",
    "skunkcrafts_updater_ignorelist.txt",
    "skunkcrafts_updater_config.txt",
]
blacklist = []
oncelist = []
deltalist = {}
newwhite = {}
oldwhite = {}
sizeslist = {}

rmtconfig = "skunkcrafts_updater.cfg"
lclconfig = "skunkcrafts_updater_config.txt"
blackname = "skunkcrafts_updater_blacklist.txt"
whitename = "skunkcrafts_updater_whitelist.txt"
sizesname = "skunkcrafts_updater_sizeslist.txt"
ignorename = "skunkcrafts_updater_ignorelist.txt"
oncename = "skunkcrafts_updater_oncelist.txt"


def bozo(reason):
    print(reason)
    print(f"Usage: {sys.argv[0]} zone aircraft command")
    print("Commands: lock, unlock, check, update, deadmeat")
    exit(1)


def fatal(reason):
    print(f"Fatal error: {reason}")
    exit(1)


def success(reason):
    print(f"Success: {reason}")
    exit()


if len(sys.argv) != 4:
    bozo(f"Incorrect number of arguments {len(sys.argv)}")

zone = sys.argv[1]
acf = sys.argv[2]
cmd = sys.argv[3]

src = "/tmp"
dst = "/tmp"

if not zone in zones:
    fatal(f"Unknown zone {zone}")

zone = zones[zone]
src = (zone["local"] + "/" + acf).replace("//", "/")
ftp_fqdn = zone["ftp"]
ftp_user = zone["user"]
ftp_pass = zone["pass"]
ftp_base = (zone["base"] + "/" + acf).replace("//", "/")

if not os.path.isdir(src):
    fatal(f"{src} is not a valid folder")

try:
    print(f"ftp to: {ftp_fqdn}")
    ftp = ftplib.FTP(ftp_fqdn)
    print(f"login with: {ftp_user}")
    ftp.login(user=ftp_user, passwd=ftp_pass)
    print(f"cwd to: {ftp_base}")
    ftp.cwd(ftp_base)
except ftplib.all_errors as error:
    fatal(f"ftp to {ftp_fqdn} as {ftp_user} failed: {error} ")


def CRC32_from_file(filename):
    buf = open(filename, "rb").read()
    buf = binascii.crc32(buf) & 0xFFFFFFFF
    return f"{buf:d}"


def rmtconfig_read():
    print("Reading remote config")
    config = {}

    def readcfg(line):
        fi = line.split("|")
        if len(fi) == 2:
            config[fi[0]] = fi[1]

    try:
        ftp.cwd(ftp_base)
        ftp.retrlines(f"RETR {rmtconfig}", readcfg)
        return config
    except ftplib.all_errors as error:
        fatal(f"{ftp_fqdn}: RETR {ftp_base}/{rmtconfig} failed: {error} ")


def rmtconfig_write(config):
    print("Writing remote config")
    buf = io.BytesIO()
    for k, v in config.items():
        buf.write(str.encode(f"{k}|{v}\n"))
    buf.seek(0)
    try:
        ftp.cwd(ftp_base)
        ftp.storbinary(f"STOR {rmtconfig}", buf)
    except ftplib.all_errors as error:
        fatal(f"{ftp_fqdn}: STOR {ftp_base}/{rmtconfig} failed: {error} ")


def change_lock(lock):
    print("Changing lock")
    config = rmtconfig_read()
    lock = "true" if lock else "false"
    if "locked" in config and config["locked"] == lock:
        print(f"Lock already {lock}")
    config["locked"] = lock
    rmtconfig_write(config)


def get_lock():
    config = rmtconfig_read()
    return "locked" in config and config["locked"] == "true"


def load_list(name, lst):
    fname = f"{src}/{name}"
    try:
        with open(fname, "r") as fh:
            lst += fh.read().splitlines()
        for line in lst:
            line = line.replace("\\", "/")
    except IOError as error:
        fatal(f"failed to read {fname} : {error}")


if cmd not in commands:
    bozo(f"Command '{cmd}' not recognized")

if cmd == "lock":
    change_lock(True)
    success("Remote depot locked")

if cmd == "unlock":
    change_lock(False)
    success("Remote depot unlocked")

if cmd == "status":
    success(f"Remote depot lock is {get_lock()}")

os.chdir(src)

# Get remote whitelist
print("Getting remote whitelist")


def read_oldwhite(line):
    fi = line.split("|")
    if len(fi) == 2:
        oldwhite[fi[0].replace("\\", "/")] = fi[1]


try:
    ftp.retrlines(f"RETR {whitename}", read_oldwhite)
except ftplib.all_errors as error:
    fatal(f"{ftp_fqdn}: RETR {ftp_base}/{whitename} failed: {error} ")


def tree_ftp(mylist, mypath):
    for entry, facts in ftp.mlsd():
        f = facts["type"]
        if f == "dir":
            pwd = ftp.pwd()
            ftp.cwd(entry)
            tree_ftp(mylist, mypath + "/" + entry)
            ftp.cwd(pwd)
        elif f == "file":
            mylist.append(str.lstrip(mypath + "/" + entry, "/"))


if cmd == "deadmeat":
    mylist = []
    ftp.cwd(ftp_base)
    print("Files in depot but not in whitelist:")
    tree_ftp(mylist, "")
    for entry in sorted(mylist, key=str.lower):
        if entry not in oldwhite and entry not in notdeadmeat:
            print(entry)
    exit()

# Populate lists
print("Getting ignorelist")
load_list(ignorename, ignorelist)
print("Getting blacklist")
load_list(blackname, blacklist)
print("Getting oncelist")
load_list(oncename, oncelist)

# Build local whitelist
print("Populating new white list")
for entry in sorted(glob.iglob("**", recursive=True), key=str.lower):
    if os.path.isfile(entry):
        posix_entry = entry.replace("\\", "/")
        if posix_entry in oncelist:
            newwhite[posix_entry] = -1
            sizeslist[posix_entry] = os.path.getsize(entry)
        elif posix_entry in ignorelist:
            pass
        else:
            newwhite[posix_entry] = CRC32_from_file(posix_entry)
            sizeslist[posix_entry] = os.path.getsize(entry)

with open(whitename, "w", newline="\n") as fh:
    for entry, crc in newwhite.items():
        fh.write(f"{entry}|{crc}\n")

with open(sizesname, "w", newline="\n") as fh:
    for entry, crc in sizeslist.items():
        fh.write(f"{entry}|{crc}\n")

# Look for delta
print("Looking for new/modified files")
for entry, crc in newwhite.items():
    posix_entry = entry.replace("\\", "/")
    if posix_entry in oldwhite:
        if crc != oldwhite[posix_entry] and crc != -1:
            deltalist[posix_entry] = f"new crc {crc}"
    else:
        deltalist[posix_entry] = "new file"

if cmd == "check":
    for entry, reason in deltalist.items():
        print(f"Need to send '{entry}' : {reason}")
    if len(entry) == 0:
        print("Nothing to do")
    exit()


def ftp_check_dir(mydir):
    try:
        ftp.cwd(mydir)
        return
    except ftplib.all_errors as error:
        ftp.mkd(mydir)
        ftp.cwd(mydir)


def ftp_chdir(
    ftp_path,
):
    dirs = [d for d in ftp_path.split("/") if d != ""]
    for p in dirs:
        print(p)
        check_dir(p)


def check_dir(folder):
    filelist = []
    ftp.retrlines("LIST", filelist.append)
    found = False

    for f in filelist:
        if f.split()[-1] == folder and f.lower().startswith("d"):
            found = True

    if not found:
        ftp.mkd(folder)
    ftp.cwd(folder)


# ~ def ftp_check_dir(mydir):
# ~ for entry, facts in ftp.mlsd():
# ~ if entry == mydir and facts["type"] == "dir":
# ~ ftp.cwd(entry)
# ~ return
# ~ ftp.mkd(mydir)
# ~ print(f"cwd({mydir})")
# ~ ftp.cwd(mydir)

# ~ old_ftp_path = "something that does not exists"
# ~ def ftp_chdir(ftp_path):
# ~ print(f"chdir to: {ftp_path}")
# ~ global old_ftp_path
# ~ if old_ftp_path == ftp_path:
# ~ return
# ~ ftp.cwd(f"{ftp_base}")
# ~ dirs = [d for d in ftp_path.split('/') if d != '']
# ~ for p in dirs:
# ~ ftp_check_dir(p)
# ~ old_ftp_path = ftp_path


def ftp_chdir(ftp_path):
    try:
        # ~ print(f"trying ftp.cwd({ftp_path})")
        ftp.cwd(ftp_path)
        return
    except ftplib.all_errors as error:
        ftp_less, folder = os.path.split(ftp_path)
        # ~ print(f"Error, now trying {ftp_less}")
        ftp_chdir(ftp_less)
        wd = ftp.pwd()
        # ~ print(f"In {wd} doing ftp.mkd({folder})")
        ftp.mkd(folder)
        # ~ print(f"Retrying chdir to {ftp_less}")
        ftp_chdir(ftp_path)


def ftp_send(src, dst):
    try:
        fh = open(src, "rb")
    except IOError as error:
        fatal(f"failed to open {src}, partial update! : {error}")

    try:
        path, dest = os.path.split(f"{ftp_base}/{dst}")
        ftp_chdir(path)
        # ~ wd = ftp.pwd()
        # ~ print(f"ftp.pwd() = {wd}")
        # ~ print(f"STOR {dest}")
        ftp.storbinary(f"STOR {dest}", fh)
        fh.close()
    except ftplib.all_errors as error:
        fatal(f"{ftp_fqdn}: ftp_chdir({path}) then STOR {dest} failed: {error} ")


if cmd == "update":
    for entry, reason in deltalist.items():
        print(f"Sending '{entry}' ({reason})")
        ftp_send(entry, entry)
    print(f"Sending {whitename}")
    ftp_send(whitename, whitename)
    print(f"Sending {blackname}")
    ftp_send(blackname, blackname)
    print(f"Sending {sizesname}")
    ftp_send(sizesname, sizesname)
    print(f"Sending {rmtconfig}")
    ftp_send(lclconfig, rmtconfig)
    success(f"Update finished and remote depot lock is {get_lock()}")

    exit()

print("Control should not reach this statement")
exit()
