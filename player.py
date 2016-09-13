import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
Gst.init(None)

TIMEOUT = 1000

class Player(object):
    def __init__(self):
        self.url = None
        self.playbin = Gst.ElementFactory.make("playbin", "player")
        fakesink = Gst.ElementFactory.make("fakesink", "fakesink")
        self.playbin.set_property("video-sink", fakesink)

    def wait_for_state(self):
        while self.playbin.get_state(TIMEOUT)[0] == Gst.StateChangeReturn.ASYNC:
            continue
        if self.playbin.get_state(TIMEOUT)[0] == Gst.StateChangeReturn.FAILURE:
            return False
        return True

    def load_url(self, url):
        self.url = url
        self.playbin.set_property('uri', url)

    def play(self):
        self.playbin.set_state(Gst.State.PLAYING)
        return self.wait_for_state()

    def is_playing(self):
        if not self.wait_for_state():
            return False
        state = self.playbin.get_state(TIMEOUT)[1]
        #print state
        if state == Gst.State.PLAYING\
                or state == Gst.State.PAUSED\
                or state == Gst.State.READY:
            return True
        return False

    def stop(self):
        self.playbin.set_state(Gst.State.NULL)
        return self.wait_for_state()

    def pause(self):
        self.playbin.set_state(Gst.State.PAUSED)
        return self.wait_for_state()

    def unpause(self):
        return self.play()

    def get_duration(self):
        success = False
        i = 0
        while not success:
            success, dur = self.playbin.query_duration(Gst.Format.TIME)
            i += 1
            if i > 1000:
                return 0
        return dur / 1000000

    def get_position(self):
        success = False
        i = 0
        while not success:
            success, pos = self.element.query_position(Gst.Format.TIME)
            i += 1
            if i > 1000:
                return 0
        return pos / 1000000

    def set_position(self, position):
        self.playbin.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, position * 1000000)
        return self.wait_for_state()
