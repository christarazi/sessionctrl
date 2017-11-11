#!/usr/sbin/env python3


# Copyright (C) 2017 Chris Tarazi
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

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
import shlex
import json
import time
import argparse
import base64
import configparser
from pprint import pprint
from subprocess import Popen, PIPE, TimeoutExpired

parser = argparse.ArgumentParser()
parser.add_argument('-d',
                    '--dry-run',
                    action="store_true",
                    help="don't actually save/restore/move")
group = parser.add_mutually_exclusive_group()
group.add_argument('-r', action="store_true", help="restores session")
group.add_argument('-s', action="store_true", help="saves session")
group.add_argument('-m',
                   action="store_true",
                   help="only moves already open windows")

args = parser.parse_args()

global blacklist
global replace_apps

config = configparser.ConfigParser()
blacklist = []
replace_apps = []

conf_file_path = "{}/.sessionctrl.conf".format(os.path.expanduser("~"))
session_file_path = "{}/.sessionctrl.info".format(os.path.expanduser("~"))

# Create config file if it does not exist.
# Otherwise parse the config file for the blacklist and replace_apps.
if not os.path.isfile(conf_file_path):
    config.add_section("Options")
    config.set("Options", "blacklist", "")
    config.set("Options", "replace_apps", "")
    with open(conf_file_path, 'w') as f:
        config.write(f)
else:
    with open(conf_file_path, 'r') as f:
        config.read_file(f)
    blacklist = config.get("Options", "blacklist").split()
    replace_apps = config.get("Options", "replace_apps").split()

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
with Popen(shlex.split("which wmctrl"), stdout=PIPE) as proc:
    try:
        proc.wait(timeout=5)
    except TimeoutExpired:
        print("Timeout expired checking for wmctrl")
        sys.exit(-1)

    if proc.returncode != 0:
        print(proc.returncode, "Please install wmctrl as it is a dependency.")
        sys.exit(-1)

with Popen(shlex.split("which xprop"), stdout=PIPE) as proc:
    try:
        proc.wait(timeout=5)
    except TimeoutExpired:
        print("Timeout expired checking for xprop")
        sys.exit(-1)

    if proc.returncode != 0:
        print("Please install xprop as it is a dependency.")
        sys.exit(-1)

# sys.exit(0)


def _get_open_windows(cmd):
    p = Popen(
        shlex.split(cmd),
        stdout=PIPE,
        universal_newlines=True)

    return p.communicate()[0].replace("\u0000", "").split('\n')


def _get_exec_path(pid):
    return Popen(
        shlex.split("strings /proc/{}/cmdline".format(pid)),
        stdout=PIPE, universal_newlines=True) \
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
        if not m:
            continue

        _wid = m.group(1)
        desktop = m.group(2)
        pid = int(m.group(3))
        geo = (int(m.group(4)), int(m.group(5)),
               int(m.group(6)), int(m.group(7)))

        # If pid is 0 then the application does not support windows.
        # And skip over desktop-specific windows.
        if pid == 0 or desktop == "-1":
            continue

        # Get command of the application and check if it is blacklisted before
        # continuing.
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
                exec_path = Popen(
                    shlex.split("which {}".format(apps)),
                    stdout=PIPE, universal_newlines=True) \
                    .communicate()[0] \
                    .replace("\u0000", "") \
                    .strip()

        if blacklisted:
            continue

        # Get _NET_WM_STATE properties of the window, using xprop.
        xprop = Popen(
            shlex.split("xprop -id {}".format(_wid)),
            stdout=PIPE, universal_newlines=True) \
            .communicate()[0] \
            .replace("\u0000", "")

        # Populate list of states and convert them to something wmctrl
        # understands.
        net_wm_states = []
        for prop in xprop.split('\n'):
            if prop.startswith("_NET_WM_STATE(ATOM) = "):
                r = re.search(r"_NET_WM_STATE(ATOM) = ([\w, ]*$)", prop)
                if r:
                    net_wm_states = r.group(1).split(',')
                    net_wm_states = [
                        wm_states[
                            x.strip()] for x in net_wm_states if x.strip() in wm_states]
                    if not net_wm_states:
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
    if not args.dry_run:
        with open(session_file_path, "w") as f:
            json.dump(d, f)
        print("Session saved.")
    else:
        print("Dry run save.")


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

    if args.dry_run:
        print("Dry run restore.")

    for desktop in d:
        for entry in d[desktop]:
            if (entry[3] in open_windows and
                    open_windows[entry[3]] > 0):
                # print("[DEBUG]", "skipping", entry[3], open_windows[entry[3]])
                open_windows[entry[3]] -= 1
                continue

            coords = ",".join(map(str, entry[1]))
            winname = base64.urlsafe_b64decode(
                entry[4]).decode("utf-8", "ignore")

            print("Launching {} ...".format(entry[3]))
            if not args.dry_run:
                Popen(shlex.split(entry[3]))
            time.sleep(1)

            print("Moving to 0,{}".format(coords))
            if not args.dry_run:
                Popen(shlex.split(
                    "wmctrl -r \"{0}\" -e 0,{1}".format(winname, coords)))
            time.sleep(1)

            print("Moving to workspace {}".format(desktop))
            if not args.dry_run:
                Popen(shlex.split("wmctrl -r :ACTIVE: -t {}".format(desktop)))
            print()


def move_windows():
    cmd = "wmctrl -lG"
    re_str = (
        r"^[x0-9a-f]+\s+(-?[0-9]+)\s+[0-9]+\s+[0-9]+"
        r"\s+[0-9]+\s+[0-9]+\s+[^\s]+[\s]+(.+$)"
    )

    # Get list of open windows.
    unmoved_windows = []
    windows = _get_open_windows(cmd)
    for window in windows:
        m = re.search(re_str, window)
        if m and m.group(1) != "-1":
            encoded = base64.urlsafe_b64encode(
                bytes(m.group(2), "utf-8")).decode('ascii')
            unmoved_windows.append(json.dumps(encoded))

    d = {}
    with open(session_file_path, "r") as f:
        d = json.load(f)

    if args.dry_run:
        print("Dry run move.")

    for desktop in d:
        for window in d[desktop]:
            if window[4] not in unmoved_windows:
                continue
            coords = ",".join(map(str, window[1]))
            winname = base64.urlsafe_b64decode(
                window[4]).decode("utf-8", "ignore")

            # Remove vert & horz attribute to allow window to be moved
            if not args.dry_run:
                Popen(shlex.split(
                    "wmctrl -r \"{0}\" -b remove,maximized_vert,maximized_horz"
                    .format(winname)))

            print(winname)
            print("Moving to 0,{}".format(coords))
            if not args.dry_run:
                Popen(shlex.split(
                    "wmctrl -r \"{0}\" -e 0,{1}".format(winname, coords)))
            time.sleep(1)

            print("Moving to workspace {}".format(desktop))
            if not args.dry_run:
                Popen(shlex.split(
                    "wmctrl -r \"{0}\" -t {1}".format(winname, desktop)))

            print("Modifying properties to {}\n".format(window[2]))
            if not args.dry_run:
                Popen(shlex.split(
                    "wmctrl -r \"{0}\" -b {1}".format(winname, window[2])))


if args.r:
    restore_session()
elif args.s:
    save_session()
elif args.m:
    move_windows()
else:
    parser.print_help()
    sys.exit(-1)
