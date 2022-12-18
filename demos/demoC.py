# This one will be for testing out the super class paraTxt

import tkinter as tk
#import Tkinter
import os
import sys
mainpath = os.path.join(os.path.dirname(__file__), '../')
sys.path.append(mainpath)
from classes import paraTxt

synonyms = ['concise', 'terse']
test = paraTxt.paraTxt()
test.widget_paraText.insert('1.0', ' I will be concise. I want to be concise. I hope to one day be concise.')
test.widget_paraText.add_tag_rep(synonyms[0], synonyms, sync='True')
test.widget_paraText.config(state=tk.DISABLED)

test.mainloop()