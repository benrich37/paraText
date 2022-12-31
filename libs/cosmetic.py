import tkinter as tk


def grid_label(master, text, row, column):
    ret_label = tk.Label(master,
                         text=text,
                         borderwidth=1,
                         relief='solid')
    ret_label.grid(row=row, column=column)
    return ret_label

def grid_msg(master, textvar, x0, xw, y0, yw):
    ret_label = tk.Label(master,
                         textvariable=textvar)
    ret_label.grid(row=y0, rowspan=yw, column=x0, columnspan=xw)
    return ret_label


def grid_title(master, text, row, column):
    ret_label = tk.Label(master, text=text, font=("Arial", 20))
    ret_label.grid(row=row,column=column)
    return ret_label

def grid_block(master, x0, xw, y0, yw, color):
    ret_label = tk.Label(master,
                 text='.'*2500,
                 background=color,
                 highlightbackground=color,
                 height=1,
                 font=("Arial", 1))
    ret_label.grid(row=y0, rowspan=yw, column=x0, columnspan=xw)
    return ret_label