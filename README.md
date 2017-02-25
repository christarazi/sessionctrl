# sessionctrl
A Python script to manage your X session - save, restore, &amp; move windows.

## Setup

The two dependencies are:

 - [wmctrl](https://sites.google.com/site/tstyblo/wmctrl)
 - xprop

Both should be easily found in any major distribution's repository.

## Usage

Simply run:

```shell
$ ./sessionctrl.py -s       # Saves your current session.
$ ./sessionctrl.py -r       # Restores your saved session.
$ ./sessionctrl.py -m       # Moves currently opened windows. Does not open new windows.
```

### Additional information

The session is saved in `$HOME/.sessionctrl.info`.

There is a config file `$HOME/.sessionctrl.conf` which is created on the first
run. The two options are:

 - `blacklist`    - do not save any applications under this list
 - `replace_apps` - substitute applications for another

Note: keep in mind both options are activated on partial matches, not necessarily
a full match.

An example configuration:

```
blacklist=xfce4 xfce4-terminal thunar
replace_apps=android-studio
```

As you'll notice in the `blacklist`, anything that matches 'xfce4' will be
ignored. The other two are included for the sake of terseness.

The reason for `replace_apps` is some applications such as 'Android Studio' do
not show up as themselves, rather under some strange name like
'sun-awt-X11-XFramePeer', but still have 'android-studio' somewhere in the
name. What the script will do with `replace_apps` is if any application's
`cmdline` (found under `/proc/$PID/cmdline`) partially matches what's inside
`replace_apps`, then *that* (in this case 'android-studio') command string will
be used instead when restoring session.
