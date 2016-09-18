import json
import os
import tkFileDialog
import Tkinter
import ttk
from urllib2 import urlopen

from eyed3.id3.frames import ImageFrame
from eyed3.mp3 import Mp3AudioFile
from gmusicapi import Mobileclient
import auth
import shared


def filename_template(track):
    """
    Formats template for naming a downloaded file
    :param track: dict containing track info
    :return: filename string
    """
    return str(track['trackNumber']) + "-" + track['title'] + "-" + track['album'] + "-" + track['artist'] + ".mp3"


def get_image_tuple_from_url(url):
    """
    Gets an album or artist image from the given url.
    :param url: URL of the album/artist image
    :return: tuple containing mime-type and image data
    """
    response = urlopen(url)
    mime_type = response.info().type
    image_bytes = response.read()
    return mime_type, image_bytes


def download_track(track, path='', mobile_client=None, device_id=None):
    """
    Downloads the mp3 file of the given track

    :param track: Track dict
    :param path: Path to download to. If omitted, then will download to current working directory.
    :param mobile_client: Instance of the Mobileclient class
    :param device_id: Mobile device ID
    :return: None
    """
    if 'id' in track:
        track_id = track['id']
    elif 'storeId' in track:
        track_id = track['storeId']
    else:
        print 'Problem with track info...'
        print track
        return
    try:
        stream_url = mobile_client.get_stream_url(track_id, device_id)
        song_bytes = urlopen(stream_url).read()
    except Exception, e:
        print "Error retrieving track: " + track['title']
        print "Error: ", e
        return

    output_file = open(os.path.join(path, filename_template(track)), "wb")
    output_file.write(song_bytes)
    output_file.close()
    id3 = Mp3AudioFile(output_file.name)
    id3.initTag()
    id3.tag.title = track['title']
    id3.tag.artist = track['artist']
    id3.tag.album = track['album']
    id3.tag.genre = track['genre']
    year_int = int(track['year'])
    if year_int != 0:
        id3.tag.release_date = year_int
        id3.tag.original_release_date = year_int
        id3.tag.recording_date = year_int
    id3.tag.track_num = track['trackNumber']
    if 'albumArtRef' in track:
        mime_type, image_data = get_image_tuple_from_url(track['albumArtRef'][0]['url'])
        id3.tag.images.set(ImageFrame.FRONT_COVER, image_data, mime_type)
    elif 'artistArtRef' in track:
        mime_type, image_data = get_image_tuple_from_url(track['artistArtRef'][0]['url'])
        id3.tag.images.set(ImageFrame.FRONT_COVER, image_data, mime_type)
    id3.tag.save()


