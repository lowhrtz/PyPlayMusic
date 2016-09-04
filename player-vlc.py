import vlc

class Player(object):
    def __init__(self):
        self.media_player = vlc.MediaPlayer()

    def load_url(self, url):
        self.media_player.set_mrl(url)

    def play(self):
        self.media_player.play()

    def stop(self):
        self.media_player.stop()

    def pause(self):
        self.media_player.pause()

    def unpause(self):
        self.media_player.pause()

    def get_duration(self):
        return self.media_player.get_length()

    def get_position(self):
        return self.media_player.get_time()

    def set_position(self, position):
        self.media_player.set_time(int(position))
