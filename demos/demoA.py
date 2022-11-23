import tkinter as tk
import os
import sys
import time
mainpath = os.path.join(os.path.dirname(__file__), '../')
sys.path.append(mainpath)
from classes import paraText

root = tk.Tk()
root.geometry("440x100")
root.title('testA')
synonyms = ['concise', 'terse']
rephrasings = ["However I want to be super duper wordy.", "Except I love the sound of my own voice.", "But I gotta say what I gotta say."]

myText = paraText.paraText()
myText.insert('1.0', 'I will be concise. I want to be concise. I hope to one day be concise.' + rephrasings[0])
myText.grid(column=0, row=0, padx=5, pady=5)


myText.add_tag_rep(synonyms[0], synonyms, sync=myText.syncTrue)
myText.add_tag_rep(rephrasings[0], rephrasings, sync=myText.syncFalse)
myText.config(state=tk.DISABLED)
"""
    serial - serial number of event
    num - mouse button pressed (ButtonPress, ButtonRelease)
    focus - whether the window has the focus (Enter, Leave)
    height - height of the exposed window (Configure, Expose)
    width - width of the exposed window (Configure, Expose)
    keycode - keycode of the pressed key (KeyPress, KeyRelease)
    state - state of the event as a number (ButtonPress, ButtonRelease,
                            Enter, KeyPress, KeyRelease,
                            Leave, Motion)
    state - state as a string (Visibility)
    time - when the event occurred
    x - x-position of the mouse
    y - y-position of the mouse
    x_root - x-position of the mouse on the screen
             (ButtonPress, ButtonRelease, KeyPress, KeyRelease, Motion)
    y_root - y-position of the mouse on the screen
             (ButtonPress, ButtonRelease, KeyPress, KeyRelease, Motion)
    char - pressed character (KeyPress, KeyRelease)
    send_event - see X/Windows documentation
    keysym - keysym of the event as a string (KeyPress, KeyRelease)
    keysym_num - keysym of the event as a number (KeyPress, KeyRelease)
    type - type of the event as a number
    widget - widget in which the event occurred
    delta - delta of wheel movement (MouseWheel)"""

def lookat_e(e):
    event = e.__repr__()
    items = e.__dict__.items()
    # myvars = vars()
    # for item in items:
    #     var_name = "myvar_" + str(item[0])
    #     myvars.__setitem__(var_name, item[1])
    #     print(eval(var_name))
    # print(myvars)
    new_event = tk.Event()
    for item in items:
        new_event.__setattr__(item[0], item[1])
    print(e)
    print(new_event)

# def duplicate_event(e):
#     items = e.__dict__.items()

    # myvars = vars()
    # toeval = "toprint"
    # myvars.__setitem__(toeval, "printed")
    # print(myvars)
    # print("{}".format(eval(toeval)))

    # print(e)
    # print(e.serial)
    # print(e.num)
    # print(e.focus)
    # print(e.height)
    # print(e.width)
    # print(e.keycode)
    # print(e.state)
    # print(e.time)
    # print(e.x)
    # print(e.y)
    # print(e.x_root)
    # print(e.y_root)
    # print(e.char)
    # print(e.send_event)
    # print(e.keysym)
    # print(e.keysym_num)
    # print(e.type)
    # print(e.widget)
    # print(e.delta)

myText.bind('<Button-1>', lambda e: lookat_e(e))


root.mainloop()