class MainWindow(shared.Centerable, Tkinter.Tk):
    """
    Main GUI window for the application.
    """
    def __init__(self, parent=None):
        """
        MainWindow __init__ function
        :param parent: Tk parent. Fine to be None.
        :return: None
        """
        Tkinter.Tk.__init__(self)
        self.parent = parent
        self.resizable(0, 0)
        self.device_id = None
        self.library = mobile_client.get_all_songs()

        # Initializes the gui widgets. Should only be called from the __init__function.
        self.grid()

        # Set up widgets
        tracklist_frame = Tkinter.Frame(self)
        tracklist_scrollbar = Tkinter.Scrollbar(self)
        self.tree = tree = ttk.Treeview(self, height=30, yscrollcommand=tracklist_scrollbar.set)
        tree.column("#0", width=750)
        tracklist_scrollbar.config(command=tree.yview)
        download_button = Tkinter.Button(self, text="Download", state="normal", command=self.on_download_press)

        # place widgets on grid
        tracklist_frame.grid(column=0, row=0, rowspan=1, sticky='NS')
        self.tree.grid(in_=tracklist_frame, column=0, row=0, sticky='NS')
        tracklist_scrollbar.grid(in_=tracklist_frame, column=1, row=0, sticky='NS')
        download_button.grid(column=0, row=1, sticky='EW')

        self.fill_tree(self.library)
        self.center()
        splash.master.destroy()
        self.device_chooser = shared.ChooseDevice(self, mobile_client)

    def fill_tree(self, tracks):
        """
        Fills the tree
        :param tracks:
        :return: None
        """
        tracks.sort(key=lambda trk: trk['title'])
        tracks.sort(key=lambda trk: trk['trackNumber'])
        tracks.sort(key=lambda trk: trk['discNumber'])
        tracks.sort(key=lambda trk: trk['album'])
        tracks.sort(key=lambda trk: trk['albumArtist'])
        for track in tracks:
            if track['albumArtist'] == '':
                artist_label = ''
            else:
                artist_label = 'ar:$:' + track['albumArtist'].strip()

            if track['album'] == '':
                album_label = ''
            else:
                album_label = 'al:$:' + track['album'].strip()

            try:
                if artist_label != '':
                    self.tree.insert('', 'end', artist_label, text='Artist: ' + track['albumArtist'],
                                     values=('artist:' + track['albumArtist'],))
            except Tkinter.TclError:
                pass
            try:
                if album_label != '':
                    self.tree.insert(artist_label, 'end', album_label + artist_label, text='Album: ' + track['album'],
                                     values=('album:' + track['album'],))
            except Tkinter.TclError:
                pass
            self.tree.insert(album_label + artist_label, 'end', track['title'] + track['id'], text=track['title'],
                             values=(json.dumps(track),))

    def on_download_press(self):
        """
        Callback for pressing the download button. This will create a folder
        structure and download tracks based on what is selected in the tree.
        :return: None
        """
        if self.device_id is None:
            shared.ChooseDevice(self, mobile_client)
            # print(self.device_id)
            return
        base_dir = tkFileDialog.askdirectory(master=self)
        if not base_dir:
            return
        steps_number = self.count_steps()
        progress = ProgressWindow(self, 0, steps_number)
        progress.set_message('Downloading...')
        progress.center()
        for selected_item in self.tree.selection():
            values = self.tree.item(selected_item)['values']
            data = values[0]
            if data.startswith('artist:'):
                progress.steps_complete(1)
                artist_name = data.split(':', 1)[1]
                progress.set_message('Retreiving: ' + artist_name)
                albums = self.tree.get_children(selected_item)
                for album in albums:
                    album_item = self.tree.item(album)
                    album_name = album_item['values'][0].split(':', 1)[1]
                    progress.set_message('Retrieving: ' + album_name)
                    os.makedirs(os.path.join(base_dir, artist_name, album_name))
                    progress.steps_complete(1)
                    tracks = self.tree.get_children(album)
                    for track_child in tracks:
                        track_item = self.tree.item(track_child)
                        track_data = track_item['values'][0]
                        track = json.loads(track_data)
                        progress.set_message('Retrieving: ' + track['title'])
                        download_track(track, os.path.join(base_dir, artist_name, album_name),
                                       mobile_client=mobile_client, device_id=self.device_id)
                        progress.steps_complete(1)
            elif data.startswith('album:'):
                progress.steps_complete(1)
                album_name = data.split(':', 1)[1]
                progress.set_message('Retreiving: ' + album_name)
                os.makedirs(os.path.join(base_dir, album_name))
                progress.steps_complete(1)
                tracks = self.tree.get_children(selected_item)
                for track_child in tracks:
                    track_item = self.tree.item(track_child)
                    track_data = track_item['values'][0]
                    track = json.loads(track_data)
                    progress.set_message('Retreiving: ' + track['title'])
                    download_track(track, os.path.join(base_dir, album_name), mobile_client=mobile_client,
                                   device_id=self.device_id)
                    progress.steps_complete(1)
            else:
                track = json.loads(data)
                progress.set_message('Retreiving: ' + track['title'])
                download_track(track, base_dir, mobile_client=mobile_client, device_id=self.device_id)
                progress.steps_complete(1)
        progress.destroy()

    def count_steps(self):
        """
        Counts the number of steps involved in downloading the selected items.
        :return: The number of steps to tell the progress bar to use.
        """
        count = 0
        selection = self.tree.selection()
        for selected_item in selection:
            count += 1
            for child in self.tree.get_children(selected_item):
                count += 1
                for grandchild in self.tree.get_children(child):
                    count += 1
        return count


class ProgressWindow(shared.Centerable, Tkinter.Toplevel):
    """
    Progress window for downloading.
    """
    def __init__(self, parent, minimum, maximum):
        """
        Init function for ProgressWindow class.
        :param parent: Parent widget
        :param minimum: Starting value
        :param maximum: Maximum value
        """
        Tkinter.Toplevel.__init__(self, parent)
        self.parent = parent
        self.overrideredirect(1)
        self.message = Tkinter.Label(self)
        self.message.pack()

        self.bar = ttk.Progressbar(self, orient="horizontal", length=200, mode="determinate")
        self.bar['value'] = minimum
        self.bar['maximum'] = maximum
        self.bar.pack(padx=10, pady=10)

    def steps_complete(self, number_of_steps):
        """
        Adds the specified number of steps to the progress window.
        :param number_of_steps: Number of steps to add
        :return: None
        """
        self.bar['value'] += number_of_steps
        self.parent.update_idletasks()
        self.update_idletasks()

    def set_message(self, message_text):
        self.message.config(text=message_text)
        self.update_idletasks()


if __name__ == "__main__":
    splash = shared.Splash('GMusicDownloader\nis loading...')
    #mobile_client = Mobileclient(debug_logging=True)
    mobile_client = Mobileclient(debug_logging=False)
    authenticated = False
    force_prompt = False
    while not authenticated:
        auth_handle = auth.AuthHandler("Google Auth", force_prompt)
        if auth_handle.canceled:
            exit(0)
        email = auth_handle.uname
        password = auth_handle.passwd
        if mobile_client.login(email, password, Mobileclient.FROM_MAC_ADDRESS):
            authenticated = True
        else:
            force_prompt = True

    app = MainWindow()
    app.title('GMusic Downloader')
    app.mainloop()
