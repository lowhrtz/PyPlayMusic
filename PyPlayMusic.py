#!/usr/bin/python
import io
from PIL import Image, ImageTk
import os
import random
import re
import tkFont
import Tkinter
import ttk
from urllib2 import urlopen
#import numpy

from gmusicapi import Mobileclient, Webclient
import swmixer

import auth

# Module constants
TMP_MP3 = "tmp.mp3"
DEFAULT_IMAGE = "notes.png"
SAMPLE_RATE = 44100


def convert_milli_to_std(millisecs):
    """
    Converts milliseconds to string in standard time. EG 1:30
    :param millisecs: number of milliseconds
    :return: Standard time as string
    """
    millisecs = int(millisecs)
    secs = millisecs / 1000
    mins = secs / 60
    secs_rem = secs % 60
    if secs_rem >= 0 and secs_rem < 10:
        secs = "0" + str(secs_rem)
    else:
        secs = str(secs_rem)
    return str(mins) + ":" + secs


def convert_sample_to_milli(sample, rate):
    """
    Converts samples to milliseconds.
    :param sample: number of samples
    :param rate: sample rate
    :return: the number of milliseconds equal to sample samples
    """
    #print "Convert Returns:", sample / float(size) * 500
    return sample / rate * 500  # I would think this should be 1000 but that gives values twice as big as they should be. Strange...


def convert_milli_to_sample(milli, rate):
    """
    Converts milliseconds to samples.
    :param milli: the number of milliseconds
    :param rate: sample rate
    :return: the number of samples equal to milli milliseconds
    """
    return milli / float(500) * rate


class TrackList(list):
    """
    TrackList is a list of tracks that keeps track of the current position.
    """
    def __init__(self, copy_list=None):
        """
        TrackList __init__ function
        :param copy_list: list to be copied. If None then new list is initialized
        :return: None
        """
        if copy_list is None:
            super(TrackList, self).__init__()
            self.pos = 0
        else:
            super(TrackList, self).__init__(copy_list)
            self.pos = 0

    def next(self):
        """
        Moves pointer to next track and returns track at that position.
        :return: track at new position
        """
        if self.pos == len(self) - 1:
            self.pos = 0
        else:
            self.pos += 1
        return self[self.pos]

    def prev(self):
        """
        Moves pointer to previous track and returns track at that position.
        :return: track at new position
        """
        if self.pos == 0:
            self.pos = len(self) - 1
        else:
            self.pos -= 1
        return self[self.pos]

    def at(self, index):
        """
        Moves pointer to specified index and returns track at that position.
        :param index: index of desired track
        :return: track at new position
        """
        try:
            self[index]
        except IndexError:
            return None
        self.pos = index
        return self[self.pos]

    def current(self):
        return self[self.pos]


