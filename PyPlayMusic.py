#!/usr/bin/python
import io
from PIL import Image, ImageTk
import random
import re
import sys
import tkFont
import Tkinter
import ttk
from urllib2 import urlopen

from gmusicapi import Mobileclient

import auth
import GMusicDownloader
import shared
args = sys.argv
if len(args) > 1:
    backend = args[1]
    try:
        backend_module = __import__('player_' + backend, fromlist=['Player'])
        Player = getattr(backend_module, 'Player')
    except ImportError, error:
        print(str(error))
        print('Backend, ' + backend + ', not found.')
        print('Look for a file named player_' + backend + '.py, if it is missing')
        print('either an invalid backend was entered or the file is missing.')
        sys.exit(1)
else:
    try:
        from player import Player
    except ImportError:
        from player_vlc import Player

# Module constants
DEFAULT_IMAGE = "PyPlayMusicIcon.png"
LOOP_INTERVAL = 100


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
    if 0 <= secs_rem < 10:
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
    # I would think this should be 1000 but that gives values twice as big as they should be. Strange...
    return sample / rate * 500


def convert_milli_to_sample(milli, rate):
    """
    Converts milliseconds to samples.
    :param milli: the number of milliseconds
    :param rate: sample rate
    :return: the number of samples equal to milli milliseconds
    """
    return milli / float(500) * rate


