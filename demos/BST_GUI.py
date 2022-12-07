import tkinter as tk
import tkinter.font as tkFont
from BSTTree import *

def opening_file(filename, compiled_list):
    boolean_var = True
    f = open(filename, 'r')
    while boolean_var:
        fname = f.readline().split(',')
        if not fname[0]:
            boolean_var = False
        else:
            compiled_list.append(fname) 
    return compiled_list 
                
#Remove the new line character and return back a list 
#Next extract the first element 
#Finally extract all the other elements and move them to a list 
def remove_newline(list_of_names):
    #Remove the '\n' delimeter 
    for count,element in enumerate(list_of_names):
        for newcount, subelement in enumerate(list_of_names[count]):
            list_of_names[count] = [i.strip() for i in list_of_names[count]]
    return list_of_names

if __name__ == '__main__':

    root= tk.Tk()

    canvas1 = tk.Canvas(root, width=400, height=300)
    canvas1.pack()
    
    words = ["chili","amazing"]
    underline = b'\xcc\xb2'
    underline_word = str(underline, 'utf-8')
    word_list = [ "\u0332".join("chili"),"\u0332".join("amazing")]

    main_label = tk.Label(root, text="The {} from this place is {}".format(*word_list)) 
    #f = tkFont.Font(main_label, main_label.cget("font"))
    #f.configure(underline = True)
    #main_label.configure(font=f)       
    canvas1.create_window(200, 100, window=main_label)

    list_of_names = []
    list_of_names = opening_file('words2.txt',list_of_names)
    remove_newline(list_of_names) 
    print(list_of_names) 

    dictionary = {}
    just_keys = []
    for lst in list_of_names:
        key = lst[0]
        just_keys.append(key)
        value = lst[1:]
        dictionary[key] = value
    #print(just_keys)

    createTree = BST()
    for key, val in dictionary.items():
        createTree.insert(key, val)

    entry1 = tk.Entry(root) 
    canvas1.create_window(200, 140, window=entry1)

    def check(entry):
        if createTree.search(entry) is not None:
            synonyms = createTree.search(entry)      
        word = entry1.get()
        print (synonyms)
        return "\n".join(synonyms)
        #label1.config(text="\n".join(synonyms))

    def get_syn(): 
        word = entry1.get()
        print (just_keys)
        display = 'Try again!'
        for entry in just_keys:
            if entry == word:
                #label1 = tk.Label(root)
                display = check(entry)
                #canvas1.create_window(200, 230, window=label1)
                      
        print (canvas1.master.children)
        
        childern  = canvas1.master.children
        last_child = list(childern.keys())[-1]
        if  last_child.startswith("!label"):
            childern[last_child].destroy()
        #print (canvas1.master.__dict__)
        #print (dir(canvas1.master))
        label2 = tk.Label(root, text=display)
        canvas1.create_window(200,230, window=label2)
        canvas1.delete('1.0',tk.END)

    #Put the parent inside tk.Button() otherwise you get TCL error !button not found 
    button1 = tk.Button(root, text='Get the synonym', command=get_syn)
    canvas1.create_window(200, 180, window=button1)

    root.mainloop()
