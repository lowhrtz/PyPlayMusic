# PyPlayMusic
Python/Tk-based player for music in a Google Play Music account.

Dependencies
------------------------------------------------------------
Tkinter, gmusicapi, pycrypto, urllib2, pillow, eyed3<br />
Python 2.7.9+ is also required.


Ubuntu:<br />
`sudo apt install python-pil.imagetk python-pip python-gi`<br />
`sudo pip install gmusicapi eyed3 pycrypto`

Note About Player Backends
--------------------------
The default backend uses GStreamer 1.0 and should be available on
most current Gnome/GTK systems. There is a backup backend that uses
VLC. VLC needs to be installed to use it. Also, python-vlc needs to
be installed.<br />
Using pip on Ubuntu:<br />
`sudo pip install python-vlc`<br />
On Windows(Assuming python is on the path):<br />
`python -m pip install python-vlc`