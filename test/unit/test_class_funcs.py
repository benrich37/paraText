import tkinter as tk
import os
import sys
import unittest
mainpath = os.path.join(os.path.dirname(__file__), '../../')
sys.path.append(mainpath)
from classes import paraText

# Follow this https://stackoverflow.com/questions/4083796/how-do-i-run-unittest-on-a-tkinter-app

class TestUtils(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ex = paraText.paraText()

    def setUp(self):
        self.root = tk.Tk()

    def tearDown(self):
        self.root.destroy()

    def testnothing(self):
        self.assertTrue(True)

if __name__ == '__main__':
    unittest.main()