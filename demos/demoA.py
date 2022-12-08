import tkinter as tk
import os
import sys
mainpath = os.path.join(os.path.dirname(__file__), '../')
sys.path.append(mainpath)
from classes import paraText

root = tk.Tk()
root.geometry("600x350")
root.title('Demo A')
synonyms = ['concise', 'terse']
rephrasings = ["However I want to be super duper wordy.",
               "Except I love the sound of my own voice.",
               "But I gotta say what I gotta say."]

myText = paraText.paraText(wrap=tk.WORD, font=("Arial", 25), width=40,
                           border=0)
myText.insert('1.0', ' I will be concise. I want to be concise.'
                     ' I hope to one day be concise. ' + rephrasings[0])
myText.grid(column=0, row=0, padx=24, pady=40)

myText.add_tag_rep(synonyms[0], synonyms, sync=myText.syncTrue)
myText.add_tag_rep(rephrasings[0], rephrasings, sync=myText.syncFalse)
myText.config(state=tk.DISABLED)


root.mainloop()
