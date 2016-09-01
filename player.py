import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
Gst.init(None)

class Player(object):
    def __init__(self):
        self.element = Gst.ElementFactory.make("playbin", "player")

    def load_url(self, url):
        self.element.set_property('uri', url)

    def play(self):
        self.element.set_state(Gst.State.PLAYING)

    def stop(self):
        self.element.set_state(Gst.State.NULL)

    def pause(self):
        self.element.set_state(Gst.State.PAUSED)

    def unpause(self):
        self.play()

    def get_duration(self):
        success = False
        i = 0
        while not success:
            success, dur = self.element.query_duration(Gst.Format.TIME)
            i += 1
            if i > 1000: return 0
        return dur / 1000000

    def get_position(self):
        success = False
        i = 0
        #while not success:
        #    success, pos = self.element.query_position(Gst.Format.TIME)
        #    i += 1
        #    print(i, success, pos)
        #    if i > 1000: return 0
        success, pos = self.element.query_position(Gst.Format.TIME)
        print(success, pos)
        return pos / 1000000

    def set_position(self, position):
        self.element.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, position * 1000000)
