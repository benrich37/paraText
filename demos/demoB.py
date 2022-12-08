import tkinter as tk
import os
import sys
mainpath = os.path.join(os.path.dirname(__file__), '../')
sys.path.append(mainpath)
from classes import paraText
from libs.utils import ints_to_char_idx as car

root = tk.Tk()
root.geometry("600x350")
root.title('Demo B')
myText = paraText.paraText(wrap=tk.WORD, font=("Arial", 25), width=40,
                           border=0)

belongings = ['Buffalo',
              'Buffaloian',
              'New-york based']
namings = ['buffalo',
           'creatures',
           'discount bison']
verbs = ['buffalo', 'confuse', 'bully']
s = ' '

bl = len(namings[0])
text = belongings[0] + s\
       + namings[0] + s\
       + belongings[0] + s\
       + namings[0] + s\
       + verbs[0] + s\
       + verbs[0] + s\
       + belongings[0] + s\
       + namings[0] + '.'
belongings_idcs = [car(1,(bl * 0) + 0), car(1,(bl * 1) + 0),
                   car(1, (bl * 2) + 2), car(1, (bl * 3) + 2),
                   car(1, (bl * 6) + 6), car(1, (bl * 7) + 6)]
namings_idcs = [car(1, (bl * 1) + 1), car(1, (bl * 2) + 1),
                car(1, (bl * 3) + 3), car(1, (bl * 4) + 3),
                car(1, (bl * 7) + 7), car(1, (bl * 8) + 7)]
verbs_idcs = [car(1, (bl * 4) + 4), car(1, (bl * 5) + 4),
              car(1, (bl * 5) + 5), car(1, (bl * 6) + 5)]
myText.insert('1.0', text)
myText.add_tag_idcs(belongings_idcs, belongings, name='Belongings', sync=True)
myText.add_tag_idcs(namings_idcs, namings, name='Namings', sync=True)
myText.add_tag_idcs(verbs_idcs, verbs, name='Verbs', sync=True)


myText.grid(column=0, row=0, padx=20, pady=40)
myText.config(state=tk.DISABLED)
root.mainloop()