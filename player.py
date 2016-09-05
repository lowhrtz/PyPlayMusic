import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
Gst.init(None)

class Player(object):
    def __init__(self):
        self.url = None
        self.playbin = Gst.ElementFactory.make("playbin", "player")
        fakesink = Gst.ElementFactory.make("fakesink", "fakesink")
        self.playbin.set_property("video-sink", fakesink)

    def load_url(self, url):
        self.url = url
        self.playbin.set_property('uri', url)

    def play(self):
        self.playbin.set_state(Gst.State.PLAYING)

    def stop(self):
        self.playbin.set_state(Gst.State.NULL)

    def pause(self):
        self.playbin.set_state(Gst.State.PAUSED)

    def unpause(self):
        self.play()

    def get_duration(self):
        success = False
        i = 0
        while not success:
            success, dur = self.playbin.query_duration(Gst.Format.TIME)
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
        success, pos = self.playbin.query_position(Gst.Format.TIME)
        print(success, pos)
        return pos / 1000000

    def set_position(self, position):
        self.playbin.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, position * 1000000)
        #self.playbin.seek_simple(Gst.Format.TIME, Gst.SeekFlags.NONE, position * 1000000)
        while self.playbin.get_state(1000)[0] == Gst.StateChangeReturn.ASYNC:
            continue
        if self.playbin.get_state(1000)[0] == Gst.StateChangeReturn.FAILURE:
            print('Lost Stream. Fixing...')
            self.stop()
            while self.playbin.get_state(1000)[0] == Gst.StateChangeReturn.ASYNC:
                continue
            print('Stop State:')
            print(self.playbin.get_state(1000))
            #self.load_url(self.url)
            #while self.playbin.get_state(1000)[0] == Gst.StateChangeReturn.ASYNC:
            #    continue
            #print('Load State:')
            #print(self.playbin.get_state(1000))
            print('Playing...')
            self.play()
            while self.playbin.get_state(1000)[0] == Gst.StateChangeReturn.ASYNC:
                print(self.playbin.get_state(1000))
                continue
            print('Play State:')
            print(self.playbin.get_state(1000))
            self.playbin.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, position * 1000000)
            while self.playbin.get_state(1000)[0] == Gst.StateChangeReturn.ASYNC:
                print(self.playbin.get_state(1000)[2])
                continue
            print('Seek State:')
            print(self.playbin.get_state(1000))
