# sessionctrl
A Python script to manage your X session - save, restore, &amp; move windows for Linux
based systems.

This script is useful when you want to preserve your desktop's session across reboots.
It will save every application's position (including which workspace it's in) that is
open, allowing you to not worry about where you left off, which windows you had open,
which workspace they were in, etc.

## Setup

The three dependencies are:

 - Python 3
 - [wmctrl](https://sites.google.com/site/tstyblo/wmctrl)
 - xprop

Both should be easily found in any major distribution's repository.

## Usage

Simply run:

```shell
$ ./sessionctrl.py -s  # Saves your current session.
$ ./sessionctrl.py -r  # Restores your saved session.
$ ./sessionctrl.py -m  # Moves currently opened windows. Does not open new windows.
```

### Additional information

This script complies with the [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html)
for the following:

 - `$XDG_CONFIG_HOME`
 - `$XDG_DATA_HOME`

The session is saved in the default `$XDG_DATA_HOME`, and if not defined or
set, then:

```
$HOME/.local/share/sessionctrl
```

The config file is stored in the default `$XDG_CONFIG_HOME`, and if not defined
or set, then:

```
$HOME/.config/sessionctrl
```

Entries into the config file are separated by a space. The two options are:

 - `blacklist`    - do not save any applications under this list
 - `replace_apps` - substitute application cmdline for another

Note: keep in mind both options are activated on partial matches, not necessarily
a full match.

An example configuration:

```
blacklist = xfce4 xfce4-terminal thunar
replace_apps = android-studio
```

As you'll notice in the `blacklist`, anything that matches 'xfce4' will be
ignored. The next two are included for the sake of terseness.

The reason for `replace_apps` is some applications such as 'Android Studio' do
not show up simple as as 'Android Studio', but rather under some strange name
like 'sun-awt-X11-XFramePeer'. However, its executable name (what you type to
launch it from the terminal) still has 'android-studio' somewhere in the name.
Therefore, we want to replace the extremely long name with 'android-studio'
because that's what will actually launch it from the terminal.

In other words, what the script will do with `replace_apps` is if any
application's `cmdline` (found under `/proc/$PID/cmdline`) partially matches
what's inside `replace_apps`, then *that* (in this case 'android-studio')
command string will be used instead when restoring session.


## License

This program is free software, distributed under the terms of the [GNU] General
Public License as published by the Free Software Foundation, version 3 of the
License (or any later version).  For more information, see the file LICENSE.
