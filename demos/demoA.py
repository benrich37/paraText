import tkinter as tk
from tkinter import ttk
from libs import utils
import sys
import copy
import time
from classes import paraText

root = tk.Tk()
root.geometry("440x100")
root.title('testA')
synonyms = ['concise', 'terse']
rephrasings = ["However I want to be super duper wordy.", "Except I love the sound of my own voice.", "But I gotta say what I gotta say."]

myText = paraText.paraText()
myText.insert('1.0', 'I will be concise. I want to be concise. I hope to one day be concise. ' + rephrasings[0])
myText.grid(column=0, row=0, padx=5, pady=5)


myText.add_tag_rep(synonyms[0], synonyms, sync=myText.syncTrue)
myText.add_tag_rep(rephrasings[0], rephrasings, sync=myText.syncFalse)
# myText.config(state=tk.DISABLED)

root.mainloop()
import math
# print(hex(math.floor(23.6)))
# print(utils.get_hex(23.3))
# hexcolor = "#FF9D3B"
# print(utils.short_hex_alpha_to_dec_alpha("12"))

# ex_list = ["dfsg", "weqfgd", "efr"]
# for i, j in enumerate(ex_list):
#     print(i)
#     print(j)