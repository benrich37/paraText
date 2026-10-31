"""Demo B: tag explicit index ranges with add_tag_idcs.

"Buffalo buffalo Buffalo buffalo buffalo buffalo Buffalo buffalo." has three
word senses (place, animal, verb); each sense gets its own option list.
"""

import tkinter as tk

from paratext.textutils import ints_to_char_idx as car
from paratext.widget import ParaText

root = tk.Tk()
root.geometry("600x350")
root.title("Demo B")
my_text = ParaText(root, wrap=tk.WORD, font=("Arial", 25), width=40, border=0)

belongings = ["Buffalo", "Buffaloian", "New-york based"]
namings = ["buffalo", "creatures", "discount bison"]
verbs = ["buffalo", "confuse", "bully"]

words = [belongings[0], namings[0], belongings[0], namings[0], verbs[0], verbs[0], belongings[0], namings[0]]
text = " ".join(words) + "."
bl = len(namings[0])  # every word above is 7 characters long


def span(i):
    """(start, end) indices of the i-th word."""
    return [car(1, i * (bl + 1)), car(1, i * (bl + 1) + bl)]


my_text.insert("1.0", text)
my_text.add_tag_idcs(span(0) + span(2) + span(6), belongings, name="Belongings", sync=True)
my_text.add_tag_idcs(span(1) + span(3) + span(7), namings, name="Namings", sync=True)
my_text.add_tag_idcs(span(4) + span(5), verbs, name="Verbs", sync=True)

my_text.grid(column=0, row=0, padx=20, pady=40)
my_text.config(state=tk.DISABLED)
root.mainloop()