def track_listbox_template(track):
    """
    Format template for items in the track listbox.
    :param track: track from TrackList
    :return: string in the format: "title" by "artist"
    """
    return track['title'] + " by " + track['artist']


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
        :return: track at new position or None if index is out of range.
        """
        try:
            self[index]
        except IndexError:
            return None
        self.pos = index
        return self[self.pos]

    def current(self):
        return self[self.pos]


class MainWindow(shared.Centerable, Tkinter.Tk):
    """
    Main GUI window for the application.
    """
    def __init__(self):
        """
        MainWindow __init__ function
        :return: None
        """
        Tkinter.Tk.__init__(self)
        self.default_image = ImageTk.PhotoImage(file=DEFAULT_IMAGE, master=self)
        self.parent = None
        self.player = Player()
        self.listbox_tracks = None
        self.playlists = None
        self.stations = None
        self.device_id = None
        self.library = None

        # Initialize the GUI
        self.protocol('WM_DELETE_WINDOW', self.close_window)
        self.tk.call('wm', 'iconphoto', self._w, self.default_image)
        self.grid()

        # Set up widgets
        search_frame = Tkinter.Frame(self)
        self.search_choose = ttk.Combobox(search_frame, state='readonly')
        self.search_choose['values'] = (
            "Search by Artist", "Search by Genre", "Search by Album", "Search by Title", "Playlists", "Stations"
        )
        self.search_choose.current(0)
        self.search_choose.bind("<<ComboboxSelected>>", self.on_search_choose_click)
        self.entry_variable = Tkinter.StringVar(search_frame)
        self.entry = Tkinter.Entry(search_frame, textvariable=self.entry_variable)
        self.entry.bind("<Return>", self.on_press_enter)
        self.entry.bind("<KP_Enter>", self.on_press_enter)
        self.search_button = Tkinter.Button(search_frame, text=u"Search", command=self.on_search_click)
        listbox_frame = Tkinter.Frame(self)
        listbox_scrollbar = Tkinter.Scrollbar(listbox_frame)
        self.track_listbox = Tkinter.Listbox(listbox_frame, yscrollcommand=listbox_scrollbar.set,
                                             font=tkFont.Font(self, family='Helvetica', size=12, weight='bold'),
                                             height=15, width=40)
        self.track_listbox.bind("<Double-Button-1>", self.select_track)
        self.track_listbox.bind("<Return>", self.select_track)
        listbox_scrollbar.config(command=self.track_listbox.yview)
        self.second_combobox = ttk.Combobox(search_frame, state='disabled')
        self.rand_list_var = Tkinter.IntVar(search_frame)
        self.randomize_list = Tkinter.Checkbutton(search_frame, text="Shuffle Results", variable=self.rand_list_var)
        self.album_image = Tkinter.Label(self, image=self.default_image)
        self.album_image['image'] = self.default_image
        self.fileinfo = Tkinter.Label(self, anchor="w", justify=Tkinter.LEFT)
        self.controls_frame = Tkinter.Frame(self)
        self.pause_button = Tkinter.Button(self.controls_frame, text="Pause",
                                           state="disabled", command=self.pause_track)
        self.current_time = Tkinter.Label(self.controls_frame, anchor="w")
        self.progress = ttk.Progressbar(self.controls_frame, orient="horizontal",
                                        length=200, mode="determinate")
        self.progress.bind("<Button-1>", self.on_track_seek)
        self.total_time = Tkinter.Label(self.controls_frame)
        self.next_button = Tkinter.Button(self.controls_frame, text="Next Track",
                                          state="disabled", command=self.on_next_track)

        # place widgets on grid
        search_frame.grid(column=0, columnspan=2, row=0, sticky='N')
        self.search_choose.grid(column=0, row=0, sticky='EW')
        self.entry.grid(column=1, row=0, sticky='EW')
        self.search_button.grid(column=2, row=0)
        self.second_combobox.grid(column=0, row=1, sticky='N')
        self.randomize_list.grid(column=1, row=1)
        listbox_frame.grid(column=2, row=0, rowspan=2, sticky='NS')
        self.track_listbox.grid(column=0, row=0, sticky='NS')
        listbox_scrollbar.grid(column=1, row=0, sticky='NS')
        self.album_image.grid(column=0, row=1)
        self.fileinfo.grid(column=1, columnspan=1, row=1)
        self.controls_frame.grid(column=0, columnspan=3, row=2)
        self.pause_button.grid(column=0, row=0)
        self.current_time.grid(column=1, row=0)
        self.progress.grid(column=2, row=0)
        self.total_time.grid(column=3, row=0)
        self.next_button.grid(column=4, row=0)

        # Final initializations
        self.player_state = "play"
        self.pause_state = "unpaused"

        self.entry.focus_set()

        self.library = mobile_client.get_all_songs()

        def key(event):
            keysym = event.keysym_num
            # print keysym
            lower_n = 110
            upper_n = 78
            space = 32
            left_key = 65361
            up_key = 65362
            right_key = 65363
            down_key = 65364
            if keysym == lower_n or keysym == upper_n:
                self.on_next_track()
            elif keysym == space:
                self.pause_track()
            elif keysym == left_key:
                self.seek_reverse(5)
            elif keysym == up_key:
                self.seek_forward(30)
            elif keysym == right_key:
                self.seek_forward(5)
            elif keysym == down_key:
                self.seek_reverse(30)

        self.fileinfo.bind("<Key>", key)
        self.fileinfo.bind("<Control-d>", lambda x: self.on_track_download(self.listbox_tracks.current()))

        # Final Commands
        self.center()
        splash.master.destroy()
        shared.ChooseDevice(self, mobile_client)

    # def center(self):
    #     """
    #     Centers the window.
    #     :return: None
    #     """
    #     self.update_idletasks()
    #     w = self.winfo_screenwidth()
    #     h = self.winfo_screenheight()
    #     size = tuple(int(_) for _ in self.geometry().split('+')[0].split('x'))
    #     x = w/2 - size[0]/2
    #     y = h/2 - size[1]/2
    #     self.geometry("+%d+%d" % (x, y))

    def close_window(self):
        """
        Close window override.
        :return: None
        """
        self.player_final_close()
        self.destroy()

    def player_final_close(self):
        """
        Stops the player. Meant to be called from the overrided close function.
        :return: None
        """
        self.player_state = "stopped"
        self.player.stop()

    def on_search_choose_click(self, event):
        """
        Callback function called when the "Search by" dropdown is selected.
        :param event: Tk event
        :return: None
        """
        current_search_index = self.search_choose.current()
        current_search = self.search_choose['values'][current_search_index]
        if current_search == "Playlists":
            self.second_combobox['state'] = "readonly"
            self.entry['state'] = "disabled"
            self.search_button['state'] = "disabled"
            self.randomize_list['state'] = "normal"
            self.playlist_option_chosen()
        elif current_search == "Stations":
            self.second_combobox['state'] = "readonly"
            self.entry['state'] = "disabled"
            self.search_button['state'] = "disabled"
            self.randomize_list['state'] = "disabled"
            self.station_option_chosen()
        else:
            self.second_combobox['state'] = "disabled"
            self.entry['state'] = "normal"
            self.search_button['state'] = "normal"
            self.randomize_list['state'] = "normal"

    def on_playlists_click(self, event):
        """
            Callback function called when playlist dropdown is selected.
            :param event: Tk event
            :return: None
            """
        self.player.stop()
        playlist_index = self.second_combobox.current()
        playlist_dict = self.playlists[playlist_index]
        playlist_tracks = self.get_playlist_tracks(playlist_dict['tracks'])
        if self.rand_list_var.get():
            random.shuffle(playlist_tracks)
        self.play(playlist_tracks)

    def playlist_option_chosen(self):
        self.second_combobox['values'] = self.get_playlists()
        self.second_combobox.current(0)
        self.second_combobox.bind("<<ComboboxSelected>>", self.on_playlists_click)

    def station_option_chosen(self):
        self.stations = mobile_client.get_all_stations()
        self.stations.reverse()
        stations_list = []
        for station in self.stations:
            stations_list.append(station['name'])
        self.second_combobox['values'] = stations_list
        self.second_combobox.current(0)
        self.second_combobox.bind("<<ComboboxSelected>>", self.on_stations_choose_click)

    def on_stations_choose_click(self, event):
        self.player.stop()
        choice_index = self.second_combobox.current()
        station_dict = self.stations[choice_index]
        station_id = station_dict['id']
        station_tracks = mobile_client.get_station_tracks(station_id, num_tracks=200)
        self.play(TrackList(station_tracks))

    def get_playlists(self):
        """
        Gets all playlists on the Google Play account
        :return: a list of playlist dictionaries
        """
        self.playlists = []
        name_list = []
        for datum in mobile_client.get_all_user_playlist_contents():
            if datum['name'] != '':
                self.playlists.append(datum)
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
        self.player.stop()
        search_tracks = TrackList([track for track in self.library
                                   if self.track_matches(track)])
        if len(search_tracks) == 0:
            global next_image
            self.progress['value'] = 0
            self.current_time['text'] = "0:00"
            self.total_time['text'] = "0:00"
            self.fill_track_listbox(search_tracks)
            next_image = self.default_image
            self.album_image.configure(image=next_image)
            self.fileinfo['text'] = "Nothing matched your search!"
            return

        if self.rand_list_var.get():
            random.shuffle(search_tracks)
        else:
            search_tracks.sort(key=lambda trk: trk['title'])
            search_tracks.sort(key=lambda trk: trk['trackNumber'])
            search_tracks.sort(key=lambda trk: trk['discNumber'])
            search_tracks.sort(key=lambda trk: trk['album'])
            search_tracks.sort(key=lambda trk: trk['artist'])

        self.play(search_tracks)

    def remove_all_focus(self):
        """
        Removes focus from interactable widgets.
        """
        self.fileinfo.focus()

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
        self.fileinfo.focus()
        if self.pause_state == "unpaused":
            self.player.pause()
            self.pause_state = "paused"
        else:
            self.player.unpause()
            self.pause_state = "unpaused"

    def on_next_track(self):
        """
        Set of instructions called when transitioning to the next track.
        :return: None
        """
        self.fileinfo.focus()
        self.enable_controls(False)
        self.search_button['state'] = "disabled"
        self.player.stop()
        self.player_state = "next"

    def play(self, tracks):
        """
        Set of instructions in preparation  for playing the track.
        :param tracks: TrackList (used for tracking purposes)
        :return: None
        """
        self.fill_track_listbox(tracks)
        if len(tracks) == 0:
            return
        track = tracks.current()
        self.change_fileinfo(track)
        self.update_idletasks()
        self.play_track(track, tracks)
        self.play_loop(tracks)

    def play_track(self, track, tracks, position=None):
        """
        Plays the given track.
        :param track: track to be played
        :param tracks: TrackList
        :param position: Position in ms, if not to be played from the beginning
        :return: None
        """
        self.remove_all_focus()
        self.change_fileinfo(track)
        self.progress['maximum'] = track['durationMillis']
        self.total_time['text'] = convert_milli_to_std(track['durationMillis'])
        self.update_listbox(tracks)
        self.update_idletasks()
        if 'id' in track:
            track_id = track['id']
        elif 'storeId' in track:
            track_id = track['storeId']
        else:
            print 'Problem with track info...'
            print track
            self.play_track(tracks.next(), tracks)
            return
        try:
            stream_audio_url = mobile_client.get_stream_url(track_id, self.device_id)
            self.player.load_url(stream_audio_url)
            self.player.play()
            if position:
                print 'Setting Position...'
                self.player.set_position(position)
                self.progress['value'] = position
                self.current_time['text'] = convert_milli_to_std(position)
                print 'Done'
        except Exception, e:
            print("Error: " + str(e))
            print("Error retrieving track: " + track['title'])
            self.play_track(tracks.next(), tracks)
            return
        max_millis = self.player.get_duration()
        if max_millis > 0:
            self.progress['maximum'] = max_millis
            self.total_time['text'] = convert_milli_to_std(max_millis)
        self.player_state = "play"
        self.pause_state = "unpaused"
        self.enable_controls(True)
        current_search_index = self.search_choose.current()
        current_search = self.search_choose['values'][current_search_index]
        if current_search != "Playlists"\
                and current_search != "Stations":
            self.search_button['state'] = "normal"

    def play_loop(self, tracks):
        """
        Virtual loop that is called every LOOP_INTERVAL milliseconds for updating the time and position gui widgets.
        :param tracks: TrackList
        :return: None
        """
        if self.listbox_tracks != tracks:
            return  # This removes any stale loops that result from new searches
        if not self.player.is_playing() \
                and self.player_state == "play":
            print 'Problem with audio stream. Fixing...'
            self.enable_controls(False)
            self.play_track(tracks.current(), tracks, self.progress['value'])
            self.after(LOOP_INTERVAL, self.play_loop, tracks)
            return
        if self.player_state == "play":
            self.after(LOOP_INTERVAL, self.play_loop, tracks)
        elif self.player_state == "next":
            self.enable_controls(False)
            self.player.stop()
            self.play_track(tracks.next(), tracks)
            self.after(LOOP_INTERVAL, self.play_loop, tracks)
        self.update_controls()

    def update_controls(self):
        """
        Updates the time and position gui widgets.
        :return: None
        """
        if self.pause_state == "unpaused":
            self.progress['value'] += LOOP_INTERVAL
            pos = self.progress['value']
            self.current_time['text'] = convert_milli_to_std(pos)
            if self.progress['value'] >= self.progress['maximum']:
                self.player_state = "next"

    def change_fileinfo(self, metadata):
        """
        Changes the track info for the gui widget
        :param metadata: dictionary containing all metadata about the track
        :return: None
        """
        global next_image
        if 'albumArtRef' in metadata:
            next_image = self.get_photo_image_from_url(metadata['albumArtRef'][0]['url'])
        elif 'artistArtRef' in metadata:
            next_image = self.get_photo_image_from_url(metadata['artistArtRef'][0]['url'])
        else:
            next_image = self.default_image
        if 'year' in metadata:
            year = str(metadata['year'])
        else:
            year = 'Unknown'
        if 'genre' in metadata:
            genre = metadata['genre']
        else:
            genre = 'Unknown'
        self.album_image.configure(image=next_image)
        self.fileinfo['text'] = "Title: " + metadata['title'] + "\nArtist: " + metadata['artist']\
                                + "\nAlbum: " + metadata['album'] + "\nGenre: " + genre + "\nYear: " + year
        self.progress['value'] = 0
        self.current_time['text'] = "0:00"
        self.total_time['text'] = "0:00"

    def get_photo_image_from_url(self, url):
        """
        Gets an album or artist image from the given url.
        :param url: URL of the album/artist image
        :return: ImageTk PhotoImage representing the album/artist image
        """
        try:
            image_bytes = urlopen(url).read()
            data_stream = io.BytesIO(image_bytes)
        except Exception, e:
            print("Error: " + str(e))
            print("Error retrieving song image.")
            print("URL: " + url)
            return self.default_image
        pil_image = Image.open(data_stream)
        return ImageTk.PhotoImage(pil_image, master=self)

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
            self.track_listbox.insert(Tkinter.END, track_listbox_template(track))

        self.listbox_tracks = tracks

    def select_track(self, event):
        """
        Callback function called when track is selected from the track listbox.
        :param event: Tk event
        :return: None
        """
        self.enable_controls(False)
        self.search_button['state'] = "disabled"
        self.player_state = "seek"
        self.player.stop()
        curselection = self.track_listbox.curselection()[0]
        tracks = self.listbox_tracks
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
        self.track_listbox.see(tracks.pos)

    def on_track_seek(self, event):
        """
        Callback function called when the track position gui is clicked.
        :param event: Tk event
        :return: None
        """
        self.fileinfo.focus()
        seek_ratio = event.x / float(self.progress.winfo_width())
        seek_milli = seek_ratio * self.progress['maximum']
        self.progress['value'] = int(seek_milli)
        self.current_time['text'] = convert_milli_to_std(int(seek_milli))
        if not self.player.set_position(seek_milli):
            self.player.stop()

    def seek_relative(self, direction, seconds):
        if direction == 0:
            direction = 1
        direction_sign = direction/abs(direction)
        current_pos = self.progress['value']
        duration = self.progress['maximum']
        new_pos = current_pos + direction_sign * seconds * 1000
        if new_pos < 0:
            new_pos = 0
            self.progress['value'] = 0
        elif new_pos >= duration:
            self.progress['value'] = self.progress['maximum']
            return
        self.progress['value'] = new_pos
        self.current_time['text'] = convert_milli_to_std(new_pos)
        if not self.player.set_position(new_pos):
            self.player.stop()

    def seek_forward(self, seconds):
        self.seek_relative(1, seconds)

    def seek_reverse(self, seconds):
        self.seek_relative(-1, seconds)

    def get_playlist_tracks(self, playlist_dict_tracks):
        """
        Gets TrackList form list of tracks in playlist dictionary.
        :param playlist_dict_tracks: list of tracks from playlist dictionary
        :return: TrackList of playlist tracks
        """
        id_list = [item['trackId'] for item in playlist_dict_tracks]
        playlist_tracks = [track for track in self.library if track['id'] in id_list]
        playlist_tracks.sort(key=lambda trk: id_list.index(trk['id']))
        return TrackList(playlist_tracks)

    def on_track_download(self, track):
        GMusicDownloader.download_track(track, path='', mobile_client=mobile_client, device_id=self.device_id)


