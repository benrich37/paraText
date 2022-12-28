
import tkinter as tk
from tkinter import ttk
from libs import utils
import sys
import copy
from classes import paraText
from libs import utils

class paraTxt(tk.Tk):
    pt_padx = 24
    pt_pady = 0
    hcolor = "#5376FE"
    default_dataview = False

    def __init__(self):
        super().__init__()
        self.title('paraTxt')
        self.geometry('1300x600')
        self.widget_paraText = paraText.paraText(wrap=tk.WORD,
                                                 font=("Arial", 18),
                                                 width=40, border=0)
        self.widget_paraText.grid(column=0, row=1, padx=self.pt_padx,
                                  pady=self.pt_pady)
        self.spawner_color = None
        self.edit_data = False
        self.dropdown_spawner = None
        # This needs to be a list of widgets
        self.dropdown_holder = []
        self.dataview_bool = self.default_dataview
        self.dataview_holder = None
        self.setup_header()
        self.setup_dataview()
        self.setup_editor()

    def clear_dropdown_holder(self):
        self.update_idletasks()

        self.dropdown_spawner.config(background=self.spawner_color)
        for w in self.dropdown_holder:
            w.destroy()
        # self.dropdown_holder.destroy()
        self.update_idletasks()
        self.spawner = None
        self.spawner_color = None
        self.dropdown_holder = []
        self.update_idletasks()
        self.focus_set()

    def start_dropdown_holder(self, dropdown, spawner):
        if not len(self.dropdown_holder) == 0:
            self.clear_dropdown_holder()
        self.dropdown_holder.append(dropdown)
        self.spawner_color = spawner.cget('background')
        self.dropdown_spawner = spawner
        spawner.config(background=self.hcolor)


    def check_bounds_conflict(self, bounds):
        """
        :param bounds: List of two char indices
        :return bool, child_tag:
        """
        self.widget_paraText.update_child_bounds()
        ref = self.widget_paraText.child_bounds.items()
        for c in ref:
            if utils.conflict_bounds(bounds, c[1]):
                return True, c[0]
        return False, 'n/a'


    def create_instance(self):
        bounds = self.widget_paraText.tag_ranges(tk.SEL)
        ret_val = self.check_bounds_conflict(bounds)

    def instance_creation(self, event):
        print('boop')
        window = tk.Toplevel(self)
        window.geometry('200x200')
        window.title('instance_creation')
        op1 = tk.Label(window, text='Create New Family...')
        op1.grid(column=1, row=1)
        op2 = tk.Label(window, text='Add to Existing Family...')
        op2.grid(column=1, row=2)
        op2.bind('<Button-1>', lambda e: self.family_editor())


    def family_editor(self):
        window = tk.Toplevel(self)
        window.geometry('400x200')
        window.title('family_editor')
        self.family_gridder(window)

    def grid_label(self, master, text, row, column):
        tk.Label(master, text=text, borderwidth=1, relief='solid').grid(row=row, column=column)

    def grid_title(self, master, text, row, column):
        tk.Label(master, text=text).grid(row=row, column=column)

    def grid_block(self, master, x0, xw, y0, yw, color):
        tk.Label(master, text='.'*2500, background=color, highlightbackground=color, height=1, font=("Arial", 1)).grid(row=y0, rowspan=yw, column=x0, columnspan=xw)

    def family_gridder(self, window):
        offx = 0
        offy = 2
        self.grid_title(window, 'Family name', 0, 0 + offx)
        self.grid_title(window, 'Options', 0, 1 + offx)
        self.grid_title(window, 'Existing Children', 0, 2 + offx)
        self.grid_title(window, 'Children Bounds', 0, 3 + offx)
        self.grid_block(window, 0, 4 + offx, 1, 1, 'black')
        self.widget_paraText.update_child_bounds()
        pr = 0
        for p in self.widget_paraText.directory.items():
            # Family label
            self.grid_label(window, p[0], pr + offy, 0 + offx)
            # option labels
            for i in range(len(p[1][0])):
                self.grid_label(window, p[1][0][i], pr + i + offy, 1 + offx)
            # Children labels
            for i in range(len(p[1][1])):
                self.grid_label(window, p[1][1][i], pr + i + offy, 2 + offx)
            # Children bounds
            for i in range(len(p[1][2])):
                self.grid_label(window, p[1][2][i], pr + i + offy, 3 + offx)
            # Find how many rows the family is occupying before starting next one
            row_max = 0
            for i in range(3):
                row_max = max(row_max, len(p[1][i]))
            pr += row_max





    def setup_editor(self):
        self.widget_paraText.tag_bind(tk.SEL, '<Button-2>', lambda e: self.instance_creation(e))

    def setup_dataview(self):
        if self.dataview_bool:
            self.show_data()
        else:
            if not self.dataview_holder is None:
                self.dataview_holder.destroy()
                self.focus_set()

    def show_data(self):
        data = self.get_paraText_data()
        dataview = tk.Text()
        dataview.insert('1.0', utils.dict_pretty(data))
        dataview.grid(column=1, row=1, padx=self.pt_padx/10,
                                  pady=self.pt_pady)
        self.dataview_holder = dataview
        dataview.focus_set()
        dataview.config(state=tk.DISABLED)

    def setup_header(self):
        header = tk.LabelFrame(self)
        header.grid(column=0, row=0, padx=self.pt_padx, pady=self.pt_pady, sticky='w')
        subheaders = []
        subheaders.append(self.setup_sh(header, 'File'))
        subheaders.append(self.setup_sh(header, 'Edit'))
        subheaders.append(self.setup_sh(header, 'View'))
        self.update_idletasks()



    def get_pl_coords(self, lineage):
        """
        :param (list[tk.Widget]) lineage:
        :return:
        """
        self.update()
        x = lineage[-1].winfo_x() + lineage[-1].winfo_width()
        y = lineage[-1].winfo_y() + lineage[-1].winfo_height()
        print(str(x) + ', ' + str(y))
        pad_xs, pad_ys = 0, 0
        return x - pad_xs, y - pad_ys

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
        self.start_dropdown_holder(dropdown, subheader)
        dropdown.focus_force()
        # shd = SubHeader Dropdown
        pop_funcs = {
            'File': self.pop_file_dropdown,
            'Edit': self.pop_edit_dropdown,
            'View': self.pop_view_dropdown
        }
        options = pop_funcs[type_str](dropdown)
        for o in options:
            o.pack(side=tk.TOP)
        # Make sure these go last
        pl_x = subheader.winfo_x() + self.pt_padx
        pl_y = subheader.winfo_y() + subheader.winfo_height() + self.pt_pady
        dropdown.place(x=pl_x, y=pl_y, anchor=tk.NW)
        dropdown.bind('<FocusOut>', lambda e: self.clear_dropdown_holder())
        self.update_idletasks()

