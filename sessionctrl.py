#!/usr/sbin/python3

'''
This tool allows you to save your desktop session.

This tool has 2 dependencies:
    1) wmctrl <https://sites.google.com/site/tstyblo/wmctrl>
    2) xprop  <https://www.x.org/archive/X11R6.7.0/doc/xprop.1.html>
in order to interact with the X Windows.

Note:
The development of wmctrl seems to have halted. There are several versions
floating around on the web, but none are from the original author.

With that in mind, minimizing a window is not supported by the official version,
but is supported in another version. This tool will utilize the official
version for the sake of simplicity. As a result, 'minimized' windows will not
actually be minimized when restoring a session.

See here: <https://bugs.launchpad.net/ubuntu/+source/wmctrl/+bug/260875>
'''

import os
import re
import sys
import subprocess
import shlex
import json
import time
import argparse
import base64
from pprint import pprint

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument('-r', action="store_true", help="restores session")
group.add_argument('-s', action="store_true", help="saves session")
group.add_argument(
    '-m',
    action="store_true",
    help="only moves already open windows")

args = parser.parse_args()

global blacklist
global replace_apps

blacklist = []
replace_apps = []

conf_file_path = "{}/.sessionctrl.conf".format(os.path.expanduser("~"))
session_file_path = "{}/.sessionctrl.info".format(os.path.expanduser("~"))

# Create config file if it does not exist.
# Otherwise parse the config file for the blacklist and replace_apps.
if not os.path.isfile(conf_file_path):
    with open(conf_file_path, 'w') as f:
        f.write("blacklist=\n")
        f.write("replace_apps=\n")
else:
    with open(conf_file_path, 'r') as f:
        for line in f.readlines():
            if line.startswith("blacklist="):
                blacklist = [
                    x.strip() for x in line[
                        line.index('=') +
                        1:].split(' ')]
            elif line.startswith("replace_apps="):
                replace_apps = [
                    x.strip() for x in line[
                        line.index('=') +
                        1:].split(' ')]

# print(blacklist)
# print(replace_apps)

wm_states = {
    # "_NET_WM_STATE_MODAL": "modal",
    # "_NET_WM_STATE_STICKY": "sticky",
    "_NET_WM_STATE_MAXIMIZED_VERT": "maximized_vert",
    "_NET_WM_STATE_MAXIMIZED_HORZ": "maximized_horz",
    # "_NET_WM_STATE_SHADED": "shaded",
    # "_NET_WM_STATE_SKIP_TASKBAR": "skip_taskbar",
    # "_NET_WM_STATE_SKIP_PAGER": "skip_pager",
    "_NET_WM_STATE_HIDDEN": "hidden",
    # "_NET_WM_STATE_FULLSCREEN": "fullscreen",
    # "_NET_WM_STATE_ABOVE": "above",
    # "_NET_WM_STATE_BELOW": "below"
}

# Sanity check for dependencies
with subprocess.Popen(shlex.split("which wmctrl"), stdout=subprocess.PIPE) as proc:
    try:
        proc.wait(timeout=5)
    except TimeoutExpired as e:
        print("Timeout expired checking for wmctrl")
        sys.exit(-1)

    if proc.returncode != 0:
        print(proc.returncode, "Please install wmctrl as it is a dependency.")
        sys.exit(-1)

with subprocess.Popen(shlex.split("which xprop"), stdout=subprocess.PIPE) as proc:
    try:
        proc.wait(timeout=5)
    except TimeoutExpired as e:
        print("Timeout expired checking for xprop")
        sys.exit(-1)

    if proc.returncode != 0:
        print("Please install xprop as it is a dependency.")
        sys.exit(-1)

# sys.exit(0)


def _get_open_windows(cmd):
    p = subprocess.Popen(
        shlex.split(cmd),
        stdout=subprocess.PIPE,
        universal_newlines=True)

    return p.communicate()[0].replace("\u0000", "").split('\n')


def _get_exec_path(pid):
    return subprocess.Popen(
        shlex.split("strings /proc/{}/cmdline".format(pid)),
        stdout=subprocess.PIPE, universal_newlines=True) \
        .communicate()[0] \
        .replace("\u0000", "") \
        .replace('\n', ' ') \
        .strip()