class MainWindow(Tkinter.Tk):
    """
    Main GUI window for the application.
    """
    def __init__(self, parent, web_client, mobile_client):
        """
        MainWindow __init__ function
        :param parent: Tk parent. Fine to be None.
        :param web_client: gmusicapi Webclient is expected
        :param mobile_client: gmusicapi Mobileclient is expected
        :return: None
        """
        Tkinter.Tk.__init__(self, parent)
        self.parent = parent
        self.web_client = web_client
        self.mobile_client = mobile_client
        self.channel = None
        self.library = None
        self.initialize()

    def initialize(self):
        """
        Initializes the gui widgets. Should only be called from the __init__function.
        :return: None
        """
        self.protocol('WM_DELETE_WINDOW', self.close_window)
        self.grid()

        # Set up widgets
        search_frame = Tkinter.Frame(self)
        self.search_choose = ttk.Combobox(self, state='readonly')
        self.search_choose['values'] = (
            "Search by Artist", "Search by Genre", "Search by Album", "Search by Title", "Playlists"
        )
        self.search_choose.current(0)
        self.search_choose.bind("<<ComboboxSelected>>", self.on_search_choose_click)
        #print self.search_choose['values']
        self.entry_variable = Tkinter.StringVar()
        self.entry = Tkinter.Entry(self, textvariable=self.entry_variable)
        self.entry.bind("<Return>", self.on_press_enter)
        self.search_button = Tkinter.Button(self, text=u"Search", command=self.on_search_click)
        listbox_frame = Tkinter.Frame(self)
        listbox_scrollbar = Tkinter.Scrollbar(self)
        self.track_listbox = Tkinter.Listbox(self, yscrollcommand=listbox_scrollbar.set,
                                             font=tkFont.Font(family='Helvetica', size=12, weight='bold'),
                                             height=15, width=40)
        #self.track_listbox.config(yscrollcommand=listbox_scrollbar.set)
        self.track_listbox.bind("<Double-Button-1>", self.select_track)
        self.track_listbox.bind("<Return>", self.select_track)
        listbox_scrollbar.config(command=self.track_listbox.yview)
        self.playlists = ttk.Combobox(self, state='disabled')
        self.playlists['values'] = self.get_playlists()
        self.playlists.current(0)
        self.playlists.bind("<<ComboboxSelected>>", self.on_playlists_click)
        self.rand_list_var = Tkinter.IntVar()
        randomize_list = Tkinter.Checkbutton(self, text="Shuffle Results", variable=self.rand_list_var)
        self.default_image = ImageTk.PhotoImage(Image.open(DEFAULT_IMAGE))
        self.album_image = Tkinter.Label(self, image=self.default_image)
        self.album_image['image'] = self.default_image
        self.fileinfo = Tkinter.Label(self, anchor="w", justify=Tkinter.LEFT)
        self.controls_frame = Tkinter.Frame(self)
        self.pause_button = Tkinter.Button(self, text="Pause", state="disabled", command=self.pause_track)
        self.current_time = Tkinter.Label(self, anchor="w")
        self.progress = ttk.Progressbar(self, orient="horizontal",
                                        length=200, mode="determinate")
        self.progress.bind("<Button-1>", self.on_track_seek)
        self.total_time = Tkinter.Label(self)
        self.next_button = Tkinter.Button(self, text="Next Track", state="disabled", command=self.on_next_track)

        # place widgets on grid
        search_frame.grid(column=0, columnspan=2, row=0, sticky='N')
        self.search_choose.grid(in_=search_frame, column=0, row=0, sticky='EW')
        self.entry.grid(in_=search_frame, column=1, row=0, sticky='EW')
        self.search_button.grid(in_=search_frame, column=2, row=0)
        self.playlists.grid(in_=search_frame, column=0, row=1, sticky='N')
        randomize_list.grid(in_=search_frame, column=1, row=1)
        listbox_frame.grid(column=2, row=0, rowspan=2, sticky='NS')
        self.track_listbox.grid(in_=listbox_frame, column=0, row=0, sticky='NS')
        listbox_scrollbar.grid(in_=listbox_frame, column=1, row=0, sticky='NS')
        self.album_image.grid(column=0, row=1)
        self.fileinfo.grid(column=1, columnspan=1, row=1)
        self.controls_frame.grid(column=0, columnspan=3, row=2)
        self.pause_button.grid(in_=self.controls_frame, column=0, row=0)
        self.current_time.grid(in_=self.controls_frame, column=1, row=0)
        self.progress.grid(in_=self.controls_frame, column=2, row=0)
        self.total_time.grid(in_=self.controls_frame, column=3, row=0)
        self.next_button.grid(in_=self.controls_frame, column=4, row=0)

        # Final initializations
        self.player_state = "next"
        self.pause_state = "unpaused"

        self.entry.focus_set()
        swmixer.init(samplerate=SAMPLE_RATE, chunksize=1024, stereo=True)
        swmixer.start()

        self.library = self.mobile_client.get_all_songs()

    def center(self):
        """
        Centers the window.
        :return: None
        """
        self.update_idletasks()
        w = self.winfo_screenwidth()
        h = self.winfo_screenheight()
        size = tuple(int(_) for _ in self.geometry().split('+')[0].split('x'))
        x = w/2 - size[0]/2
        y = h/2 - size[1]/2
        #self.geometry("%dx%d+%d+%d" % (size + (x, y)))
        self.geometry("+%d+%d" % (x, y))

    def cleanup(self):
        """
        Cleans up the temp file
        :return: None
        """
        if os.path.isfile(TMP_MP3):
            os.remove(TMP_MP3)

    def close_window(self):
        """
        Close window override.
        :return: None
        """
        self.cleanup()
        self.player_final_close()
        self.destroy()

    def player_final_close(self):
        """
        Stops the player. Meant to be called from the overrided close function.
        :return: None
        """
        self.player_state = "stopped"
        try:
            self.channel.stop()
        except:
            pass

    def on_search_choose_click(self, event):
        """
        Callback function called when the "Search by" dropdown is selected.
        :param event: Tk event
        :return: None
        """
        current_search_index = self.search_choose.current()
        current_search = self.search_choose['values'][current_search_index]
        #print current_search
        if current_search == "Playlists":
            self.playlists['state'] = "readonly"
            self.entry['state'] = "disabled"
            self.search_button['state'] = "disabled"
        else:
            self.playlists['state'] = "disabled"
            self.entry['state'] = "normal"
            self.search_button['state'] = "normal"

    def on_playlists_click(self, event):
        """
        Callback function called when playlist dropdown is selected.
        :param event: Tk event
        :return: None
        """
        self.channel.done = True
        try:
            self.channel.stop()
        except AttributeError:
            pass
        playlist_index = self.playlists.current()
        playlist_dict = self.playlists.data[playlist_index]
        playlist_id = playlist_dict['id']
        #print playlist_id
        #print playlist_dict['tracks'][0]
        playlist_tracks = self.get_playlist_tracks(playlist_dict['tracks'])
        if self.rand_list_var.get():
            random.shuffle(playlist_tracks)
        self.play(playlist_tracks)

    def get_playlists(self):
        """
        Gets all playlists on the Google Play account
        :return: a list of playlist dictionaries
        """
        self.playlists.data = []
        name_list = []
        for datum in self.mobile_client.get_all_user_playlist_contents():
            #print datum['name']
            if datum['name'] != '':
                self.playlists.data.append(datum)
                name_list.append(datum['name'])
        return name_list

    def on_press_enter(self, event):
        """
        Callback function called when enter is pressed.
        :param event: Tk event
        :return: None
        """
        self.on_search_click()

    def on_search_click(self):
        """
        Callback function called when "Search" button is clicked.
        :return: None
        """
        self.player_state = "new_search"
        self.enable_controls(False)
        try:
            self.channel.stop()
            self.channel.done = True
        except AttributeError:
            pass
        search_tracks = TrackList([track for track in self.library
                                   if self.track_matches(track)])
        if len(search_tracks) == 0:
            global next_image
            next_image = ImageTk.PhotoImage(Image.open(DEFAULT_IMAGE))
            self.album_image.configure(image = next_image)
            self.fileinfo['text'] = "Nothing matched your search!"
            return

        if self.rand_list_var.get():
            random.shuffle(search_tracks)
        else:
            search_tracks.sort(key=lambda track: track['trackNumber'])
            search_tracks.sort(key=lambda track: track['album'])
            search_tracks.sort(key=lambda track: track['artist'])

        self.play(search_tracks)

    def track_matches(self, track):
        """
        Determines if the given track matches the search parameters.
        :param track: TrackList track
        :return: MatchObject or None but typically treated like True and False respectively.
        """
        current_search_index = self.search_choose.current()
        current_search = self.search_choose['values'][current_search_index]
        if current_search == "Search by Artist":
            search_field = track['artist']
        elif current_search == "Search by Genre":
            search_field = track['genre']
        elif current_search == "Search by Title":
            search_field = track['title']
        else:
            search_field = track['album']

        return re.search(self.entry_variable.get().replace(' ', '|'), search_field, flags=re.I)

    def pause_track(self):
        """
        Pauses the currently playing track.
        :return: None
        """
        if self.pause_state == "unpaused":
            self.channel.pause()
            self.pause_state = "paused"
        else:
            self.channel.unpause()
            self.pause_state = "unpaused"

    def on_next_track(self):
        """
        Set of instructions called when transitioning to the next track.
        :return: None
        """
        self.enable_controls(False)
        self.search_button['state'] = "disabled"
        #pygame.mixer.music.stop()
        self.channel.stop()
        self.channel.done = True

    def play(self, tracks):
        """
        Set of instructions in preparation  for playing the track.
        :param tracks: TrackList (used for tracking purposes)
        :return: None
        """
        self.fill_track_listbox(tracks)
        track = tracks.current()
        self.change_fileinfo(track)
        self.play_track(track, tracks)
        self.play_loop(tracks)

    def play_track(self, track, tracks):
        """
        Plays the given track.
        :param track: track to be played
        :param tracks: TrackList
        :return: None
        """
        self.change_fileinfo(track)
        self.progress['maximum'] = track['durationMillis']
        self.total_time['text'] = convert_milli_to_std(track['durationMillis'])
        self.update_listbox(tracks)
        self.update_idletasks()
        try:
            stream_audio = self.web_client.get_stream_audio(track['id'])
            #print "This is here"
        except:
            print "Error retrieving track: " + track['title']
            self.play_track(tracks.next(), tracks)
            return
        tmp_file = open(TMP_MP3, "wb")
        tmp_file.write(stream_audio)
        song = swmixer.Sound(TMP_MP3)
        #stream_audio = numpy.fromstring(stream_audio, dtype=numpy.int8)
        #song = swmixer.Sound(data=stream_audio)
        self.channel = song.play()
        self.player_state = "next"
        self.pause_state = "unpaused"
        self.enable_controls(True)
        current_search_index = self.search_choose.current()
        current_search = self.search_choose['values'][current_search_index]
        if current_search != "Playlists":
            self.search_button['state'] = "normal"

    def play_loop(self, tracks):
        """
        Virtual loop that is called every 100 milliseconds for updating the time and position gui widgets.
        :param tracks: TrackList
        :return: None
        """
        #print tracks.pos
        if self.track_listbox.data != tracks: return  # This removes any stale loops that result from new searches
        self.update_controls()
        if self.player_state != "stopped" and not self.channel.done:
            #print "We should see a bunch of these."
            self.after(100, self.play_loop, tracks)
        elif self.player_state == "next":
            #print "NEXT!"
            self.enable_controls(False)
            self.play_track(tracks.next(), tracks)
            self.after(100, self.play_loop, tracks)

    def update_controls(self):
        """
        Updates the time and position gui widgets.
        :return: None
        """
        pos = convert_sample_to_milli(self.channel.get_position(), SAMPLE_RATE)
        self.progress['value'] = pos
        self.current_time['text'] = convert_milli_to_std(pos)

    def change_fileinfo(self, metadata):
        """
        Changes the track info for the gui widget
        :param metadata: dictionary containing all metadata about the track
        :return: None
        """
        global next_image
        #print metadata
        if metadata.has_key('albumArtRef'):
            next_image = self.get_photo_image_from_url(metadata['albumArtRef'][0]['url'])
        elif metadata.has_key('artistArtRef'):
            next_image = self.get_photo_image_from_url(metadata['artistArtRef'][0]['url'])
        else:
            next_image = ImageTk.PhotoImage(Image.open(DEFAULT_IMAGE))
        self.album_image.configure(image = next_image)
        self.fileinfo['text'] = "Title: " + metadata['title'] + "\nArtist: " + metadata['artist'] + "\nAlbum: " + metadata['album'] + "\nGenre: " + metadata['genre']
        self.progress['value'] = 0
        self.current_time['text'] = "0:00"
        self.total_time['text'] = "0:00"

    def get_photo_image_from_url(self, url):
        """
        Gets an album or artist image from the given url.
        :param url: URL of the album/artist image
        :return: ImageTk PhotoImage representing the album/artist image
        """
        image_bytes = urlopen(url).read()
        data_stream = io.BytesIO(image_bytes)
        pil_image = Image.open(data_stream)
        return ImageTk.PhotoImage(pil_image)

    def enable_controls(self, enable):
        """
        Enables or disables the gui controls.
        :param enable: boolean, if true then enable if false the disable
        :return: None
        """
        if enable:
            self.next_button['state'] = "normal"
            self.pause_button['state'] = "normal"
        else:
            self.next_button['state'] = "disabled"
            self.pause_button['state'] = "disabled"

    def fill_track_listbox(self, tracks):
        """
        Fills the tracks listbox with track from tracks TrackList
        :param tracks: TrackList
        :return: None
        """
        self.track_listbox.delete(0, Tkinter.END)
        for track in tracks:
            self.track_listbox.insert(Tkinter.END, self.track_listbox_template(track))

        self.track_listbox.data = tracks

    def track_listbox_template(self, track):
        """
        Format template for items in the track listbox.
        :param track: track from TrackList
        :return: string in the format: "title" by "artist"
        """
        return track['title'] + " by " + track['artist']

    def select_track(self, event):
        """
        Callback function called when track is selected from the track listbox.
        :param event: Tk event
        :return: None
        """
        self.enable_controls(False)
        self.search_button['state'] = "disabled"
        self.player_state = "seek"
        self.channel.stop()
        curselection = self.track_listbox.curselection()[0]
        tracks = self.track_listbox.data
        self.play_track(tracks.at(int(curselection)), tracks)

    def update_listbox(self, tracks):
        """
        Updates the listbox to highlight the current track.
        :param tracks: TrackList
        :return: None
        """
        self.track_listbox.select_clear(0, Tkinter.END)
        self.track_listbox.select_set(tracks.pos)
        self.track_listbox.activate(tracks.pos)

    def on_track_seek(self, event):
        """
        Callback function called when the track position gui is clicked.
        :param event: Tk event
        :return: None
        """
        seek_ratio = event.x / float(self.progress.winfo_width())
        #print seek_ratio
        seek_milli = seek_ratio * self.progress['maximum']
        #print seek_milli
        self.channel.set_position(convert_milli_to_sample(seek_milli, SAMPLE_RATE))
        self.progress['value'] = int(seek_milli)
        self.current_time['text'] = convert_milli_to_std(int(seek_milli))

    def get_playlist_tracks(self, playlist_dict_tracks):
        """
        Gets TrackList form list of tracks in playlist dictionary.
        :param playlist_dict_tracks: list of tracks from playlist dictionary
        :return: TrackList of playlist tracks
        """
        id_list = [item['trackId'] for item in playlist_dict_tracks]
        playlist_tracks = [track for track in self.library if track['id'] in id_list]
        playlist_tracks.sort(key = lambda track: id_list.index(track['id']))
        #print playlist_tracks
        return TrackList(playlist_tracks)


if __name__ == "__main__":
    web_client = Webclient()
    mobile_client = Mobileclient()
    authenticated = False
    force_prompt = False
    while not authenticated:
        auth_handle = auth.AuthHandler("Google Auth", force_prompt)
        if auth_handle.canceled:
            exit(0)
        email = auth_handle.uname
        password = auth_handle.passwd
        if (web_client.login(email, password) and
                mobile_client.login(email, password, Mobileclient.FROM_MAC_ADDRESS)):
            authenticated = True
        else:
            force_prompt = True

    app = MainWindow(None, web_client, mobile_client)
    app.title('PyPlayMusic')
    app.center()
    app.mainloop()
