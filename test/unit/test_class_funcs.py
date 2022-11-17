import tkinter as tk
import _tkinter
import os
import sys
import unittest
mainpath = os.path.join(os.path.dirname(__file__), '../../')
sys.path.append(mainpath)
from classes import paraText
from libs import utils

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

    def test_get_parent_rep_tag(self):
        pattern = "test"
        expected = self.ex.repFlag + pattern
        output = self.ex.get_parent_rep_tag(pattern)
        self.assertEqual(expected, output)

    def test_get_child_rep_tag(self):
        idx = 1
        sync = True
        pattern = self.synonyms[0]
        expected = self.ex.repFlag + str(idx) + self.ex.repIdFlag + str(sync) + self.ex.syncFlag + pattern
        self.assertEqual(expected, self.ex.get_child_rep_tag(idx, sync, pattern))
        self.assertEqual(expected, self.ex.get_child_rep_tag(str(idx), str(sync), pattern))

    def test_parse_child_rep_tag(self):
        idx = 1
        sync = True
        pattern = self.synonyms[0]
        child_rep_tag = self.ex.get_child_rep_tag(idx, sync, pattern)
        output = self.ex.parse_child_rep_tag(child_rep_tag)
        self.assertEqual(output[0], idx)
        self.assertEqual(output[1], str(sync))
        self.assertEqual(output[2], pattern)

    def test_interp_sync_arg(self):
        self.assertEqual(self.ex.interp_sync_arg(None), self.ex.default_sync)
        self.assertEqual(self.ex.interp_sync_arg(True), self.ex.syncTrue)
        self.assertEqual(self.ex.interp_sync_arg(False), self.ex.syncFalse)

    def test_append_options(self):
        pattern = self.synonyms[0]
        parent_tag = self.ex.get_parent_rep_tag(pattern)
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

    def test_get_init_rep_id(self):
        pattern = self.synonyms[0]
        parent_tag = self.ex.get_parent_rep_tag(pattern)
        opt_list = self.synonyms
        self.assertEqual(0, self.ex.get_init_rep_id(pattern))
        self.ex.add_tag_rep(pattern, opt_list)
        self.assertEqual(len(self.ex.rep_replace_tags[parent_tag]) , self.ex.get_init_rep_id(pattern))

    def test_get_last_rep_id(self):
        pattern = self.synonyms[0]
        parent_tag = self.ex.get_parent_rep_tag(pattern)
        opt_list = self.synonyms
        self.assertEqual(0, self.ex.get_init_rep_id(pattern))
        self.ex.add_tag_rep(pattern, opt_list)
        self.assertEqual(len(self.ex.rep_replace_tags[parent_tag]) - 1, self.ex.get_last_rep_id(pattern))


    def test_setup_rep_bind_tag_attacker(self):
        #### SETUP ####

        pattern = self.synonyms[0]
        opt_list = self.synonyms
        parent_tag = self.ex.get_parent_rep_tag(pattern)
        synctag = "True"
        self.ex.append_options(parent_tag, opt_list)
        matches = utils.return_matches(self.ex, pattern)
        for i in range(len(matches)):
            ctag_i = self.ex.get_child_rep_tag(0 + i,
                                            synctag,
                                            pattern)
            self.ex.append_child_tags(parent_tag, ctag_i)
            bound1 = matches[i]
            bound2 = utils.add_to_char_idx(matches[i], len(pattern))
            self.ex.tag_add(ctag_i,
                         bound1,
                         bound2
                         )
        attacker_tags = self.ex.rep_replace_tags[parent_tag]
        attacker_tag = attacker_tags[0]
        ####
        # Make sure the most recently added widget is the paraText widget itself
        self.assertEqual(self.root.winfo_children()[-1].winfo_class(), self.ex.winfo_class())
        self.ex.setup_rep_bind_tag_attacker(attacker_tag, attacker_tag, parent_tag)
        self.ex.update_idletasks()
        # get coordinates of where this was created
        bounds = self.ex.tag_ranges(attacker_tag)
        coords = self.ex.bbox(bounds[0])
        # ESSENTIAL!!! There must be motion event on text with bound events before they can trigger
        self.ex.event_generate('<Motion>', x=coords[0], y=coords[1])
        self.ex.event_generate('<Button-2>', x=coords[0], y=coords[1])
        self.ex.event_generate('<ButtonRelease-2>', x=coords[0], y=coords[1])
        option_list = self.root.winfo_children()[1]
        # Most recently created widget should be a TFrame
        self.assertEqual(option_list.winfo_class(), 'TFrame')





    def test_Add_Tag_Rep(self):
        self.ex.add_tag_rep(self.synonyms[0], self.synonyms, sync=self.ex.syncTrue)

if __name__ == '__main__':
    unittest.main()