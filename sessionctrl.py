'''
This tool allows you to save your desktop session.

This tool has 2 dependencies:
    1) wmctrl <https://sites.google.com/site/tstyblo/wmctrl>
    2) xprop  <https://www.x.org/archive/X11R6.7.0/doc/xprop.1.html>
in order to interact with the X Windows.

Note: 
The developement of wmctrl seems to have halted. There are several versions 
floating around on the web, but none are from the original author.

With that in mind, minimizing a window is not supported by the official version,
but is supported in another version. This tool will utilize the official
version for the sake of simplicity. As a result, 'minimized' windows will not
actually be minimized when restoring a session.

See here: <https://bugs.launchpad.net/ubuntu/+source/wmctrl/+bug/260875>
'''

import os, re, sys, subprocess, shlex, json, time, argparse
from pprint import pprint

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument('-r', action="store_true", help="restores session")
group.add_argument('-s', action="store_true", help="saves session")
group.add_argument('-m', action="store_true", help="only moves already open windows")

args = parser.parse_args()

blacklist = ["Thunar", "xfce4-terminal", "android"]
replace_apps = ["android-studio"]

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

def save_session():
    cmd = "wmctrl -lpG"
    p = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE, universal_newlines=True)
    output = p.communicate()[0].replace("\u0000", "")
    
    d = {}
    for line in output.split('\n'):
        blacklisted = False

        m = re.search("^([^\s]+)[\s]+([^\s]+)[\s]+([^\s]+)[\s]+([^\s]+)[\s]+([^\s]+)[\s]+([^\s]+)[\s]+([^\s]+)[\s]+[^\s]+[\s]+([\x20-\x7E]+)", line)
        if m:
            _wid = m.group(1)
            desktop = m.group(2)
            pid = int(m.group(3))
            geo = (int(m.group(4)), int(m.group(5)), int(m.group(6)), int(m.group(7)))

            # Get command of the application.
            application = subprocess.Popen(shlex.split("cat /proc/" + str(pid) + "/cmdline"), stdout=subprocess.PIPE, universal_newlines=True).communicate()[0].replace("\u0000", "")

            # json.dumps automatically escapes quotation marks in string.
            # Need to make window_name has escaped quotation marks.
            window_name = json.dumps(m.group(8))

            # Skip over desktop-specific windows.
            if desktop == "-1":
                continue

            for item in blacklist:
                if item in application:
                    blacklisted = True
                    break

            # Substitute applications from predetermined list.
            # Some applications such as 'Android Studio' do not show up as themselves,
            # rather under some strange name like 'sun-awt-X11-XFramePeer'.
            for apps in replace_apps:
                if apps in application:
                    application = subprocess.Popen(shlex.split("which " + apps), stdout=subprocess.PIPE, universal_newlines=True).communicate()[0].replace("\u0000", "").strip()
        
            if not blacklisted:

                # Get _NET_WM_STATE properties of the window, using xprop.
                xprop = subprocess.Popen(shlex.split("xprop -id " + _wid), stdout=subprocess.PIPE, universal_newlines=True).communicate()[0].replace("\u0000", "")
                
                # Populate list of states and convert them to something wmctrl understands.
                net_wm_states = []
                for prop in xprop.split('\n'):
                    if prop.startswith("_NET_WM_STATE(ATOM) = "):
                        r = re.search("_NET_WM_STATE\(ATOM\) = ([\w, ]*$)", prop)
                        if r:
                            net_wm_states = r.group(1).split(',')
                            net_wm_states = [wm_states[x.strip()] for x in net_wm_states if x.strip() in wm_states ]
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
                                net_wm_states = "add," + ','.join(net_wm_states)
                            print("DEBUG:", net_wm_states)

                # Finally insert an entry into the dictionary containing 
                # all window information for an application.
                if desktop in d:
                    d[desktop].append([pid, geo, net_wm_states, application, window_name])
                else:
                    d[desktop] = [[pid, geo, net_wm_states, application, window_name]]

    # Write dictionary out to our config file.
    with open(".sessionctrl.info", "w") as f:
        json.dump(d, f)
        print()

def restore_session():
    d = {}
    with open(".sessionctrl.info", "r") as f:
        d = json.load(f)

    for desktop in d:
        for entry in d[desktop]:
            coords = ",".join(map(str, entry[1]))
            print("Launching", entry[3], "...")
            subprocess.Popen(shlex.split(entry[3]))
            time.sleep(1)
            print("Moving", entry[3], "to 0," + coords)
            subprocess.Popen(shlex.split("wmctrl -r '" + entry[4] + "' -e 0," + coords))
            time.sleep(1)
            print("Moving to workspace", desktop)
            subprocess.Popen(shlex.split("wmctrl -r :ACTIVE: -t " + desktop))
            print()

def move_windows():
    cmd = "wmctrl -lG"
    p = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE, universal_newlines=True)
    output = p.communicate()[0].replace("\u0000", "")

    # Get list of open windows.
    unmoved_windows = []
    for line in output.split('\n'):
        m = re.search("^[^\s]+[\s]+([^\s]+)[\s]+([^\s]+)[\s]+([^\s]+)[\s]+([^\s]+)[\s]+([^\s]+)[\s]+[^\s]+[\s]+([\x20-\x7E]+)", line)
        if m and m.group(1) != "-1":
            unmoved_windows.append(json.dumps(m.group(6)))

    d = {}
    with open(".sessionctrl.info", "r") as f:
        d = json.load(f)

    for desktop in d:
        for entry in d[desktop]:
            for unmoved in unmoved_windows:
                if entry[4] == unmoved:
                    coords = ",".join(map(str, entry[1]))
                    print("Moving", entry[4], "to 0," + coords)
                    print("DEBUG:", unmoved)
                    subprocess.Popen(shlex.split("wmctrl -r " + unmoved + " -e 0," + coords))
                    time.sleep(1)
                    print("Moving to workspace", desktop)
                    subprocess.Popen(shlex.split("wmctrl -r " + unmoved + " -t " + desktop))
                    print("Modifiying properties of", unmoved, " with", entry[2])
                    subprocess.Popen(shlex.split("wmctrl -r " + unmoved + " -b " + entry[2]))
                    print()


if args.r:
    restore_session()
elif args.s:
    save_session()
elif args.m:
    move_windows()
else:
    print("You've managed to trick ArgumentParser, congrats...")
    sys.exit(-1)

