import tkinter as tk
from classes import paraText, paraTxt, editor
from libs import utils, cosmetic

class family_creator(tk.Toplevel):
    fam_name = None
    options = []

    def __init__(self, spawner):
        self.s = spawner
        super().__init__(spawner)
        selection = self.s.w_pT.get(tk.SEL_FIRST, tk.SEL_LAST)
        # Shows the current selected text
        self.sel_label = cosmetic.grid_title(self, selection, 0, 0)
        # Choose family name? Button
        self.fam_button = tk.Button(self, text='Choose family name?')
        self.fam_button.grid(row=1, column=0)
        # Add all instances of "(selected string)"? Button
        self.rep_init_button = tk.Button(self,
                                    text='Add all instances of \"' + selection + '\" to family?')
        self.rep_init_button.grid(row=2, column=0)
        # Prepare different options for new family somehow
        # Fill-out text box with an "Add" button next to it
        # Display all added options underneath this text box
        # All added options should have an "Edit" button and a "Delete" button next to them
        # "Okay" button
        # Will scan given options and ask if all instances of each option
        # should also be added the family

    def add_family_popup_options_handler(self, popup, x_0, y_0):
        entry_box = tk.Entry(popup)
        entry_box.grid(row=y_0, column=x_0)
        add_button = tk.Button(popup, text="Add")
        add_button.grid(row = y_0, column = x_0 + 1)
        options = []