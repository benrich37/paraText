import tkinter as tk
from tkinter import ttk
import _tkinter
import os
import sys
import unittest
mainpath = os.path.join(os.path.dirname(__file__), '../../')
sys.path.append(mainpath)
from classes import paraText
from libs import utils
from libs import event_gen
import time

# Follow this https://stackoverflow.com/questions/4083796/how-do-i-run-unittest-on-a-tkinter-app

def save_items(root, e):
    items = e.__dict__.items()
    root.ex_event = tk.Event()
    for item in items:
        root.ex_event.__setattr__(item[0], item[1])


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
        self.sample_line = 'abcdefghijklmnopqrstuvwxyz'
        self.ex_phrase_concise = 'I will be concise. I want to be concise. I hope to one day be concise.'
        self.ex_phrase_terse = 'I will be terse. I want to be terse. I hope to one day be terse.'
        self.ex.insert('1.0', self.ex_phrase_concise + '\n')
        self.ex.insert('2.0', self.sample_line)
        # self.ex.insert('3.0', self.sample_line)
        # self.ex.insert('4.0', self.sample_line)
        self.ex.grid(column=0, row=0, padx=5, pady=5)
        self.pump_events()

        self.ex.bind('<Button-1>', lambda e: save_items(self, e))
        event_gen.left_click_coord(self.ex, tuple([0,0,0,0]))
        self.ex.unbind('<Button-1>')

        self.sample_iso = "_ISO_foobar"
        self.sample_parent = "_REP_foobar"
        self.sample_rep_s1 = "_REP_1_CNT_True_SNC_foobar"
        self.sample_rep_u1 = "_REP_1_CNT_False_SNC_foobar"
        self.sample_rep_s2 = "_REP_2_CNT_True_SNC_foobar"
        self.sample_rep_u2 = "_REP_2_CNT_False_SNC_foobar"

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

    def test_clear_widget_holder(self):
        self.assertEqual(len(self.ex.winfo_children()), 0)
        self.ex.widget_holder = tk.Label(master=self.ex)
        self.assertEqual(len(self.ex.winfo_children()), 1)
        self.ex.clear_widget_holder()
        self.assertEqual(len(self.ex.winfo_children()), 0)

    def test_get_replace_type(self):
        sample_tags = [self.sample_iso, self.sample_rep_s1, self.sample_rep_u1]
        expected_returns = [self.ex.replace_types[0],
                            self.ex.replace_types[1],
                            self.ex.replace_types[2]]
        for i in range(len(sample_tags)):
            self.assertEqual(self.ex.get_replace_type(sample_tags[i]),
                             expected_returns[i])

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

    def test_get_synced_tags(self):
        self.assertEqual(self.ex.get_synced_tags([]), [])
        self.assertListEqual(self.ex.get_synced_tags([self.sample_rep_s1, self.sample_rep_s1]),
                             [self.sample_rep_s1, self.sample_rep_s1])
        self.assertListEqual(self.ex.get_synced_tags([self.sample_rep_u1, self.sample_rep_s1]),
                             [self.sample_rep_s1])
        self.assertListEqual(self.ex.get_synced_tags([self.sample_rep_s1, self.sample_rep_u1]),
                             [self.sample_rep_s1])
        self.assertListEqual(self.ex.get_synced_tags([self.sample_rep_u1, self.sample_rep_u1]),
                             [])

    def test_change_child_tag_sync_flag(self):
        self.ex.tag_add(self.sample_rep_s1, "1.0", "1.5")
        self.ex.append_child_tags(self.sample_parent, self.sample_rep_s1)
        self.assertEqual(self.ex.rep_replace_tags[self.sample_parent][0], self.sample_rep_s1)
        self.ex.change_child_tag_sync_flag(self.sample_rep_s1, self.ex.syncFalse, self.sample_parent)
        self.assertEqual(self.ex.rep_replace_tags[self.sample_parent][0], self.sample_rep_u1)


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

    def test_append_child_tags(self):
        self.assertRaises(KeyError, lambda: self.ex.rep_replace_tags[self.sample_parent])
        self.ex.append_child_tags(self.sample_parent, self.sample_rep_s1)
        self.assertListEqual(self.ex.rep_replace_tags[self.sample_parent], [self.sample_rep_s1])
        self.ex.append_child_tags(self.sample_parent, self.sample_rep_s1)
        self.assertListEqual(self.ex.rep_replace_tags[self.sample_parent], [self.sample_rep_s1])
        self.ex.append_child_tags(self.sample_parent, self.sample_rep_u1)
        self.assertListEqual(self.ex.rep_replace_tags[self.sample_parent], [self.sample_rep_s1,
                                                                            self.sample_rep_u1])

    def test_setup_rep_bind_tag_attacker(self):
        """
        This test function is obviously too long, I'm just gonna go through and test
        as much as possible than figure out how we can generalize it
        """
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


        self.ex.setup_rep_bind_tag(parent_tag)
        self.ex.update_idletasks()
        for t in attacker_tags:
            # test text cosmetics

            self.assertEqual(len(self.root.winfo_children()), 1)
            self.assertEqual(self.root.winfo_children()[-1].winfo_class(),
                             self.ex.winfo_class())
            char_idx = self.ex.tag_ranges(t)[0]
            event_gen.click_char(self.ex, char_idx, event_gen.right_click_coord)
            self.assertEqual(len(self.root.winfo_children()), 2)
            option_list = self.root.winfo_children()[1]
            self.assertEqual(option_list.winfo_class(), 'TFrame')
            ## Stuff
            ## End Stuff
            option_list.destroy()

        # self.assertEqual(self.ex_event, "esrdfg")


    """
    Sample button click event saved in self.ex_event
    """
    def test_gen_options(self):
        pattern = self.synonyms[0]
        opt_list = self.synonyms
        parent_tag = self.ex.get_parent_rep_tag(pattern)
        self.ex.add_tag_rep(pattern, opt_list)

        self.assertEqual(self.root.winfo_children()[-1].winfo_class(), self.ex.winfo_class())
        target_tags = self.ex.rep_replace_tags[parent_tag]
        attacker_tag = self.ex.rep_replace_tags[parent_tag][0]
        self.ex.gen_options(
            # self.ex_event is defined in the class setup, so interpreters might have
            # trouble recognizing its existence below
            self.ex_event,
            parent_tag,
            target_tags,
            attacker_tag,
        )
        option_list = self.root.winfo_children()[1]
        self.assertEqual(option_list.winfo_class(), 'TFrame')
        option_list_children = option_list.winfo_children()
        option_list_typebox = option_list_children[-1]
        self.assertEqual(option_list_typebox.cget('text'), self.ex.get_replace_type(attacker_tag)[0])
        option_list_options = option_list_children[:-1]
        self.assertEqual(len(opt_list), len(option_list_options))
        for i in range(len(opt_list)):
            self.assertEqual(opt_list[i], option_list_options[i].cget('text'))

    def test_new_option(self):
        # Set up the the full parent/child/options family
        ex_parent = self.ex.get_parent_rep_tag(self.synonyms[0])
        self.ex.add_tag_rep(self.synonyms[0], self.synonyms, sync=self.ex.syncTrue)
        self.assertEqual(self.ex.get('1.0', 'end').splitlines()[0], self.ex_phrase_concise)
        ex_frame = ttk.Frame(self.ex.master)
        ex_opt = self.ex.new_option(ex_frame, ex_parent, self.ex.rep_replace_tags[ex_parent], 1)
        ex_opt.grid(row=0, column=1, sticky=tk.W)
        ex_frame.place(x=10, y=10)
        self.ex.update_idletasks()
        event_gen.left_click_coord(ex_opt, [ex_opt.winfo_x(), ex_opt.winfo_y()])
        self.assertEqual(self.ex.get('1.0', 'end').splitlines()[0], self.ex_phrase_terse)

    def test_gen_typebox(self):
        replace_types = self.ex.replace_types
        ex_frame = ttk.Frame(self.ex.master)
        for s in replace_types:
            typebox = self.ex.gen_typebox(s, ex_frame)
            self.assertEqual(typebox.cget('text'), s[0])
            utils.del_fn(typebox)

    def test_gen_changing_typebox_get_to_fro(self):
        sample_iso = self.sample_iso
        sample_rep_s = self.sample_rep_s1
        sample_rep_u = self.sample_rep_u1
        sample_iso_ret = self.ex.gen_changing_typebox_get_to_fro(sample_iso)
        sample_rep_s_ret = self.ex.gen_changing_typebox_get_to_fro(sample_rep_s)
        sample_rep_u_ret = self.ex.gen_changing_typebox_get_to_fro(sample_rep_u)
        self.assertEqual(sample_iso_ret[0], self.ex.replace_types[0])
        self.assertEqual(sample_iso_ret[1], self.ex.replace_types[0])
        self.assertEqual(sample_rep_s_ret[0], self.ex.replace_types[1])
        self.assertEqual(sample_rep_s_ret[1], self.ex.replace_types[2])
        self.assertEqual(sample_rep_u_ret[0], self.ex.replace_types[2])
        self.assertEqual(sample_rep_u_ret[1], self.ex.replace_types[1])


    # The handler is tested instead of the top-level function because unittest
    # gets confused with the tkinter "after" function
    def test_gen_changing_typebox_handler(self):
        sample_tags = [self.sample_iso, self.sample_rep_s1, self.sample_rep_u1]

        for t in sample_tags:
            t_r1, t_r2 = self.ex.gen_changing_typebox_get_to_fro(t)
            children = self.root.winfo_children()
            self.assertEqual(len(children), 1)
            self.ex.gen_changing_typebox_handler(self.ex_event, t)
            children = self.root.winfo_children()
            self.assertEqual(len(children), 2)
            changing_typebox = children[1]
            self.assertEqual(changing_typebox.winfo_class(), 'TFrame')
            typebox_children = changing_typebox.winfo_children()
            self.assertEqual(len(typebox_children), 3)
            self.assertEqual(typebox_children[0].winfo_class(), 'Label')
            self.assertEqual(typebox_children[0].cget('text'), t_r1[0])
            self.assertEqual(typebox_children[1].winfo_class(), 'Label')
            self.assertEqual(typebox_children[1].cget('text'), '-->')
            self.assertEqual(typebox_children[2].winfo_class(), 'Label')
            self.assertEqual(typebox_children[2].cget('text'), t_r2[0])
            utils.del_fn(changing_typebox)

    def test_change_sync_worker(self):
        self.ex.append_child_tags(self.sample_parent, self.sample_rep_s1)
        self.ex.append_child_tags(self.sample_parent, self.sample_rep_u2)
        # self.ex.append_child_tags(self.sample_parent, self.sample_iso)
        self.ex.tag_add(self.sample_rep_s1, '2.0', '2.10')
        self.ex.tag_add(self.sample_rep_u2, '2.10', '2.20')
        self.assertListEqual(self.ex.rep_replace_tags[self.sample_parent], [self.sample_rep_s1,
                                                                            self.sample_rep_u2])
        self.ex.change_sync_worker(self.sample_rep_s1, self.sample_parent)
        self.assertListEqual(self.ex.rep_replace_tags[self.sample_parent], [self.sample_rep_u1,
                                                                            self.sample_rep_u2])
        self.ex.change_sync_worker(self.sample_rep_u2, self.sample_parent)
        self.assertListEqual(self.ex.rep_replace_tags[self.sample_parent], [self.sample_rep_u1,
                                                                            self.sample_rep_s2])
        self.ex.change_sync_worker(self.sample_rep_s2, self.sample_parent)
        self.assertListEqual(self.ex.rep_replace_tags[self.sample_parent], [self.sample_rep_u1,
                                                                            self.sample_rep_u2])

    def test_replace_text(self):
        self.assertEqual(self.ex.get('2.0', 'end-1c'), self.sample_line)
        self.ex.replace_text("foo", self.sample_iso)
        self.assertEqual(self.ex.get('2.0', 'end-1c'), self.sample_line)
        self.ex.tag_add(self.sample_iso, '2.0', '2.10')
        self.ex.replace_text("foo", self.sample_iso)
        self.assertEqual(self.ex.get('2.0', 'end-1c'), 'foo' + self.sample_line[10:])
        self.ex.replace_text("foo", self.sample_iso)
        self.assertEqual(self.ex.get('2.0', 'end-1c'), 'foo' + self.sample_line[10:])
        self.ex.replace_text("bar", self.sample_iso)
        self.assertEqual(self.ex.get('2.0', 'end-1c'), 'bar' + self.sample_line[10:])

    def test_replace_texts(self):
        self.assertEqual(self.ex.get('2.0', 'end-1c'), self.sample_line)
        self.ex.replace_texts('foo', [self.sample_iso])
        self.assertEqual(self.ex.get('2.0', 'end-1c'), self.sample_line)
        self.ex.tag_add(self.sample_iso, '2.0', '2.10')
        self.ex.tag_add(self.sample_rep_s1, '2.10', '2.20')
        self.ex.tag_add(self.sample_rep_u1, '2.20', 'end-1c')
        self.ex.replace_texts('foo', [self.sample_iso])
        self.assertEqual(self.ex.get('2.0', 'end-1c'), 'foo' + self.sample_line[10:])
        self.ex.replace_texts('bar', [self.sample_iso, self.sample_rep_s1])
        self.assertEqual(self.ex.get('2.0', 'end-1c'), 'bar' + 'bar' + self.sample_line[20:])
        self.ex.replace_texts('foo', [self.sample_iso, self.sample_rep_s1, self.sample_rep_u1])
        self.assertEqual(self.ex.get('2.0', 'end-1c'), 'foo' + 'foo' + 'foo')
        self.ex.replace_texts('bar', [self.sample_iso, self.sample_rep_u1])
        self.assertEqual(self.ex.get('2.0', 'end-1c'), 'bar' + 'foo' + 'bar')

    def test_add_tag_rep(self):
        # This test only checks that all of the expected sequences are binded to each tagname,
        # as how tkinter remembers what functions are binded to each sequence is very
        # hard to interpret
        ex_parent = self.ex.get_parent_rep_tag(self.synonyms[0])
        self.ex.add_tag_rep(self.synonyms[0], self.synonyms, sync=self.ex.syncTrue)
        expected_seqs = ['<Button-2>', '<Shift-Button-2>', '<Shift-Button-1>']
        for t in self.ex.rep_replace_tags[ex_parent]:
            seqs = self.ex.tag_bind(t, None, None)
            for s in expected_seqs:
                self.assertTrue(s in seqs)

    def test_setup_rep_bind_attacker(self):
        self.ex.tag_add(self.sample_rep_u1, '1.0')
        self.ex.setup_rep_bind_tag_attacker(self.sample_rep_u1, [self.sample_rep_u1], self.sample_parent)
        expected_seqs = ['<Button-2>', '<Shift-Button-2>', '<Shift-Button-1>']
        seqs = self.ex.tag_bind(self.sample_rep_u1, None, None)
        for s in expected_seqs:
            self.assertTrue(s in seqs)

    def test_setup_rep_bind_tag(self):
        # set up the parent/children in memory
        self.ex.rep_replace_tags[self.sample_parent] = [self.sample_rep_s1, self.sample_rep_s2]
        # Make sure each child tag is actually tagged in the text
        self.ex.tag_add(self.sample_rep_s1, '1.1')
        self.ex.tag_add(self.sample_rep_s2, '1.2')
        self.ex.setup_rep_bind_tag(self.sample_parent)
        # Perform same passing metric as written for add_tag_rep
        expected_seqs = ['<Button-2>', '<Shift-Button-2>', '<Shift-Button-1>']
        for t in self.ex.rep_replace_tags[self.sample_parent]:
            seqs = self.ex.tag_bind(t, None, None)
            for s in expected_seqs:
                self.assertTrue(s in seqs)






    # def test_add_tag_rep(self):
    #     self.ex.add_tag_rep(self.synonyms[0], self.synonyms, sync=self.ex.syncTrue)

if __name__ == '__main__':
    unittest.main()