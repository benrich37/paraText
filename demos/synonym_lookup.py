"""Look up synonyms stored in a BST, loaded from demos/data/words.txt.

Each line of the word file is ``word, synonym1, synonym2, ...``.
"""

import tkinter as tk
from pathlib import Path

from paratext.bst import BST

WORDS_FILE = Path(__file__).parent / "data" / "words.txt"


def load_synonyms(path=WORDS_FILE) -> BST:
    tree = BST()
    for line in Path(path).read_text().splitlines():
        entries = [e.strip() for e in line.split(",") if e.strip()]
        if entries:
            tree.insert(entries[0], entries[1:])
    return tree


def main():
    tree = load_synonyms()
    root = tk.Tk()
    root.title("Synonym lookup")
    known = ", ".join(key for key, _ in tree.inorder())
    tk.Label(root, text=f"Known words: {known}").pack(padx=20, pady=(20, 5))
    entry = tk.Entry(root)
    entry.pack(padx=20, pady=5)
    result = tk.Label(root, text="", justify=tk.LEFT)

    def get_syn(event=None):
        word = entry.get().strip()
        result.config(text="\n".join(tree.search(word)) if word in tree else "Try again!")

    entry.bind("<Return>", get_syn)
    tk.Button(root, text="Get the synonym", command=get_syn).pack(padx=20, pady=5)
    result.pack(padx=20, pady=(5, 20))
    root.mainloop()


if __name__ == "__main__":
    main()
