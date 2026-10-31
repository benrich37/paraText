"""Demo A: tag every occurrence of a pattern with add_tag_rep.

Right-click an underlined span for replacement options; shift-left-click to
toggle whether it is synced (red) or unsynced (yellow) with its siblings.
"""

import tkinter as tk

from paratext.widget import ParaText

root = tk.Tk()
root.geometry("600x350")
root.title("Demo A")
synonyms = ["concise", "terse"]
rephrasings = [
    "However I want to be super duper wordy.",
    "Except I love the sound of my own voice.",
    "But I gotta say what I gotta say.",
]

my_text = ParaText(root, wrap=tk.WORD, font=("Arial", 25), width=40, border=0)
my_text.insert("1.0", " I will be concise. I want to be concise. I hope to one day be concise. " + rephrasings[0])
my_text.grid(column=0, row=0, padx=24, pady=40)

my_text.add_tag_rep(synonyms[0], synonyms, sync=my_text.syncTrue)
my_text.add_tag_rep(rephrasings[0], rephrasings, sync=my_text.syncFalse)
my_text.config(state=tk.DISABLED)

root.mainloop()
