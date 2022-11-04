import tkinter as tk
import os
import sys
import unittest
mainpath = os.path.join(os.path.dirname(__file__), '../../')
sys.path.append(mainpath)
from classes import paraText

class TestUtils(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ex = paraText.paraText()

    def testnothing(self):
        self.assertTrue(True)

if __name__ == '__main__':
    unittest.main()