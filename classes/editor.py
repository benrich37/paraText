import tkinter as tk
from classes import paraText, paraTxt

class editor(tk.Toplevel):
    fam_labels = []
    def_bgs = {}

    def __init__(self, spawner, mode=0):
        """
        :param (paraTxt.paraTxt) spawner:
        """
        self.s = spawner
        super().__init__(spawner)
        self.geometry('700x200')
        self.title('Editor')
        self.write_current_backgrounds()
        self.family_gridder(self, mode=mode)

    def write_current_backgrounds(self):
        ref = self.s.w_pT.directory.items()
        for p in ref:
            for c in p[1][1]:
                self.def_bgs[c] = self.s.w_pT.tag_cget(c,
                                                       option='background')

    def grid_msg(self, master, textvar, x0, xw, y0, yw):
        tk.Label(master,
                 textvariable=textvar).grid(row=y0,
                                            rowspan=yw,
                                            column=x0,
                                            columnspan=xw)

    def grid_label(self, master, text, row, column):
        ret_label = tk.Label(master,
                        text=text,
                        borderwidth=1,
                        relief='solid')
        ret_label.grid(row=row, column=column)
        return ret_label

    def grid_title(self, master, text, row, column):
        tk.Label(master,
                 text=text).grid(row=row,
                                 column=column)

    def grid_block(self, master, x0, xw, y0, yw, color):
        tk.Label(master,
                 text='.'*2500,
                 background=color,
                 highlightbackground=color,
                 height=1,
                 font=("Arial", 1)).grid(row=y0,
                                         rowspan=yw,
                                         column=x0,
                                         columnspan=xw)

    def fam_grid_mode_msg(self, mode):
        mode_dict = {
            0: 'View Only',
            1: 'Choose family to append selection',
            2: 'Create new family',
            3: 'Edit existing families'
        }
        return tk.StringVar(self, value=mode_dict[mode])

    def highlight_child(self, tagname, color):
        self.s.w_pT.tag_configure(tagName=tagname,
                                  background=color)

    def reset_highlight(self, tagname):
        self.s.w_pT.tag_configure(tagName=tagname,
                                  background=self.def_bgs[tagname])

    def reset_family_highlight(self, family_name):
        child_tags = self.s.w_pT.directory[family_name][1]
        for i in range(len(child_tags)):
            self.reset_highlight(child_tags[i])

    def highlight_family(self, family_name, color, option=None):
        child_tags = self.s.w_pT.directory[family_name][1]
        if option is not None:
            child_texts = self.s.w_pT.directory[family_name][3]
            for i in range(len(child_tags)):
                if child_texts[i] == option:
                    self.highlight_child(child_tags[i], color)
        else:
            for i in range(len(child_tags)):
                self.highlight_child(child_tags[i], color)



    def bind_label_parent(self, label, mode):
        """
        :param (tkinter.Label) label:
        :param (int) mode:
        :return:
        """
        label.bind('<Enter>', lambda e: self.highlight_family(label.cget('text'),
                                                              self.s.w_pT.sel_click_color))
        label.bind('<Leave>',
                   lambda e: self.reset_family_highlight(label.cget('text')))
    # All: Hover: highlight instances,
    # All: clear existing binds
    # 1: Button1: Append current selection to family
    # 2: n/a
    # 3: Button1: Edit family name, option to delete
    def bind_label_option(self, label, mode, fam_name):
        """
        :param (tkinter.Label) label:
        :param (int) mode:
        :return:
        """
        label.bind('<Enter>',
                   lambda e: self.highlight_family(fam_name,
                                                   self.s.w_pT.sel_click_color,
                                                   option=label.cget('text')))
        label.bind('<Leave>',
                   lambda e: self.reset_family_highlight(fam_name))
    # All: Hover: highlight instances,
    # All: clear existing binds
    # 1: n/a
    # 2: Button1: Copy option to new family?
    # 3: Button1: Edit option, option to delete
    def bind_label_child(self, label, mode):
        """
        :param (tkinter.Label) label:
        :param (int) mode:
        :return:
        """
        label.bind('<Enter>',
                   lambda e: self.highlight_child(label.cget('text'),
                                                  self.s.w_pT.sel_click_color))
        label.bind('<Leave>',
                   lambda e: self.reset_highlight(label.cget('text')))
    #### Binds labels for child tag and child bounds
    # All: Hover: highlight instances,
    # All: clear existing binds
    # 1: n/a
    # 2: Button1: Change family association to new family
    # 3: Button1: Change family association, option to delete all association



    def add_family_popup(self):
        return None
    # Shows the current selected text
    # Choose family name? Button
    # Add all instances of "(selected string)"? Button
    # Prepare different options for new family somehow
        # Fill-out text box with an "Add" button next to it
        # Display all added options underneath this text box
        # All added options should have an "Edit" button and a "Delete" button next to them
    # "Okay" button
        # Will scan given options and ask if all instances of each option
        # should also be added the family


    def family_gridder(self, window, mode=0):
        offx = 0
        offy = 3
        mode_strvar = self.fam_grid_mode_msg(mode)
        self.grid_msg(window, mode_strvar, 0, 4 + offx, 0, 1)
        self.grid_title(window, 'Family name', 1, 0 + offx)
        self.grid_title(window, 'Options', 1, 1 + offx)
        self.grid_title(window, 'Existing Children', 1, 2 + offx)
        self.grid_title(window, 'Children Bounds', 1, 3 + offx)
        self.grid_block(window, 0, 4 + offx, 2, 1, 'black')
        self.s.w_pT.update_directory()
        pr = 0
        for p in self.s.w_pT.directory.items():
            # Family label
            fam_label = self.grid_label(window, p[0], pr + offy, 0 + offx)
            self.bind_label_parent(fam_label, mode)
            # option labels
            for i in range(len(p[1][0])):
                op_i = self.grid_label(window, p[1][0][i], pr + i + offy, 1 + offx)
                self.bind_label_option(op_i, mode, p[0])
            # Children labels
            for i in range(len(p[1][1])):
                child_i = self.grid_label(window, p[1][1][i], pr + i + offy, 2 + offx)
                self.bind_label_child(child_i, mode)
            # Children bounds
            for i in range(len(p[1][2])):
                self.grid_label(window, p[1][2][i], pr + i + offy, 3 + offx)
            # Find how many rows the family is occupying before starting next one
            row_max = 0
            for i in range(3):
                row_max = max(row_max, len(p[1][i]))
            pr += row_max