import json
import os
#import tkFont
import tkFileDialog
import Tkinter
import ttk
from urllib2 import urlopen

from eyed3.id3.frames import ImageFrame
from eyed3.mp3 import Mp3AudioFile
from gmusicapi import Mobileclient
import auth


class MainWindow(Tkinter.Tk):
    """
    Main GUI window for the application.
    """
    def __init__(self, parent, mobile_client):
        """
        MainWindow __init__ function
        :param parent: Tk parent. Fine to be None.
        :param mobile_client: gmusicapi Mobileclient is expected
        :return: None
        """
        Tkinter.Tk.__init__(self, parent)
        self.parent = parent
        self.resizable(0,0)
        self.mobile_client = mobile_client
        self.device_id = None
        self.library = self.mobile_client.get_all_songs()

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
        self.device_chooser = ChooseDevice(self, mobile_client)

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
        self.geometry("+%d+%d" % (x, y))

    def fill_tree(self, tracks):
        """

        """
        tracks.sort(key=lambda track: track['title'])
        tracks.sort(key=lambda track: track['trackNumber'])
        tracks.sort(key=lambda track: track['discNumber'])
        tracks.sort(key=lambda track: track['album'])
        tracks.sort(key=lambda track: track['albumArtist'])
        #print(tracks[0])
        for track in tracks:
            #print(track['title'])
            if track['albumArtist'] == '':
                artistLabel = ''
            else:
                artistLabel = 'ar:$:' + track['albumArtist'].strip()

            if track['album'] == '':
                albumLabel = ''
            else:
                albumLabel = 'al:$:' + track['album'].strip()

            try:
                if artistLabel != '':
                    self.tree.insert('', 'end', artistLabel, text='Artist: ' + track['albumArtist'], values=('artist:' + track['albumArtist'],))
            except Tkinter.TclError:
                pass
            try:
                if albumLabel != '':
                    self.tree.insert(artistLabel, 'end', albumLabel + artistLabel, text='Album: ' + track['album'], values=('album:' + track['album'],))
            except Tkinter.TclError:
                pass
            self.tree.insert(albumLabel + artistLabel, 'end', track['title'] + track['id'], text=track['title'], values=(json.dumps(track),))

    def filename_template(self, track):
        """
        Formats template for naming a downloaded file
        :param track: dict containing track info
        :return: filename string
        """
        return str(track['trackNumber']) + "-"  + track['title'] + "-" + track['album'] + "-" + track['artist'] + ".mp3"

    def get_image_tuple_from_url(self, url):
        """
        Gets an album or artist image from the given url.
        :param url: URL of the album/artist image
        :return: tuple containing mime-type and image data
        """
        response = urlopen(url)
        mime_type = response.info().type
        image_bytes = response.read()
        return (mime_type, image_bytes)

    def on_download_press(self):
        """
        Callback for pressing the download button. This will create a folder
        structure and download tracks based on what is selected in the tree.
        :return: None
        """
        if self.device_id is None:
            ChooseDevice(self, self.mobile_client)
            print(self.device_id)
            return
        base_dir = tkFileDialog.askdirectory()
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
                    #print(album_item)
                    album_name = album_item['values'][0].split(':', 1)[1]
                    progress.set_message('Retreiving: ' + album_name)
                    os.makedirs(os.path.join(base_dir, artist_name, album_name))
                    progress.steps_complete(1)
                    tracks = self.tree.get_children(album)
                    for track_child in tracks:
                        track_item = self.tree.item(track_child)
                        track_data = track_item['values'][0]
                        track = json.loads(track_data)
                        progress.set_message('Retreiving: ' + track['title'])
                        self.download_track(track, os.path.join(base_dir, artist_name, album_name))
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
                    self.download_track(track, os.path.join(base_dir, album_name))
                    progress.steps_complete(1)
            else:
                track = json.loads(data)
                #print track['title']
                progress.set_message('Retreiving: ' + track['title'])
                self.download_track(track, base_dir)
                progress.steps_complete(1)
        progress.destroy()

    def count_steps(self):
        """

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

    def download_track(self, track, path=''):
        """
        Downloads the mp3 file of the given track
        :param track: Track dict
        :param path: Path to download to. If omitted, then will download to current working directory.
        :return: None
        """
        try:
            stream_url = self.mobile_client.get_stream_url(track['id'], self.device_id)
            song_bytes = urlopen(stream_url).read()
            #print stream_url
        except Exception, e:
            print "Error retrieving track: " + track['title']
            print "Error: ", e
            return

        output_file = open(os.path.join(path, self.filename_template(track)), "wb")
        output_file.write(song_bytes)
        output_file.close()
        id3 = Mp3AudioFile(output_file.name)
        id3.initTag()
        id3.tag.title = track['title']
        id3.tag.artist = track['artist']
        id3.tag.album = track['album']
        id3.tag.genre = track['genre']
        #print(track['year'])
        year_int = int(track['year'])
        if year_int != 0:
            id3.tag.release_date = year_int
            id3.tag.original_release_date = year_int
            id3.tag.recording_date = year_int
        id3.tag.track_num = track['trackNumber']
        if track.has_key('albumArtRef'):
            mime_type, image_data = self.get_image_tuple_from_url(track['albumArtRef'][0]['url'])
            #mime_type = image_tuple[0]
            #image_data = image_tuple[1]
            id3.tag.images.set(ImageFrame.FRONT_COVER, image_data, mime_type)
        elif track.has_key('artistArtRef'):
            mime_type, image_data = self.get_image_tuple_from_url(track['artistArtRef'][0]['url'])
            #mime_type = image_tuple[0]
            #image_data = image_tuple[1]
            id3.tag.images.set(ImageFrame.FRONT_COVER, image_data, mime_type)
        id3.tag.save()
        #print(track)
        #print(id3.tag.getBestDate())

class ProgressWindow(Tkinter.Toplevel):
    """
    Progress window for downloading.
    """
    def __init__(self, parent, minimum, maximum):
        Tkinter.Toplevel.__init__(self, parent) 
        self.parent = parent
        self.overrideredirect(1)
        self.message = Tkinter.Label(self)
        self.message.pack()

        self.bar = ttk.Progressbar(self, orient="horizontal", length=200, mode="determinate")
        self.bar['value'] = minimum
        self.bar['maximum'] = maximum
        self.bar.pack(padx=10, pady=10)

        #self.grab_set()

    def center(self):
        self.update_idletasks()
        parent_x, parent_y = (int(_) for _ in self.parent.geometry().split('+', 1)[1].split('+'))
        parent_w, parent_h = (int(_) for _ in self.parent.geometry().split('+', 1)[0].split('x'))
        w, h = (int(_) for _ in self.geometry().split('+')[0].split('x'))
        x = parent_x + parent_w/2 - w/2
        y = parent_y + parent_h/2 - h/2
        self.geometry("+%d+%d" % (x, y))

    def steps_complete(self, number_of_steps):
        self.bar['value'] += number_of_steps
        self.parent.update_idletasks()
        self.update_idletasks()
        #print(self.bar['value'])

    def set_message(self, message_text):
        self.message.config(text=message_text)
        self.update_idletasks()


class ChooseDevice(Tkinter.Toplevel):
    """

    """
    def __init__(self, parent, mobile_client):
        Tkinter.Toplevel.__init__(self, parent)
        self.parent = parent
        self.wm_title('Choose Device')
        self.attributes("-topmost", True)
        self.protocol('WM_DELETE_WINDOW', lambda x=1: x)

        self.text_label = Tkinter.Label(self, text='Choose a mobile device ID.')
        self.text_label.pack()

        dev_list = []
        for dev in mobile_client.get_registered_devices():
            if dev['type'] == 'ANDROID' or dev['type'] == 'IOS':
                dev_list.append(dev['friendlyName'] + ':' + dev['id'])
        
        self.device_chooser_var = None
        self.device_chooser = ttk.Combobox(self, textvariable=self.device_chooser_var, values=dev_list)
        self.device_chooser.bind('<<ComboboxSelected>>', self.device_chosen)

        self.bind("<FocusOut>", self.regain_focus)

        self.device_chooser.pack()
        self.center()
        self.regain_focus()

    def device_chosen(self, e):
        device_choice = self.device_chooser.get()
        #print(device_choice)
        self.parent.device_id = device_choice.split(':0x')[1]
        self.destroy()

    def center(self):
        self.update_idletasks()
        parent_x, parent_y = (int(_) for _ in self.parent.geometry().split('+', 1)[1].split('+'))
        parent_w, parent_h = (int(_) for _ in self.parent.geometry().split('+', 1)[0].split('x'))
        w, h = (int(_) for _ in self.geometry().split('+')[0].split('x'))
        x = parent_x + parent_w/2 - w/2
        y = parent_y + parent_h/2 - h/2
        self.geometry('+%d+%d' % (x, y))

    def regain_focus(self, e=None):
        self.grab_set()
        self.focus()

if __name__ == "__main__":
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

    app = MainWindow(None, mobile_client)
    app.title('GMusic Downloader')
    #app.center()
    app.mainloop()