def save_session():
    cmd = "wmctrl -lpG"
    re_str = (
        "^([x0-9a-f]+)\\s+(-?[0-9]+)\\s+([0-9]+)\\s+([0-9]+)\\s+"
        "([0-9]+)\\s+([0-9]+)\\s+([0-9]+)\\s+[^\\s]+[\\s]+(.+$)")

    d = {}
    windows = _get_open_windows(cmd)
    for window in windows:
        blacklisted = False

        m = re.search(re_str, window)
        if m:
            _wid = m.group(1)
            desktop = m.group(2)
            pid = int(m.group(3))
            geo = (int(m.group(4)), int(m.group(5)),
                   int(m.group(6)), int(m.group(7)))

            # If pid is 0 then the application does not support windows.
            if pid == 0:
                continue

            # Skip over desktop-specific windows.
            if desktop == "-1":
                continue

            # Get command of the application.
            exec_path = _get_exec_path(pid)

            for item in blacklist:
                if item in exec_path:
                    blacklisted = True
                    break

            # Encode window name into base64 and store the ASCII of the
            # base64 string into JSON because it expects strings,
            # not binary data.
            window_name = json.dumps(
                base64.urlsafe_b64encode(bytes(m.group(8), "utf-8"))
                .decode('ascii'))

            # Substitute applications from predetermined list.
            # Some applications such as 'Android Studio' do not show up as themselves,
            # rather under some strange name like 'sun-awt-X11-XFramePeer'.
            for apps in replace_apps:
                if apps in exec_path:
                    exec_path = subprocess.Popen(
                        shlex.split("which {}".format(apps)),
                        stdout=subprocess.PIPE, universal_newlines=True) \
                        .communicate()[0] \
                        .replace("\u0000", "") \
                        .strip()

            if not blacklisted:

                # Get _NET_WM_STATE properties of the window, using xprop.
                xprop = subprocess.Popen(
                    shlex.split("xprop -id {}".format(_wid)),
                    stdout=subprocess.PIPE, universal_newlines=True) \
                    .communicate()[0] \
                    .replace("\u0000", "")

                # Populate list of states and convert them to something wmctrl
                # understands.
                net_wm_states = []
                for prop in xprop.split('\n'):
                    if prop.startswith("_NET_WM_STATE(ATOM) = "):
                        r = re.search(
                            "_NET_WM_STATE\(ATOM\) = ([\w, ]*$)", prop)
                        if r:
                            net_wm_states = r.group(1).split(',')
                            net_wm_states = [
                                wm_states[
                                    x.strip()] for x in net_wm_states if x.strip() in wm_states]
                            if len(net_wm_states) == 0:
                                net_wm_states = "remove,maximized_vert,maximized_horz"
                            elif len(net_wm_states) == 1:
                                if "maximized_horz" in net_wm_states:
                                    net_wm_states = "remove,maximized_vert"
                                elif "maximized_vert" in net_wm_states:
                                    net_wm_states = "remove,maximized_horz"
                                elif "hidden" in net_wm_states:
                                    net_wm_states = "add,hidden"
                            else:
                                net_wm_states = "add," + \
                                    ','.join(net_wm_states)
                            # print("DEBUG:", net_wm_states)

                # Finally insert an entry into the dictionary containing
                # all window information for an application.
                if desktop in d:
                    d[desktop].append(
                        [pid, geo, net_wm_states, exec_path, window_name])
                else:
                    d[desktop] = [[pid, geo, net_wm_states, exec_path, window_name]]

    # Write dictionary out to our session file.
    with open(session_file_path, "w") as f:
        json.dump(d, f)
        print("Session saved.")


def restore_session():
    cmd = "wmctrl -lp"
    re_str = "^[^\\s]+[\\s]+[-0-9]+[\\s]+(\\d+)"

    open_windows = {}
    windows = _get_open_windows(cmd)
    for window in windows:
        m = re.search(re_str, window)
        if not m:
            continue
        pid = int(m.group(1))
        if pid >= 2:
            ep = _get_exec_path(pid)
            open_windows[ep] = open_windows.get(ep, 0) + 1

    d = {}
    with open(session_file_path, "r") as f:
        d = json.load(f)

    for desktop in d:
        for entry in d[desktop]:
            if (entry[3] in open_windows and
                    open_windows[entry[3]] > 0):
                # print("[DEBUG]", "skipping", entry[3], open_windows[entry[3]])
                open_windows[entry[3]] -= 1
                continue

            coords = ",".join(map(str, entry[1]))
            print("Launching {} ...".format(entry[3]))
            subprocess.Popen(shlex.split(entry[3]))
            time.sleep(1)

            print("Moving to 0,{}".format(coords))
            # Decode base64 string representing the window name.
            decoded_win = base64.urlsafe_b64decode(
                entry[4]).decode("utf-8", "ignore")
            subprocess.Popen(shlex.split(
                "wmctrl -r \"{0}\" -e 0,{1}".format(decoded_win, coords)))
            time.sleep(1)

            print("Moving to workspace {}".format(desktop))
            subprocess.Popen(
                shlex.split(
                    "wmctrl -r :ACTIVE: -t {}".format(desktop)))
            print()


def move_windows():
    cmd = "wmctrl -lG"
    re_str = (
        "^[x0-9a-f]+\s+(-?[0-9]+)\s+[0-9]+\s+[0-9]+"
        "\s+[0-9]+\s+[0-9]+\s+[^\s]+[\s]+(.+$)")

    # Get list of open windows.
    unmoved_windows = []
    windows = _get_open_windows(cmd)
    for window in windows:
        m = re.search(re_str, window)
        if m and m.group(1) != "-1":
            encoded = base64.urlsafe_b64encode(bytes(m.group(2), "utf-8")) \
                .decode('ascii')
            unmoved_windows.append(json.dumps(encoded))

    d = {}
    with open(session_file_path, "r") as f:
        d = json.load(f)

    for desktop in d:
        for window in d[desktop]:
            if window[4] in unmoved_windows:
                coords = ",".join(map(str, window[1]))
                decoded_win = base64.urlsafe_b64decode(
                    window[4]).decode("utf-8", "ignore")
                print(decoded_win)
                print("Moving to 0,{}".format(coords))
                subprocess.Popen(shlex.split(
                    "wmctrl -r \"{0}\" -e 0,{1}".format(decoded_win, coords)))
                time.sleep(1)
                print("Moving to workspace {}".format(desktop))
                subprocess.Popen(shlex.split(
                    "wmctrl -r \"{0}\" -t {1}".format(decoded_win, desktop)))
                print("Modifying properties to {}".format(window[2]))
                subprocess.Popen(shlex.split(
                    "wmctrl -r \"{0}\" -b {1}".format(decoded_win, window[2])))
                print()


if args.r:
    restore_session()
elif args.s:
    save_session()
elif args.m:
    move_windows()
else:
    parser.print_help()
    sys.exit(-1)
