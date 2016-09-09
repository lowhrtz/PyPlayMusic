#!/usr/bin/python

import tkFont
import Tkinter
from Crypto.Cipher import Blowfish
from Crypto import Random
from struct import pack, unpack

KEY = b'4hdkljf01n3(ijl2hqsamn^wjl'
CACHE_FILE = '.cache'


def open_cached():
    """
    Opens cached credentials file.
    :return: File object or None if file does not exist or cannot be opened
    """
    try:
        cached = open(CACHE_FILE)
    except IOError:
        return None
    return cached


def encrypt(passwd):
    """
    Encrypts the given string.
    :param passwd: password string
    :return: encrypted string representation of given passwd
    """
    bs = Blowfish.block_size
    iv = Random.new().read(bs)
    cipher = Blowfish.new(KEY, Blowfish.MODE_CBC, iv)
    plen = bs - len(passwd) % bs
    padding = [plen]*plen
    padding = pack('b'*plen, *padding)
    return iv + cipher.encrypt(passwd + padding)


def decrypt(ciphered_pw):
    """
    Decrypts the given encrypted string.
    :param ciphered_pw: string to be decrypted
    :return: unencrypted string
    """
    bs = Blowfish.block_size
    iv = Random.new().read(bs)
    cipher = Blowfish.new(KEY, Blowfish.MODE_CBC, iv)
    padded_decrypt = cipher.decrypt(ciphered_pw)
    padding_len = unpack('b', padded_decrypt[-1:])[0]
    return padded_decrypt[len(iv):len(ciphered_pw) - padding_len]


class AuthHandler(object):
    """
    Class used as an interface for external programs/libraries. Particularly useful for testing cached authentication
    before opening the AuthWindow.
    """
    def __init__(self, title, force_prompt=False, above_this=None):
        """
        AuthHandler __init__ function
        :param title: Desired title for AuthWindow
        :param force_prompt: boolean to indicate whether to open AuthWindow even if cached file is found and readable
        :return: None
        """
        self.uname = None
        self.passwd = None
        self.canceled = False
        cached = open_cached()
        if cached and not force_prompt:
            self.uname = cached.readline().rstrip()
            self.passwd = decrypt(cached.read())
        else:
            auth_win = AuthWindow(None, title, above_this)
            # auth_win.mainloop()
            # This used to be a call to auth_win.mainloop() but this caused issues when the splash was introduced
            import time
            while True:
                # This causes it to loop at the same(or at least comparable) rate as mainloop
                time.sleep(.1)
                try:
                    auth_win.update_idletasks()
                    auth_win.update()
                except Tkinter.TclError:
                    # A TclError is raised when update is called after the window has been destroyed
                    break
            if not auth_win.canceled:
                self.uname = auth_win.uname
                self.passwd = auth_win.passwd
            else:
                self.canceled = auth_win.canceled


class AuthWindow(Tkinter.Tk):
    """
    Tk window for prompting for username and password.
    """
    def __init__(self, parent, title, above_this=None):
        """
        AuthWindow __init__ function.
        :param parent: Tk parent, OK to be None
        :param title: title of the window
        :return: None
        """
        Tkinter.Tk.__init__(self, parent)
        self.parent = parent
        self.title(title)
        self.protocol('WM_DELETE_WINDOW', self.on_cancel_click)
        self.uname = None
        self.passwd = None
        self.canceled = True
        self.font = tkFont.Font(self, family='Helvetica', size=13)
        self.above_this = above_this
        if above_this:
            above_this.withdraw()
        self.initialize()

        # Initialize gui widgets.
        self.grid()

        self.u_field_variable = Tkinter.StringVar(self)
        self.user_field = Tkinter.Entry(self, textvariable=self.u_field_variable, font=self.font)
        self.p_field_variable = Tkinter.StringVar(self)
        self.pass_field = Tkinter.Entry(self, textvariable=self.p_field_variable, show='*', font=self.font)
        auth_button = Tkinter.Button(self, text=u"OK", command=self.on_auth_click, font=self.font)
        cancel_button = Tkinter.Button(self, text=u"Cancel", command=self.on_cancel_click, font=self.font)
        self.user_field.bind("<Return>", self.on_press_enter)
        self.pass_field.bind("<Return>", self.on_press_enter)

        # Place widgets in the grid
        self.user_field.grid(column=0, columnspan=2, row=0, sticky='EW')
        self.pass_field.grid(column=0, columnspan=2, row=1, sticky='EW')
        auth_button.grid(column=1, row=2, sticky='EW')
        cancel_button.grid(column=0, row=2, sticky='EW')

        self.user_field.focus_set()
        self.center()

    def center(self):
        """
        Centers the AuthWindow
        :return: None
        """
        self.update_idletasks()
        w = self.winfo_screenwidth()
        h = self.winfo_screenheight()
        size = tuple(int(_) for _ in self.geometry().split('+')[0].split('x'))
        x = w/2 - size[0]/2
        y = h/2 - size[1]/2
        self.geometry("+%d+%d" % (x, y))

    def on_press_enter(self, event):
        """
        Callback function called when enter is pressed.
        :param event: Tk event
        :return: None
        """
        self.on_auth_click()

    def on_auth_click(self):
        """
        Callback function called when "OK" button is clicked.
        :return: None
        """
        self.canceled = False
        self.uname = self.u_field_variable.get()
        self.passwd = self.p_field_variable.get()
        cached = open(CACHE_FILE, 'w')
        cached.write(self.uname + '\n' + encrypt(self.passwd))
        if self.above_this:
            self.above_this.deiconify()
        self.destroy()

    def on_cancel_click(self):
        """
        Callback function called when "Cancel" button is clicked.
        :return: None
        """
        self.canceled = True
        self.destroy()

if __name__ == "__main__":
    app = AuthWindow(None, "Test")
    app.mainloop()
