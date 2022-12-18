
import tkinter as tk
from tkinter import ttk
from libs import utils
import sys
import copy
from classes import paraText

class paraTxt(tk.Tk):
    pt_padx = 24
    pt_pady = 0
    hcolor = "#5376FE"

    def __init__(self):
        super().__init__()
        self.title('paraTxt')
        self.geometry('900x600')
        self.widget_paraText = paraText.paraText(wrap=tk.WORD,
                                                 font=("Arial", 25),
                                                 width=40, border=0)
        self.widget_paraText.grid(column=0, row=1, padx=self.pt_padx,
                                  pady=self.pt_pady)
        self.spawner_color = None
        self.dropdown_spawner = None
        self.dropdown_holder = None
        self.setup_header()

    def clear_dropdown_holder(self, spawner):
        self.update_idletasks()
        spawner.config(background=self.spawner_color)
        self.dropdown_holder.destroy()
        self.update_idletasks()
        self.spawner_color = None
        self.dropdown_holder = None
        self.update_idletasks()
        self.focus_set()

    def setup_header(self):
        header = tk.LabelFrame(self)
        header.grid(column=0, row=0, padx=self.pt_padx, pady=self.pt_pady, sticky='w')
        subheaders = []
        subheaders.append(self.setup_sh(header, 'File'))
        subheaders.append(self.setup_sh(header, 'Edit'))
        self.update_idletasks()

    def setup_sh(self, header, type_str):
        """
        :param (tk.LabelFrame) header:
        :param (str) type_str:
        :return (tk.LabelFrame) subheader:
        """
        # sh = SubHeader
        subheader = tk.Label(header, text=type_str)
        subheader.pack(side=tk.LEFT)
        subheader.bind('<Button-1>',
                       lambda e: self.spawn_shd(subheader,
                                                type_str))
        return subheader

    def spawn_shd(self, subheader, type_str):
        """
        :param (tk.Label) subheader:
        :param (str) type_str:
        :return (tk.LabelFrame) dropdown:
        """
        dropdown = tk.LabelFrame(self)
        if not self.dropdown_holder is None:
            self.clear_dropdown_holder(self.dropdown_spawner)
        dropdown.focus_force()
        self.spawner_color = subheader.cget('background')
        self.dropdown_spawner = subheader
        subheader.config(background=self.hcolor)
        # shd = SubHeader Dropdown
        pop_funcs = {
            'File': self.pop_file_dropdown,
            'Edit': self.pop_edit_dropdown
        }
        options = pop_funcs[type_str](dropdown)
        for o in options:
            o.pack(side=tk.TOP)
        # Make sure these go last
        pl_x = subheader.winfo_x() + self.pt_padx
        pl_y = subheader.winfo_y() + subheader.winfo_height() + self.pt_pady
        dropdown.place(x=pl_x, y=pl_y, anchor=tk.NW)
        self.dropdown_holder = dropdown
        dropdown.bind('<Button-1>', lambda e: print(e))
        dropdown.bind('<FocusOut>', lambda e: self.clear_dropdown_holder(subheader))
        self.update_idletasks()


    def pop_file_dropdown(self, dropdown):
        dd_new = tk.Label(dropdown, text='New...')
        dd_open = tk.Label(dropdown, text='Open...')
        options = [dd_new, dd_open]
        return options

    def pop_edit_dropdown(self, dropdown):
        dd_mode = tk.Label(dropdown, text='Mode...')
        options = [dd_mode]
        return options

    def get_paraText_data(self):
        return self.widget_paraText.directory.items()


# TODO
