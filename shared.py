import tkFont
import Tkinter
import ttk


class Centerable(object):
    """
    Class that adds a center member to windows in this application.
    """
    def center(self):
        """
        Centers the window
        :return: None
        """
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


class Splash(Centerable, Tkinter.Toplevel):
    """
    Class for the splash window.
    """
    def __init__(self, message_text='PyPlayMusic is loading...', parent=None):
        Tkinter.Toplevel.__init__(self, parent)
        self.parent = parent
        self.master.withdraw()
        self.overrideredirect(True)
        self.geometry('400x200')

        inset = Tkinter.Frame(self, bg='#ed7c00', padx=10, pady=10)
        inset.pack(fill=Tkinter.BOTH, expand=1)
        message = Tkinter.Label(inset, text=message_text,
                                font=tkFont.Font(inset, family='Times', size=23, weight='bold'),
                                bg='#fd8c00')
        message.pack(fill=Tkinter.BOTH, expand=1)

        self.center()
        self.update_idletasks()


class ChooseDevice(Centerable, Tkinter.Toplevel):
    """
    Class that defines the device chooser window.
    """
    def __init__(self, parent, mobile_client):
        """
        Init function for the ChooseDevice class
        :param parent: Used for centering purposes
        :param mobile_client: GMusicAPI Mobileclient instance
        """
        Tkinter.Toplevel.__init__(self, parent)
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
        self.device_chooser.bind('<<ComboboxSelected>>', lambda event: self.device_chosen())

        self.bind("<FocusOut>", lambda event: self.regain_focus())

        self.device_chooser.pack()
        self.center()
        self.update_idletasks()
        self.regain_focus()

    def device_chosen(self):
        """
        Callback function evoked once the device has been chosen.
        :return: None
        """
        device_choice_index = self.device_chooser.current()
        device_choice = self.device_chooser['values'][device_choice_index]
        self.parent.device_id = device_choice.split(':0x')[1]
        self.destroy()

    def regain_focus(self):
        """
        Callback function evoked when ChooseDevice loses focus.
        :return: None
        """
        self.attributes("-topmost", True)
        self.grab_set()
        self.device_chooser.focus()
