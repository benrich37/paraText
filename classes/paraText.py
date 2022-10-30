import tkinter as tk
from tkinter import ttk
from libs import utils
import sys
import copy


class paraText(tk.Text):
    repFlag = "_REP_"
    repIdFlag = "_CNT_"
    syncFlag = "_SNC_"
    syncTrue = "TRUE"
    syncFalse = "FALSE"
    isoFlag = "_ISO_"

    replace_sync_types = [
        syncTrue,
        syncFalse
    ]

    replace_types = [
        "iso",
        "synced",
        "unsynced"
    ]

    replace_type_dict = {
        replace_types[0]: "#5376FE",
        replace_types[1]: "#FFBCBC",
        replace_types[2]: "#FFE4AD",
    }

    # Example tagnames
    # _ISO_blahblah
    ## a tag with surface text blahblah that is only expected to appear once
    # _REP_12_CNT_FALSE_SNC_blahblah
    ## a tag with surface text blahblah with personal id '12' and requests no sync
    # _REP_3_CNT_TRUE_SNC_blahblah
    ## a tag with surface text blahblah with personal id '3' and requests sync
    ### (a change to another tag with the same surface pattern will trigger a change to this tag, and vice versa)
    
    # https://htmlcolorcodes.com/color-picker/
    default_color="#FF5E3B"
    default_opaque_color = "#FFFFFF"
    sel_click_color="#3BB3FF"
    up_click_color="#FF3B3B"
    down_click_color="#FF9D3B"
    neg_click_color="#C8B1B1"
    # defaultunderlinecolor="red"
    # syncedunderlinecolor="#EE8100"

    def __init__(self, master=None, cnf={}, **kw):
        tk.Widget.__init__(self, master, 'text', cnf, kw)
        # replace_tags is a dictionary with tags, key values being the options possible
        # if tag has the iso flag, that tag is the tag used
        # if tag has the rep flag, look in rep_replace_tags for all tags actually used (each tag must be unique)
        self.replace_tags = {}
        self.rep_replace_tags = {}
        self.default_sync = self.syncTrue
        self.widget_holder = None


    ###
    ############
    #########################
    ##### COSMETIC FUNCTIONS ####################
    ######################### vvv
    ############ vvv
    ### vvv

    def get_replace_type_color(self, tag):
        replace_type = self.get_replace_type(tag)
        return self.replace_type_dict[replace_type]

    def change_highlight_default(self, event, widget):
        widget.config(background=self.default_color)

    def change_highlight_sel(self, event, widget):
        widget.config(background=self.sel_click_color)

    def change_highlight_up(self, event, widget):
        widget.config(background=self.up_click_color)

    def change_highlight_down(self, event, widget):
        widget.config(background=self.down_click_color)

    def change_highlight_neg(self, event, widget):
        widget.config(background=self.neg_click_color)

    def clear_widget_holder(self):
        utils.del_fn(self.widget_holder)
        self.widget_holder = None

    # This function is a lost cause, too many actions too quickly
    # def fadeout_widget_holder(self):
    #     children = self.widget_holder.winfo_children()
    #     hex_colors = []
    #     for child in children:
    #         hex_colors.append(child["background"])
    #     init_alphas = []
    #     for hex_color in hex_colors:
    #         init_alphas.append(utils.short_hex_alpha_to_dec_alpha(utils.get_hex_alpha(hex_color)))
    #     init_alpha = max(init_alphas)
    #     while init_alpha >= 0:
    #         for i in range(len(children)):
    #             print("doing nothing")
    #         # for i, child in enumerate(children):
    #         #     new_back = utils.set_hex_alpha(hex_colors[i], init_alpha)
    #         #     child.config(background=new_back)
    #         i -= 1
    #         # Sleep some time to make the transition not immediate
    #         time.sleep(0.05)
    #     self.clear_widget_holder()

    ###
    ############
    #########################
    ##### TAG CONVENTION FUNCTIONS ####################
    ######################### vvv
    ############ vvv
    ### vvv

    def get_replace_type(self, tag):
        tag1 = tag[0:5]
        if tag1 == self.isoFlag:
            return self.replace_types[0]
        elif tag1 == self.repFlag:
            synctag = self.parse_child_rep_id(tag)[1]
            if synctag == self.syncTrue:
                return self.replace_types[1]
            else:
                return self.replace_types[2]
        else:
            raise ValueError("Unexpected tag")

    def return_reptag_i(self, idx, sync, pattern):
        return self.child_rep_id(idx, sync, pattern)

    def child_rep_id(self, idx, sync, pattern):
        return self.repFlag + str(idx) + self.repIdFlag + str(sync) + self.syncFlag + pattern

    def parent_rep_id(self, pattern):
        return self.repFlag + pattern

    def parse_child_rep_id(self, rep_id):
        try:
            idx1 = len(self.repFlag)
            idx2 = rep_id.index(self.repIdFlag)
            return_id = int(rep_id[idx1:idx2])
        except Exception as e:
            print(e)
            sys.exit(1)
        try:
            idx3 = rep_id.index(self.repIdFlag) + len(self.repIdFlag)
            idx4 = rep_id.index(self.syncFlag)
            sync_arg = rep_id[idx3:idx4]
        except Exception as e:
            print(e)
            sys.exit(1)
        pattern = rep_id[idx4 + len(self.syncFlag):]
        return return_id, sync_arg, pattern

    def interp_sync_arg(self, syncarg):
        if syncarg is None:
            syncflag = self.default_sync
        else:
            syncflag = str(syncarg)
        return syncflag

    def get_last_rep_id(self, pattern):
        ids = []
        rep_ids = self.rep_replace_tags[self.parent_rep_id(pattern)]
        for i in rep_ids:
            id_i = self.parse_child_rep_id(rep_ids[i])[0]
            ids.append(id_i)
        return max(ids)

    def get_init_rep_id(self, pattern):
        start_id = None
        parent_tag = self.parent_rep_id(pattern)
        # if len(self.rep_replace_tags[self.parent_rep_id(pattern)]) == 0:
        if not parent_tag in self.rep_replace_tags:
            start_id = 0
        else:
            start_id = self.get_last_rep_id(pattern)
        return start_id

    ###
    ############
    #########################
    ##### REPLACE FUNCTIONALITY FUNCTIONS ####################
    ######################### vvv
    ############ vvv
    ### vvv

    def append_options(self, tag, opt_list):
        if not tag in self.replace_tags:
            self.replace_tags[tag] = []
        for i in range(len(opt_list)):
            utils.append_no_dup(opt_list[i], self.replace_tags[tag])

    def get_synced_tags(self, given_tags):
        synced_tags = []
        for i in range(len(given_tags)):
            sync_arg = self.parse_child_rep_id(given_tags[i])[1]
            if sync_arg == self.syncTrue:
                synced_tags.append(given_tags[i])
        return synced_tags

    def replace_text_handler(self, chosen_text, target_tag):
        init_bounds = self.tag_ranges(target_tag)
        if len(init_bounds) > 0:
            utils.insert(self, target_tag, chosen_text)
            self.delete(init_bounds[0], init_bounds[1])

    def replace_text(self, event, chosen_text, target_i):
        self.config(state=tk.NORMAL)
        self.replace_text_handler(chosen_text, target_i)
        utils.del_fn(event.widget.master)
        self.config(state=tk.DISABLED)

    def replace_texts(self, event, chosen_text, target_tags):
        for i in range(len(target_tags)):
            self.replace_text(event, chosen_text, target_tags[i])

    def change_sync_selection(self, event, attacker_tag):
        type_flag = attacker_tag[0:5]
        if type_flag == self.isoFlag:
            self.change_highlight_neg(event, event.widget)
        else:
            sync_flag = self.parse_child_rep_id(attacker_tag)
            if sync_flag == self.syncTrue:
                self.change_highlight_down(event, event.widget)
            else:
                self.change_highlight_up(event, event.widget)

    def change_child_tag_sync_flag(self, oldtag, new_sync_flag, parent_tag):
        ## NOTE: This function changes the paratext memory as well as returning the new tag for convenience
        idx, old_sync, pattern = self.parse_child_rep_id(oldtag)
        newtag = self.child_rep_id(idx, new_sync_flag, pattern)
        print('old dict is ' + str(self.rep_replace_tags[parent_tag]))
        place_in_list = self.rep_replace_tags[parent_tag].index(oldtag)
        self.rep_replace_tags[parent_tag][place_in_list] = newtag
        print('new dict is ' + str(self.rep_replace_tags[parent_tag]))
        bounds = self.tag_ranges(oldtag)
        self.tag_delete(oldtag)
        self.tag_add(newtag, bounds[0], bounds[1])
        return newtag

    def change_sync_to_false(self, event, target_tags, attacker_tag, parent_tag):
        new_attacker_tag = self.change_child_tag_sync_flag(attacker_tag, self.syncFalse, parent_tag)
        self.setup_rep_bind_tag(parent_tag)
        # self.setup_rep_bind_tag_attacker(new_attacker_tag, [new_attacker_tag], parent_tag)

    def change_sync_to_true(self, event, target_tags, attacker_tag, parent_tag):
        new_attacker_tag = self.change_child_tag_sync_flag(attacker_tag, self.syncTrue, parent_tag)
        # self.setup_rep_bind_tag_attacker(new_attacker_tag, target_tags, parent_tag)
        self.setup_rep_bind_tag(parent_tag)

    def change_sync(self, event, target_tags, attacker_tag, parent_tag):
        print('doing change sync')
        self.gen_changing_typebox(event, attacker_tag)
        type_flag = attacker_tag[0:5]
        if type_flag == self.isoFlag:
            self.focus_set()
        else:
            sync_flag = self.parse_child_rep_id(attacker_tag)[1]
            if sync_flag == self.syncTrue:
                self.change_sync_to_false(event, target_tags, attacker_tag, parent_tag)
            else:
                self.change_sync_to_true(event, target_tags, attacker_tag, parent_tag)

    def new_option(self, event, frame, parent_tag, target_tags, opt_idx, attacker_tag):
        opt_list = self.replace_tags[parent_tag]
        new_opt = tk.Label(master=frame, text=opt_list[opt_idx], borderwidth=1, relief="solid")
        new_opt.config(background=self.default_color)
        new_opt.bind('<Button-1>', lambda e: self.change_highlight_sel(e, new_opt))
        new_opt.bind('<ButtonRelease-1>',
                     lambda e: self.replace_texts(e, opt_list[opt_idx], target_tags))
        return new_opt

    def gen_typebox(self, replace_type, frame):
        color = self.replace_type_dict[replace_type]
        type_box = tk.Label(master=frame, text=replace_type[0], background=color)
        return type_box

    def gen_options(self, event, parent_tag, target_tags, attacker_tag):
        opt_list = self.replace_tags[parent_tag]
        frame = ttk.Frame(self.master)
        opt_boxes = []
        for i in range(len(opt_list)):
            opt_boxes.append(self.new_option(event, frame, parent_tag, target_tags, i, attacker_tag))
            opt_boxes[i].grid(row=i, column=1, sticky=tk.W)
        replace_type = self.get_replace_type(attacker_tag)
        type_box = self.gen_typebox(replace_type, frame)
        type_box.grid(row=0, column=0, sticky=tk.E)
        frame.grid_configure()
        frame.place(x=event.x, y=event.y)
        frame.focus_set()
        self.widget_holder = frame
        frame.bind('<FocusOut>', lambda e: self.clear_widget_holder())
        # frame.bind('<FocusOut>', lambda e: utils.del_fn(e.widget))
        self.update_idletasks()

    def gen_changing_typebox_get_to_fro(self, attacker_tag):
        type_flag = attacker_tag[0:5]
        if type_flag == self.isoFlag:
            r1 = self.replace_types[0]
            r2 = self.replace_types[0]
        elif type_flag == self.repFlag:
            sval = self.parse_child_rep_id(attacker_tag)[1]
            if sval == self.syncTrue:
                r1 = self.replace_types[1]
                r2 = self.replace_types[2]
            elif sval == self.syncFalse:
                r1 = self.replace_types[2]
                r2 = self.replace_types[1]
            else:
                print('unexpected tag in generating changing type box')
                sys.exit(1)
        else:
            print('unexpected tag in generating changing type box')
            sys.exit(1)
        return r1, r2

    def gen_changing_typebox(self, event, attacker_tag):
        frame = ttk.Frame(self.master)
        r1, r2 = self.gen_changing_typebox_get_to_fro(attacker_tag)
        b1 = tk.Label(master=frame, text=r1[0], background=self.replace_type_dict[r1])
        b2 = tk.Label(master=frame, text='-->', background=self.default_opaque_color)
        b3 = tk.Label(master=frame, text=r2[0], background=self.replace_type_dict[r2])
        b1.grid(row=0, column=0)
        b2.grid(row=0, column=1)
        b3.grid(row=0, column=2)
        frame.grid_configure()
        frame.place(x=event.x, y=event.y)
        frame.focus_set()
        frame.bind('<FocusOut>', lambda e: utils.del_fn(e.widget))
        self.update_idletasks()
        self.widget_holder = frame
        self.after(500, self.clear_widget_holder)

    def setup_rep_bind_tag_attacker(self, attacker_tag, target_tags, parent_tag):
        self.tag_bind(attacker_tag,
                      '<Button-2>',
                      lambda e: self.gen_options(e,
                                                 parent_tag,
                                                 target_tags,
                                                 attacker_tag
                                                 )
                      )
        # I believe this might not be working because events with modifiers are superceded by events specified sans modifier
        # ie, since button-2 is already tagged, shift-button-2 won't execute
        self.tag_bind(attacker_tag,
                      '<Shift-Button-2>',
                      lambda e: self.gen_changing_typebox(e, attacker_tag)
                      )
        self.tag_bind(attacker_tag,
                      '<Shift-Button-1>',
                      lambda e: self.change_sync(e, target_tags, attacker_tag, parent_tag)
                      )
        sync_flag = self.parse_child_rep_id(attacker_tag)
        underline_color = self.get_replace_type_color(attacker_tag)
        self.tag_config(attacker_tag,
                        underline=True,
                        underlinefg=underline_color,
                        foreground=utils.make_darker(underline_color)
                        )
        self.update_idletasks()

    def setup_rep_bind_tag(self, parent_tag):
        # attacker_tags are tags which we will bind replace commands upon
        attacker_tags = self.rep_replace_tags[parent_tag]
        # target_tags are the tags which will undergo text replacement if a command is executed
        target_tags = []
        # synced_tags indicate tags which are synced to each other
        # (all bound replace commands will replace all other synced tags)
        syncd_tags = self.get_synced_tags(attacker_tags)

        for i in range(len(attacker_tags)):
            if attacker_tags[i] in syncd_tags:
                target_tags = copy.deepcopy(syncd_tags)
            else:
                target_tags = [attacker_tags[i]]
            self.setup_rep_bind_tag_attacker(attacker_tags[i], target_tags, parent_tag)

    def append_child_tags(self, parent_tag, child_tag):
        if not parent_tag in self.rep_replace_tags:
            self.rep_replace_tags[parent_tag] = []
        utils.append_no_dup(child_tag, self.rep_replace_tags[parent_tag])

    def add_tag_rep(self, pattern, opt_list, sync=None):
        parent_tag = self.parent_rep_id(pattern)
        synctag = self.interp_sync_arg(sync)
        self.append_options(parent_tag, opt_list)
        matches = utils.return_matches(self, pattern)
        start_id = self.get_init_rep_id(pattern)
        for i in range(len(matches)):
            ctag_i = self.child_rep_id(start_id + i,
                                           synctag,
                                           pattern)
            self.append_child_tags(parent_tag, ctag_i)
            bound1 = matches[i]
            bound2 = utils.add_to_idx(matches[i], len(pattern))
            self.tag_add(ctag_i,
                         bound1,
                         bound2
                         )
        self.setup_rep_bind_tag(parent_tag)
