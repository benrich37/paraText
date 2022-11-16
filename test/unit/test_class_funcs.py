import tkinter as tk
import _tkinter
import os
import sys
import unittest
mainpath = os.path.join(os.path.dirname(__file__), '../../')
sys.path.append(mainpath)
from classes import paraText

# Follow this https://stackoverflow.com/questions/4083796/how-do-i-run-unittest-on-a-tkinter-app

class TKinterTestCase(unittest.TestCase):
    """These methods are going to be the same for every GUI test,
    so refactored them into a separate class
    """
    def setUp(self):
        self.root=tk.Tk()
        self.root.geometry("440x100")
        self.root.title('Test')
        self.synonyms = ['concise', 'terse']
        self.ex = paraText.paraText()
        self.ex.insert('1.0', 'I will be concise. I want to be concise. I hope to one day be concise. ')
        self.ex.grid(column=0, row=0, padx=5, pady=5)
        self.pump_events()

    def tearDown(self):
        if self.root:
            self.root.destroy()
            self.pump_events()

    def pump_events(self):
        while self.root.dooneevent(_tkinter.ALL_EVENTS | _tkinter.DONT_WAIT):
            pass

class TestClassFuncs(TKinterTestCase):
    def test_nothing(self):
        self.assertTrue(True)

    def test_parent_rep_id(self):
        pattern = "test"
        expected = self.ex.repFlag + pattern
        output = self.ex.parent_rep_id(pattern)
        self.assertEqual(expected, output)

    def test_interp_sync_arg(self):
        self.assertEqual(self.ex.interp_sync_arg(None), self.ex.default_sync)
        self.assertEqual(self.ex.interp_sync_arg(True), self.ex.syncTrue)
        self.assertEqual(self.ex.interp_sync_arg(False), self.ex.syncFalse)

    def test_append_options(self):
        pattern = self.synonyms[0]
        parent_tag = self.ex.parent_rep_id(pattern)
        opt_list = self.synonyms
        # Should raise key error before option list is added to the system
        self.assertRaises(KeyError, lambda: self.ex.replace_tags[parent_tag])
        self.ex.append_options(parent_tag, opt_list)
        # length of option list should match length of provided option list
        self.assertEqual(len(opt_list), len(self.ex.replace_tags[parent_tag]))
        # Making sure all options got added
        for o in opt_list:
            self.assertTrue(o in self.ex.replace_tags[parent_tag])
        self.ex.append_options(parent_tag, opt_list)
        # Making sure options only appear once
        for o in opt_list:
            self.assertEqual(self.ex.replace_tags[parent_tag].count(o), 1)


    # def test_get_init_rep_id(self):


    def test_Add_Tag_Rep(self):
        self.ex.add_tag_rep(self.synonyms[0], self.synonyms, sync=self.ex.syncTrue)

if __name__ == '__main__':
    unittest.main()