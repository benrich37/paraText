import tkinter as tk
from tkinter import ttk
from libs import utils
import sys
import copy


class paraText(tk.Text):
    # String variables which will be called when constructing tag strings
    repFlag = "_REP_"
    isoFlag = "_ISO_"
    repIdFlag = "_CNT_"
    syncFlag = "_SNC_"
    syncTrue = "True"
    syncFalse = "False"

    replace_sync_types = [
        syncTrue,
        syncFalse
    ]

    # listing possible types for cosmetic purposes later on
    replace_types = [
        "iso",
        "synced",
        "unsynced"
    ]

    # Hex colors to sync up with different possible types
    replace_type_dict = {
        replace_types[0]: "#5376FE",
        replace_types[1]: "#FFBCBC",
        replace_types[2]: "#FFE4AD",
    }

    # Example tagnames
    # _ISO_blahblah
    ## a tag with surface text blahblah that is only expected to appear once
    # _REP_12_CNT_FALSE_SNC_blahblah
    ## a tag with surface text blahblah with personal id '12' and
    ## requests no sync
    # _REP_3_CNT_TRUE_SNC_blahblah
    ## a tag with surface text blahblah with personal id '3' and requests sync
    ### (a change to another tag with the same surface pattern will trigger a
    ### change to this tag, and vice versa)

    # https://htmlcolorcodes.com/color-picker/
    default_color = "#FF5E3B"
    default_opaque_color = "#FFFFFF"
    sel_click_color = "#3BB3FF"
    up_click_color = "#FF3B3B"
    down_click_color = "#FF9D3B"
    neg_click_color = "#C8B1B1"
    # defaultunderlinecolor="red"
    # syncedunderlinecolor="#EE8100"

    def __init__(self, master=None, cnf={}, **kw):
        tk.Widget.__init__(self, master, 'text', cnf, kw)
        # replace_tags is a dictionary with tags, key values being the options possible
        ## replace_tags will only have iso tags and parent rep tags
        # if tag has the iso flag, that tag is the tag used
        # if tag has the rep flag, look in rep_replace_tags for all tags
        # actually used (each tag must be unique)
        # self.replace_tags = {}
        # # rep_replace_tags is a dictionary with all the parent rep tags being used, and the key values are all the
        # # child rep tags being used
        # self.rep_replace_tags = {}
        # This will be an all encompassing directory for a parent, which will
        # instead map a family name to
        # FIRST the list of options, and
        # SECOND the list of child tagnames
        self.directory = {}
        # whether setting up rep tags will default to sync them together or not
        self.default_sync = self.syncTrue
        # May delete later - this is just a temporary variable to store in the paraText class so that particular widgets
        # can be accessed easily if desired
        self.widget_holder = None
        self.focus_set()
        self.bind('<Button-1>', lambda e: self.focus_set())
        self.count = 100

    ###
    ############
    #########################
    ##### COSMETIC FUNCTIONS ####################
    ######################### vvv
    ############ vvv
    ### vvv

    def get_replace_type_color(self, tag):
        # give a tag, return the designated color for the tag type
        replace_type = self.get_replace_type(tag)
        return self.replace_type_dict[replace_type]


    # Bunch of functions to change widget backgrounds to class variable colors
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
        """ Deletes whatever widget was put in the class widget holder
        :return:
        """
        print('clearing widget holder')
        utils.del_fn(self.widget_holder)
        self.widget_holder = None

    ###
    ############
    #########################
    ##### TAG CONVENTION FUNCTIONS ####################
    ######################### vvv
    ############ vvv
    ### vvv

    def get_replace_type(self, tag):
        """ Extracts an informative string telling the replace type of
               provided tag
        :param (str) tag: tag to look at
        :return (str) rep_type: Informative string of replace type
        """
        tag1 = tag[0:5]
        if tag1 == self.isoFlag:
            rep_type = self.replace_types[0]
        elif tag1 == self.repFlag:
            synctag = self.parse_child_rep_tag(tag)[1]
            if synctag == self.syncTrue:
                rep_type = self.replace_types[1]
            else:
                rep_type = self.replace_types[2]
        else:
            raise ValueError("Unexpected tag")
        return rep_type

    def get_child_rep_tag(self, idx, sync, pattern):
        """ Concatenates the child rep tag via given arguments and class
               variables
        :param idx: (int) child ID to use
        :param sync: (bool or str) True/False for whether its synced
        :param pattern: (str) Pattern of parent tag
        :return child_rep_tag: (str) String of constructed child rep tag
        """
        child_rep_tag = self.repFlag + str(idx) + self.repIdFlag\
            + str(sync) + self.syncFlag + pattern
        return child_rep_tag

    def get_parent_rep_tag(self, pattern):
        """
        :param pattern: String of pattern parent rep id is for
        :return parent_rep_id: String of parent rep id to be used
        """
        return self.repFlag + pattern

    def parse_child_rep_tag(self, rep_tag):
        """
        :param rep_tag: (str) child rep tag to parse
        :return:
        return_id (int) Child's ID;
        sync_arg (str) Sync bool as string;
        pattern (str) Governing pattern
        """
        try:
            idx1 = len(self.repFlag)
            idx2 = rep_tag.index(self.repIdFlag)
            return_id = int(rep_tag[idx1:idx2])
        except Exception as e:
            print(e)
            sys.exit(1)
        try:
            idx3 = rep_tag.index(self.repIdFlag) + len(self.repIdFlag)
            idx4 = rep_tag.index(self.syncFlag)
            sync_arg = rep_tag[idx3:idx4]
        except Exception as e:
            print(e)
            sys.exit(1)
        pattern = rep_tag[idx4 + len(self.syncFlag):]
        return return_id, sync_arg, pattern

    def interp_sync_arg(self, syncarg):
        """ Makes sure the syncarg given gets turned into the problem sync option flag
        :param syncarg: Boolean for if we're syncing or not
        :return syncflag: String to be used as tag for interpreting syncing
        """
        if syncarg is None:
            syncflag = self.default_sync
        else:
            syncflag = str(syncarg)
        return syncflag

    def get_last_rep_id(self, pattern):
        """ Gets the ID of the most recently added child for a parent's pattern
        :param pattern: String for parent's pattern
        :return last_rep_id: Integer of most recently added child ID
        """
        ids = []
        rep_ids = self.directory[self.get_parent_rep_tag(pattern)][1]
        for id in rep_ids:
            id_i = self.parse_child_rep_tag(id)[0]
            ids.append(id_i)
        if len(ids) == 0:
            last_rep_id = 0
        else:
            last_rep_id = max(ids)
        return last_rep_id

    def get_init_rep_id(self, pattern):
        """ Gets ID to use for adding a child
        :param pattern: String of pattern the parent tag is based on
        :return start_id: Integer of child ID to use for first appended child
        """
        parent_tag = self.get_parent_rep_tag(pattern)
        # if parent_tag not in self.rep_replace_tags:
        #     start_id = 0
        # else:
        #     start_id = self.get_last_rep_id(pattern) + 1
        if parent_tag not in self.directory:
            start_id = 0
        else:
            start_id = self.get_last_rep_id(pattern) + 1
        return start_id

    ###
    ############
    #########################
    ##### REPLACE FUNCTIONALITY FUNCTIONS ####################
    ######################### vvv
    ############ vvv
    ### vvv

    def append_options(self, tag, opt_list):
        """ Handler for adding options to a parent tag or iso tag
        :param tag: String of tag
        :param opt_list: List of strings to be added to the tags option list
        :return None:
        """
        # if tag not in self.replace_tags:
        #     self.replace_tags[tag] = []
        # for i in range(len(opt_list)):
        #     utils.append_no_dup(opt_list[i], self.replace_tags[tag])

        if tag not in self.directory:
            self.directory[tag] = [[],[]]
        for i in range(len(opt_list)):
            utils.append_no_dup(opt_list[i], self.directory[tag][0])

    def get_synced_tags(self, given_tags):
        """
        :param (list of str) given_tags: List of all tags to analyze
        :return (list of str) synced_tags: All tags from given_tags that have
                                              sync set to True
        """
        synced_tags = []
        for i in range(len(given_tags)):
            sync_arg = self.parse_child_rep_tag(given_tags[i])[1]
            if sync_arg == self.syncTrue:
                synced_tags.append(given_tags[i])
        return synced_tags

    def replace_text(self, chosen_text, target_tag):
        """
        :param (str) chosen_text: Text which will replace whatever the
                                     target_tag's text currently is
        :param (str) target_tag: Tagname for child who's text we're replacing
        :return:
        """
        self.config(state=tk.NORMAL)
        init_bounds = self.tag_ranges(target_tag)
        if len(init_bounds) > 0:
            utils.insert(self, target_tag, chosen_text)
            self.delete(init_bounds[0], init_bounds[1])
        self.config(state=tk.DISABLED)

    def replace_texts(self, chosen_text, target_tags):
        """
        :param (str) chosen_text: Text which will replace whatever the
                                     target_tags' text currently are
        :param (list of str) target_tags: Tagnames of children who's text
                                             we're replacing
        :return:
        """
        for i in range(len(target_tags)):
            self.replace_text(chosen_text, target_tags[i])
        self.focus_set()

    # def change_sync_selection(self, event, attacker_tag):
    #     type_flag = attacker_tag[0:5]
    #     if type_flag == self.isoFlag:
    #         self.change_highlight_neg(event, event.widget)
    #     else:
    #         sync_flag = self.parse_child_rep_tag(attacker_tag)
    #         if sync_flag == self.syncTrue:
    #             self.change_highlight_down(event, event.widget)
    #         else:
    #             self.change_highlight_up(event, event.widget)

    def change_child_tag_sync_flag(self, oldtag, new_sync_flag, parent_tag):
        """
        :param (str) oldtag: Child tag who's sync flag we're changing
        :param (str) new_sync_flag: Sync flag we're inserting into oldtag
        :param (str) parent_tag: Child's parent for re-tagging purposes
        :return:
        """
        idx, old_sync, pattern = self.parse_child_rep_tag(oldtag)
        newtag = self.get_child_rep_tag(idx, new_sync_flag, pattern)
        place_in_list = self.directory[parent_tag][1].index(oldtag)
        self.directory[parent_tag][1][place_in_list] = newtag
        bounds = self.tag_ranges(oldtag)
        self.tag_delete(oldtag)
        self.tag_add(newtag, bounds[0], bounds[1])
        self.update_idletasks()

    def change_sync_worker(self, attacker_tag, parent_tag):
        """
        :param (str) attacker_tag: Tagname of child who's sync option we're
                                      changing
        :param (str) parent_tag: Tagname of child's parent for updating the
                                    memory
        :return:
        """
        sync_flag = self.parse_child_rep_tag(attacker_tag)[1]
        new_sync_flag = utils.str_not(sync_flag)
        self.change_child_tag_sync_flag(attacker_tag,
                                        new_sync_flag,
                                        parent_tag)
        self.setup_rep_bind_tag(parent_tag)

    def change_sync(self, event, attacker_tag, parent_tag):
        self.gen_changing_typebox(event, attacker_tag)
        self.change_sync_worker(attacker_tag, parent_tag)

    def new_option(self, frame, parent_tag, target_tags, opt_idx):
        """
        :param (Widget) frame: The widget holding all the new options
        :param (str) parent_tag: The tagname of the target's parent
        :param (list[str]) target_tags: The tags which will have their text changed
        :param (int) opt_idx: An int referring to which option from the option
                                 list this widget will refer to
        :return (Widget) new_opt: The label widget which will trigger a change
                                     to the specified option
        """
        opt_list = self.directory[parent_tag][0]
        new_opt = tk.Label(master=frame,
                           text=opt_list[opt_idx],
                           borderwidth=1,
                           relief="solid")
        new_opt.config(background=self.default_color)
        new_opt.bind('<Button-1>',
                     lambda e: self.change_highlight_sel(e, new_opt))
        new_opt.bind('<ButtonRelease-1>',
                     lambda e: self.replace_texts(opt_list[opt_idx],
                                                  target_tags))
        return new_opt

    def gen_typebox(self, replace_type, frame):
        """ Generates the box in the topleft of an option list to tell the user
               what the sync type of the clicked selection currently is
        :param replace_type (str): The string for what the sync currently is
        :param     frame (Widget): The parent frame holding the typebox along
                                      with the options
        :return:
        """
        color = self.replace_type_dict[replace_type]
        type_box = tk.Label(master=frame,
                            text=replace_type[0],
                            background=color)
        return type_box

    def gen_options(self, event, parent_tag, target_tags, attacker_tag):
        """ Generates the options dropdown menu
        :param     (Event) event: Event which triggered the function
                                     (A right click on some tagged text)
        :param       (str) parent_tag: parent tagname of tagged selection
        :param       (list[str]) target_tags: tagnames of selections to be changed
        :param       (str) attacker_tag: tagname of the selection clicked on
        :returns: (action) Generates a list of clickable options to replace
                              text within the document
        """
        opt_list = self.directory[parent_tag][0]
        frame = ttk.Frame(self.master)
        opt_boxes = []
        for i in range(len(opt_list)):
            opt_boxes.append(self.new_option(frame,
                                             parent_tag,
                                             target_tags,
                                             i))
            opt_boxes[i].grid(row=i, column=1, sticky=tk.W)
        replace_type = self.get_replace_type(attacker_tag)
        type_box = self.gen_typebox(replace_type, frame)
        type_box.grid(row=0, column=0, sticky=tk.E)
        frame.grid_configure()
        frame.place(x=event.x, y=event.y)
        frame.focus_set()
        self.widget_holder = frame
        frame.bind('<FocusOut>', lambda e: self.clear_widget_holder())
        self.update_idletasks()

    def gen_changing_typebox_get_to_fro(self, attacker_tag):
        """ Returns the current sync type and the sync type a sync change would
              create
        :param (str) attacker_tag: The attacker tag we are looking at
        :return (str) r1: Current sync type
        :return (str) r2: Upcoming sync type
        """
        type_flag = attacker_tag[0:5]
        if type_flag == self.isoFlag:
            r1 = self.replace_types[0]
            r2 = self.replace_types[0]
        elif type_flag == self.repFlag:
            sval = self.parse_child_rep_tag(attacker_tag)[1]
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

    def gen_changing_typebox_handler(self, event, attacker_tag):

        """ Handler function to do the work for gen_changing_typebox
        :param event: Event which triggered gen_changing_typebox
        :param attacker_tag: Tag of selection which received triggering event
        :return:
        """
        frame = ttk.Frame(self.master)
        r1, r2 = self.gen_changing_typebox_get_to_fro(attacker_tag)
        b1 = tk.Label(master=frame,
                      text=r1[0],
                      background=self.replace_type_dict[r1])
        b2 = tk.Label(master=frame,
                      text='-->',
                      background=self.default_opaque_color)
        b3 = tk.Label(master=frame,
                      text=r2[0],
                      background=self.replace_type_dict[r2])
        b1.grid(row=0, column=0)
        b2.grid(row=0, column=1)
        b3.grid(row=0, column=2)
        frame.grid_configure()
        frame.place(x=event.x, y=event.y)
        frame.focus_set()
        frame.bind('<FocusOut>', lambda e: utils.del_fn(e.widget))
        self.update_idletasks()
        self.widget_holder = frame

    def gen_changing_typebox(self, event, attacker_tag):

        """Creates a box which tells the user info about changing the sync type
        :param event: Event which triggered gen_changing_typebox
        :param attacker_tag: Tag of selection which received triggering event
        :return:
        """

        self.gen_changing_typebox_handler(event, attacker_tag)
        self.after(500, self.clear_widget_holder)

    def setup_rep_bind_tag_attacker(self,
                                    attacker_tag, target_tags, parent_tag):
        """
        :param (str) attacker_tag: child tagname we are binding seq/funcs to
        :param (list of str) target_tags: all other child tagnames subject to
                                             change by actions from attacker
        :param (str) parent_tag: parent name of the children
        :return:
        """
        self.tag_bind(attacker_tag,
                      '<Button-2>',
                      lambda e: self.gen_options(e,
                                                 parent_tag,
                                                 target_tags,
                                                 attacker_tag
                                                 )
                      )
        self.tag_bind(attacker_tag,
                      '<Button-3>',
                      lambda e: self.gen_options(e,
                                                 parent_tag,
                                                 target_tags,
                                                 attacker_tag
                                                 )
                      )
        self.tag_bind(attacker_tag,
                      '<Shift-Button-2>',
                      lambda e: self.gen_changing_typebox(e, attacker_tag)
                      )
        # Binds shift-button-1 to change the sync option for the attacker_tag (changes the tagname and re-sets up all
        # the actions)
        self.tag_bind(attacker_tag,
                      '<Shift-Button-3>',
                      lambda e: self.gen_changing_typebox(e, attacker_tag)
                      )
        self.tag_bind(attacker_tag,
                      '<Shift-Button-1>',
                      lambda e: self.change_sync(e, attacker_tag, parent_tag)
                      )
        underline_color = self.get_replace_type_color(attacker_tag)
        # This should probably be its own function - just sets up the text color and stuff to give visual indicator
        # for what kind of sync type it is
        self.tag_config(attacker_tag,
                        underline=True,
                        underlinefg=underline_color,
                        foreground=utils.make_darker(underline_color)
                        )
        # update_idletasks makes sure that tasks that aren't refreshed by default get refreshed to make sure everything
        # changed appropriately (very much a safety net kind of function)
        self.update_idletasks()

    def setup_rep_bind_tag(self, parent_tag):
        """ Goes through all children for a parent_tag and sets up the proper
               binds
        :param (str) parent_tag: tagname of parent we're traversing
        :return:
        """
        # attacker_tags are tags which we will bind replace commands upon
        # target_tags are the tags which will undergo text replacement if a
        # command is executed
        # synced_tags indicate tags which are synced to each other
        # (all bound replace commands will replace all other synced tags)
        attacker_tags = self.directory[parent_tag][1]
        syncd_tags = self.get_synced_tags(attacker_tags)
        for i in range(len(attacker_tags)):
            if attacker_tags[i] in syncd_tags:
                target_tags = copy.deepcopy(syncd_tags)
            else:
                target_tags = [attacker_tags[i]]
            self.setup_rep_bind_tag_attacker(attacker_tags[i],
                                             target_tags,
                                             parent_tag)

    def append_child_tags(self, parent_tag, child_tag):
        """
        :param (str) parent_tag: Parent tag who's child list we're appending
        :param (str) child_tag: Child tag we're appending
        :return:
        """
        if parent_tag not in self.directory:
            self.directory[parent_tag] = [[],[]]
        utils.append_no_dup(child_tag, self.directory[parent_tag][1])

    def add_tag_rep(self, pattern, opt_list, sync=None):
        """
        :param (str) pattern: String of pattern to search for, where each
                                 instance of this pattern in the text will
                                 get tagged a unique child tagname
        :param (list of str) opt_list: A list of strings which will serve as
                                          options available for substitution
        :param (bool) sync: Whether these children will be initiated as synced
                               or unsynced
        :return:
        """
        parent_tag = self.get_parent_rep_tag(pattern)
        synctag = self.interp_sync_arg(sync)
        self.append_options(parent_tag, opt_list)
        matches = utils.return_matches(self, pattern)
        start_id = self.get_init_rep_id(pattern)
        for i in range(len(matches)):
            ctag_i = self.get_child_rep_tag(start_id + i,
                                            synctag,
                                            pattern)
            self.append_child_tags(parent_tag, ctag_i)
            bound1 = matches[i]
            bound2 = utils.add_to_char_idx(matches[i], len(pattern))
            self.tag_add(ctag_i,
                         bound1,
                         bound2
                         )
        self.setup_rep_bind_tag(parent_tag)

    def counter(self):
        """ Counter for giving all parents a new name if none is given
        returns: (int) the current count number
        """
        self.count += 1
        return self.count - 1

    def add_tag_idcs(self, idcs_list, opt_list, name=None, sync=None):
        """
        :param (list of str) idcs_list: List of char idcs to use as bounds
        :param (list of str) opt_list: List of options to store under parent
        :param (str) name: Name to use for storing (autogenerates int of None)
        :param (bool) sync: Whether to sync the children by default
        """
        if name is None:
            name = str(self.counter())
        parent_tag = self.get_parent_rep_tag(name)
        synctag = self.interp_sync_arg(sync)
        self.append_options(parent_tag, opt_list)
        start_id = self.get_init_rep_id(name)
        for i in range(int(len(idcs_list) / 2)):
            ctag_i = self.get_child_rep_tag(start_id + i,
                                            synctag,
                                            name)
            self.append_child_tags(parent_tag, ctag_i)
            self.tag_add(ctag_i,
                         idcs_list[(2 * i)],
                         idcs_list[(2 * i) + 1]
                         )
        self.setup_rep_bind_tag(parent_tag)