############################################################################
    def pop_file_dropdown(self, dropdown):
        dd_new = tk.Label(dropdown, text='New...')
        dd_open = tk.Label(dropdown, text='Open...')
        options = [dd_new, dd_open]
        return options
    def pop_edit_dropdown(self, dropdown):
        dd_mode = tk.Label(dropdown, text='Mode...')
        dd_mode.bind('<Button-1>', lambda e: self.spawn_edit_mode_options(e, dd_mode))
        options = [dd_mode]
        return options
    def pop_view_dropdown(self, dropdown):
        dd_toggle_data_view = tk.Label(dropdown, text='Toggle data display')
        dd_toggle_data_view.bind('<Button-1>', lambda e: self.toggle_data_view())
        options = [dd_toggle_data_view]
        return options
############################################################################

    def spawn_edit_mode_options(self, event, dd_mode):
        """
        :param (tkinter.Label) dd_mode:
        :return:
        """
        options = tk.LabelFrame(self)
        self.setup_edit_mode_readonly(options)
        self.setup_edit_mode_edit_txt(options)
        self.setup_edit_mode_edit_data(options)
        max_wid = 0
        tot_height = 0
        for c in options.winfo_children():
            c.pack(side=tk.TOP, anchor='w')
            max_wid = max(max_wid, c.winfo_width())
            tot_height += c.winfo_height()
        self.update_idletasks()
        pl_x = dd_mode.winfo_rootx() + dd_mode.winfo_width()
        pl_y = dd_mode.winfo_y() + dd_mode.winfo_height() + self.pt_pady
        options.place(x=pl_x, y=pl_y, anchor=tk.NW)
        self.dropdown_holder.append(options)
        # options.bind('<FocusOut', lambda e: )
        self.update_idletasks()
    #

    def set_read_only(self):
        self.widget_paraText.config(state=tk.DISABLED)
        self.clear_dropdown_holder()

    def setup_edit_mode_readonly(self, frame):
        option = tk.Label(frame, text='Read Only')
        option.bind('<Button-1>', lambda e: self.set_read_only())

    def set_edit_text(self):
        self.widget_paraText.config(state=tk.NORMAL)
        self.clear_dropdown_holder()

    def setup_edit_mode_edit_txt(self, frame):
        option = tk.Label(frame, text='Edit Text Only')
        option.bind('<Button-1>', lambda e: self.set_edit_text())

    def set_edit_text_and_date(self):
        self.widget_paraText.config(state=tk.NORMAL)
        self.clear_dropdown_holder()

    def setup_edit_mode_edit_data(self, frame):
        option = tk.Label(frame, text='Edit Text and Data')
        option.bind('<Button-1>', lambda e: self.set_edit_text())

    def toggle_data_view(self):
        self.dataview_bool = not(self.dataview_bool)
        self.setup_dataview()

    def get_paraText_data(self):
        self.widget_paraText.update_child_bounds()
        return self.widget_paraText.directory.items()



    #######
    # def setup_header_bl(self):
    #     header = tk.LabelFrame(self)
    #     header.grid(column=0, row=0, padx=self.pt_padx, pady=self.pt_pady, sticky='w')
    #     lineage = [self, header]
    #     subheaders = []
    #     subheaders.append(self.setup_sh_bl(lineage, 'File'))
    #     subheaders.append(self.setup_sh_bl(lineage, 'Edit'))
    #     subheaders.append(self.setup_sh_bl(lineage, 'View'))
    #     self.update_idletasks()
    #
    # def setup_sh_bl(self, lineage, type_str):
    #     """
    #     :param (list[tk.Widget]) lineage:
    #     :param (str) type_str:
    #     :return (tk.LabelFrame) subheader:
    #     """
    #     # sh = SubHeader
    #     header = lineage[-1]
    #     subheader = tk.Label(header, text=type_str)
    #     subheader.pack(side=tk.LEFT)
    #     new_lineage = lineage + [subheader]
    #     subheader.bind('<Button-1>',
    #                    lambda e: self.spawn_shd_bl(new_lineage,
    #                                             type_str))
    #     return subheader
    #
    # def spawn_shd_bl(self, lineage, type_str):
    #     """
    #     :param (list[tk.Widget]) subheader:
    #     :param (str) type_str:
    #     :return (tk.LabelFrame) dropdown:
    #     """
    #     subheader = lineage[-1]
    #     dropdown = tk.LabelFrame(self)
    #     if not self.dropdown_holder is None:
    #         self.clear_dropdown_holder(self.dropdown_spawner)
    #     dropdown.focus_force()
    #     self.spawner_color = subheader.cget('background')
    #     self.dropdown_spawner = subheader
    #     subheader.config(background=self.hcolor)
    #     # shd = SubHeader Dropdown
    #     pop_funcs = {
    #         'File': self.pop_file_dropdown_bl,
    #         'Edit': self.pop_edit_dropdown_bl,
    #         'View': self.pop_view_dropdown_bl
    #     }
    #     options = pop_funcs[type_str](dropdown)
    #     for o in options:
    #         o.pack(side=tk.TOP)
    #
    #     # Make sure these go last
    #     pl_x, pl_y = self.get_pl_coords(lineage)
    #     dropdown.place(x=pl_x, y=pl_y, anchor=tk.NW)
    #     self.dropdown_holder = dropdown
    #     dropdown.bind('<Button-1>', lambda e: print(e))
    #     dropdown.bind('<FocusOut>', lambda e: self.clear_dropdown_holder(subheader))
    #     self.update_idletasks()

    # def spawn_edit_mode_options_bl(self, event, lineage):
    #     """
    #     :param (tkinter.Label) dd_mode:
    #     :return:
    #     """
    #     dd_mode = lineage[-1]
    #     options = tk.LabelFrame(self)
    #     self.setup_edit_mode_readonly(options)
    #     self.setup_edit_mode_edit_txt(options)
    #     self.setup_edit_mode_edit_data(options)
    #     max_wid = 0
    #     tot_height = 0
    #     for c in options.winfo_children():
    #         c.pack(side=tk.TOP, anchor='w')
    #         # c.config(anchor='w')
    #         max_wid = max(max_wid, c.winfo_width())
    #         tot_height += c.winfo_height()
    #     # options.config(width=(max_wid + 10))
    #     self.update_idletasks()
    #     topdawg = dd_mode.winfo_parent()
    #     pl_x = topdawg.winfo_x() + dd_mode.winfo_x() + self.pt_padx
    #     pl_y = topdawg.winfo_y() + dd_mode.winfo_y() + dd_mode.winfo_height() + self.pt_pady
    #     # pl_x = dd_mode.winfo_rootx()
    #     # pl_y = dd_mode.winfo_rooty()
    #     options.place(x=pl_x, y=pl_y, anchor=tk.NW)
    #     self.update_idletasks()


# TODO