'''class CenterableToplevel(Tkinter.Toplevel):
    def __init__(self, parent):
        Tkinter.Toplevel.__init__(self, parent)
        self.parent = parent

    def center(self):
        self.update_idletasks()

        if self.parent is None:
            parent_x, parent_y = 0, 0
            parent_w, parent_h = self.winfo_screenwidth(), self.winfo_screenheight()
        else:
            parent_x, parent_y = (int(_) for _ in self.parent.geometry().split('+', 1)[1].split('+'))
            parent_w, parent_h = (int(_) for _ in self.parent.geometry().split('+', 1)[0].split('x'))
        w, h = (int(_) for _ in self.geometry().split('+')[0].split('x'))
        x = parent_x + parent_w / 2 - w / 2
        y = parent_y + parent_h / 2 - h / 2
        self.geometry('+%d+%d' % (x, y))


class Splash(CenterableToplevel):
    def __init__(self, parent):
        CenterableToplevel.__init__(self, parent)
        self.master.withdraw()
        self.overrideredirect(True)
        self.geometry('400x200')

        inset = Tkinter.Frame(self, bg='#ed7c00', padx=10, pady=10)
        inset.pack(fill=Tkinter.BOTH, expand=1)
        message = Tkinter.Label(inset, text='PyPlayMusic is loading...',
                                font=tkFont.Font(inset, family='Times', size=23, weight='bold'),
                                bg='#fd8c00')
        message.pack(fill=Tkinter.BOTH, expand=1)

        self.center()


class ChooseDevice(CenterableToplevel):
    """

    """
    def __init__(self, parent):
        CenterableToplevel.__init__(self, parent)
        self.parent = parent
        self.wm_title('Choose Device')
        self.protocol('WM_DELETE_WINDOW', lambda x=1: x)

        self.text_label = Tkinter.Label(self, text='Choose a mobile device ID.')
        self.text_label.pack()

        dev_list = []
        for dev in mobile_client.get_registered_devices():
            if dev['type'] == 'ANDROID' or dev['type'] == 'IOS':
                dev_list.append(dev['friendlyName'] + ':' + dev['id'])

        self.device_chooser = ttk.Combobox(self, values=dev_list)
        self.device_chooser.bind('<<ComboboxSelected>>', self.device_chosen)

        self.bind("<FocusOut>", self.regain_focus)

        self.device_chooser.pack()
        self.center()
        self.regain_focus(None)

    def device_chosen(self, event):
        device_choice_index = self.device_chooser.current()
        device_choice = self.device_chooser['values'][device_choice_index]
        self.parent.device_id = device_choice.split(':0x')[1]
        self.destroy()

    def regain_focus(self, event):
        self.attributes("-topmost", True)
        self.grab_set()
        self.device_chooser.focus()'''


if __name__ == "__main__":
    splash = shared.Splash()
    mobile_client = Mobileclient(debug_logging=False)
    authenticated = False
    force_prompt = False
    while not authenticated:
        auth_handle = auth.AuthHandler("Google Auth", force_prompt, splash)
        if auth_handle.canceled:
            exit(0)
        email = auth_handle.uname
        password = auth_handle.passwd
        if mobile_client.login(email, password, Mobileclient.FROM_MAC_ADDRESS):
            authenticated = True
        else:
            force_prompt = True

    app = MainWindow()
    app.title('PyPlayMusic')
    app.mainloop()
