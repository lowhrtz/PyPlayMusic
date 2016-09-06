import vlc


class Player(object):
    def __init__(self):
        self.media_player = vlc.MediaPlayer()

    def load_url(self, url):
        self.media_player.set_mrl(url)

    def play(self):
        if self.media_player.play() == -1:
            return False
        return True

    def is_playing(self):
        state = self.media_player.get_state()
        #print state
        if state == vlc.State.Playing\
                or state == vlc.State.Opening\
                or state == vlc.State.Paused:
            return True
        return False

    def stop(self):
        self.media_player.stop()
        return True

    def pause(self):
        self.media_player.pause()
        return True

    def unpause(self):
        return self.pause()

    def get_duration(self):
        return self.media_player.get_length()

    def get_position(self):
        return self.media_player.get_time()

    def set_position(self, position):
        self.media_player.set_time(int(position))
        state = self.media_player.get_state()
        #print state
        if state == vlc.State.Ended\
                or state == vlc.State.Stopped\
                or state == vlc.State.Error:
            return False
        return True
