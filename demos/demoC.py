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
test.w_pT.insert('1.0', ' I will be concise. I want to be concise. I hope to one day be concise.')
test.w_pT.add_tag_rep(synonyms[0], synonyms, sync='True')
test.w_pT.config(state=tk.DISABLED)

test.mainloop()