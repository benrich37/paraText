"""The original paraText widget: a tk.Text with clickable replacement options.

Underlined spans can be right-clicked to pick a replacement from an option
list, and shift-left-clicked to toggle whether that span is "synced" with the
other spans of the same parent (a replacement on one synced span replaces all
synced spans).  All state is encoded in tk text-tag names; see the class
docstring.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from paratext import textutils as utils


class ParaText(tk.Text):
    """tk.Text subclass whose tagged spans offer replacement options.

    Tag naming convention:

    - ``_ISO_<pattern>``: a stand-alone span expected to appear once.
    - ``_REP_<pattern>``: a *parent* tag.  Never applied to text; it is the key
      under which options (``replace_tags``) and children
      (``rep_replace_tags``) are stored.
    - ``_REP_<id>_CNT_<True|False>_SNC_<pattern>``: a *child* tag, one per
      occurrence, with a per-parent integer id and a sync flag.  Toggling sync
      renames the tag.
    """

    # String variables which will be called when constructing tag strings
    repFlag = "_REP_"
    isoFlag = "_ISO_"
    repIdFlag = "_CNT_"
    syncFlag = "_SNC_"
    syncTrue = "True"
    syncFalse = "False"

    replace_sync_types = [syncTrue, syncFalse]

    # Possible replace types, used for cosmetics (typebox letter and colors)
    replace_types = ["iso", "synced", "unsynced"]

    # Hex colors for each replace type
    replace_type_dict = {
        replace_types[0]: "#5376FE",
        replace_types[1]: "#FFBCBC",
        replace_types[2]: "#FFE4AD",
    }

    # https://htmlcolorcodes.com/color-picker/
    default_color = "#FF5E3B"
    default_opaque_color = "#FFFFFF"
    sel_click_color = "#3BB3FF"
    up_click_color = "#FF3B3B"
    down_click_color = "#FF9D3B"
    neg_click_color = "#C8B1B1"

    # How long (ms) the sync-change indicator stays on screen
    typebox_lifetime_ms = 500

    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        # {iso tag or parent rep tag: [option strings]}
        self.replace_tags = {}
        # {parent rep tag: [child rep tags]}
        self.rep_replace_tags = {}
        # whether new rep tags are synced together by default
        self.default_sync = self.syncTrue
        # the currently open popup (options list or sync indicator), if any
        self.widget_holder = None
        # On macOS (aqua) the right mouse button is Button-2; elsewhere it is
        # Button-3 (Button-2 is the middle button).
        self.right_button = 2 if self.tk.call("tk", "windowingsystem") == "aqua" else 3
        self.focus_set()
        self.bind("<Button-1>", lambda e: self.focus_set())
        self.count = 100

    @property
    def right_click_seq(self) -> str:
        return f"<Button-{self.right_button}>"

    @property
    def shift_right_click_seq(self) -> str:
        return f"<Shift-Button-{self.right_button}>"

    @property
    def bound_seqs(self) -> list[str]:
        """Event sequences bound to every child rep tag."""
        return [self.right_click_seq, self.shift_right_click_seq, "<Shift-Button-1>"]

    # ----------------------------------------------------------------------
    # Cosmetic functions
    # ----------------------------------------------------------------------

    def get_replace_type_color(self, tag):
        """Return the designated color for the type of ``tag``."""
        return self.replace_type_dict[self.get_replace_type(tag)]

    # Change widget backgrounds to class variable colors
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
        """Destroy whatever popup is in the widget holder."""
        utils.del_fn(self.widget_holder)
        self.widget_holder = None

    def _popup_position(self, event):
        """Convert event coords (relative to this widget) to master coords."""
        return event.x + self.winfo_x(), event.y + self.winfo_y()

    # ----------------------------------------------------------------------
    # Tag convention functions
    # ----------------------------------------------------------------------

    def get_replace_type(self, tag):
        """Return the replace type ('iso', 'synced' or 'unsynced') of ``tag``."""
        if tag.startswith(self.isoFlag):
            return self.replace_types[0]
        if tag.startswith(self.repFlag):
            synctag = self.parse_child_rep_tag(tag)[1]
            return self.replace_types[1] if synctag == self.syncTrue else self.replace_types[2]
        raise ValueError(f"Unexpected tag {tag!r}")

    def get_child_rep_tag(self, idx, sync, pattern):
        """Build a child rep tag from an id, a sync flag and a pattern."""
        return self.repFlag + str(idx) + self.repIdFlag + str(sync) + self.syncFlag + pattern

    def get_parent_rep_tag(self, pattern):
        """Build the parent rep tag for ``pattern``."""
        return self.repFlag + pattern

    def is_child_rep_tag(self, tag):
        return tag.startswith(self.repFlag) and self.repIdFlag in tag and self.syncFlag in tag

    def parse_child_rep_tag(self, rep_tag):
        """Split a child rep tag into ``(id: int, sync flag: str, pattern: str)``."""
        try:
            idx2 = rep_tag.index(self.repIdFlag)
            idx3 = idx2 + len(self.repIdFlag)
            idx4 = rep_tag.index(self.syncFlag, idx3)
            return_id = int(rep_tag[len(self.repFlag) : idx2])
        except ValueError as e:
            raise ValueError(f"{rep_tag!r} is not a child rep tag") from e
        sync_arg = rep_tag[idx3:idx4]
        pattern = rep_tag[idx4 + len(self.syncFlag) :]
        return return_id, sync_arg, pattern

    def interp_sync_arg(self, syncarg):
        """Turn a bool/str/None sync argument into a sync flag string."""
        return self.default_sync if syncarg is None else str(syncarg)

    def get_last_rep_id(self, pattern):
        """Return the largest child id under ``pattern``'s parent."""
        rep_ids = self.rep_replace_tags[self.get_parent_rep_tag(pattern)]
        return max(self.parse_child_rep_tag(t)[0] for t in rep_ids)

    def get_init_rep_id(self, pattern):
        """Return the id to use for the next child added under ``pattern``."""
        parent_tag = self.get_parent_rep_tag(pattern)
        if not self.rep_replace_tags.get(parent_tag):
            return 0
        return self.get_last_rep_id(pattern) + 1

    # ----------------------------------------------------------------------
    # Replace functionality
    # ----------------------------------------------------------------------

    def append_options(self, tag, opt_list):
        """Add options (without duplicates) to a parent or iso tag."""
        options = self.replace_tags.setdefault(tag, [])
        for opt in opt_list:
            utils.append_no_dup(opt, options)

    def get_synced_tags(self, given_tags):
        """Return the child rep tags in ``given_tags`` whose sync flag is True."""
        return [t for t in given_tags if self.is_child_rep_tag(t) and self.parse_child_rep_tag(t)[1] == self.syncTrue]

    def replace_text(self, chosen_text, target_tag):
        """Replace the text under ``target_tag`` with ``chosen_text``.

        Works on DISABLED widgets; the widget's state is restored afterwards.
        """
        prior_state = self.cget("state")
        self.config(state=tk.NORMAL)
        utils.replace_tagged_text(self, target_tag, chosen_text)
        self.config(state=prior_state)

    def replace_texts(self, chosen_text, target_tags):
        """Replace the text under every tag in ``target_tags``."""
        for tag in target_tags:
            self.replace_text(chosen_text, tag)
        self.focus_set()

    def change_child_tag_sync_flag(self, oldtag, new_sync_flag, parent_tag):
        """Rename ``oldtag`` to carry ``new_sync_flag``, in memory and in the text."""
        idx, _, pattern = self.parse_child_rep_tag(oldtag)
        newtag = self.get_child_rep_tag(idx, new_sync_flag, pattern)
        children = self.rep_replace_tags[parent_tag]
        children[children.index(oldtag)] = newtag
        bounds = self.tag_ranges(oldtag)
        self.tag_delete(oldtag)
        if bounds:
            self.tag_add(newtag, bounds[0], bounds[1])
        self.update_idletasks()

    def change_sync_worker(self, attacker_tag, parent_tag):
        """Toggle the sync flag of ``attacker_tag`` and rebind its family."""
        sync_flag = self.parse_child_rep_tag(attacker_tag)[1]
        self.change_child_tag_sync_flag(attacker_tag, utils.str_not(sync_flag), parent_tag)
        self.setup_rep_bind_tag(parent_tag)

    def change_sync(self, event, attacker_tag, parent_tag):
        self.gen_changing_typebox(event, attacker_tag)
        self.change_sync_worker(attacker_tag, parent_tag)

    def new_option(self, frame, parent_tag, target_tags, opt_idx):
        """Create the clickable label for option ``opt_idx`` of ``parent_tag``.

        :param frame: widget holding the options
        :param parent_tag: tagname of the targets' parent
        :param target_tags: tags whose text is replaced when this option is chosen
        :param opt_idx: index into the parent's option list
        """
        opt_list = self.replace_tags[parent_tag]
        new_opt = tk.Label(master=frame, text=opt_list[opt_idx], borderwidth=1, relief="solid")
        new_opt.config(background=self.default_color)
        new_opt.bind("<Button-1>", lambda e: self.change_highlight_sel(e, new_opt))
        new_opt.bind("<ButtonRelease-1>", lambda e: self.replace_texts(opt_list[opt_idx], target_tags))
        return new_opt

    def gen_typebox(self, replace_type, frame):
        """Create the small label showing the clicked span's replace type."""
        return tk.Label(master=frame, text=replace_type[0], background=self.replace_type_dict[replace_type])

    def gen_options(self, event, parent_tag, target_tags, attacker_tag):
        """Open the options popup for a right click on ``attacker_tag``."""
        self.clear_widget_holder()
        opt_list = self.replace_tags[parent_tag]
        frame = ttk.Frame(self.master)
        for i in range(len(opt_list)):
            self.new_option(frame, parent_tag, target_tags, i).grid(row=i, column=1, sticky=tk.W)
        type_box = self.gen_typebox(self.get_replace_type(attacker_tag), frame)
        type_box.grid(row=0, column=0, sticky=tk.E)
        x, y = self._popup_position(event)
        frame.place(x=x, y=y)
        frame.focus_set()
        self.widget_holder = frame
        frame.bind("<FocusOut>", lambda e: self.clear_widget_holder())
        self.update_idletasks()

    def gen_changing_typebox_get_to_fro(self, attacker_tag):
        """Return ``(current type, type after a sync toggle)`` for a tag."""
        if attacker_tag.startswith(self.isoFlag):
            return self.replace_types[0], self.replace_types[0]
        if attacker_tag.startswith(self.repFlag):
            sval = self.parse_child_rep_tag(attacker_tag)[1]
            if sval == self.syncTrue:
                return self.replace_types[1], self.replace_types[2]
            if sval == self.syncFalse:
                return self.replace_types[2], self.replace_types[1]
        raise ValueError(f"Unexpected tag {attacker_tag!r} in generating changing type box")

    def gen_changing_typebox_handler(self, event, attacker_tag):
        """Show the 'current --> next' sync type indicator and return its frame."""
        frame = ttk.Frame(self.master)
        r1, r2 = self.gen_changing_typebox_get_to_fro(attacker_tag)
        tk.Label(master=frame, text=r1[0], background=self.replace_type_dict[r1]).grid(row=0, column=0)
        tk.Label(master=frame, text="-->", background=self.default_opaque_color).grid(row=0, column=1)
        tk.Label(master=frame, text=r2[0], background=self.replace_type_dict[r2]).grid(row=0, column=2)
        x, y = self._popup_position(event)
        frame.place(x=x, y=y)
        frame.focus_set()
        frame.bind("<FocusOut>", lambda e: utils.del_fn(e.widget))
        self.update_idletasks()
        return frame

    def gen_changing_typebox(self, event, attacker_tag):
        """Briefly show the sync-change indicator for ``attacker_tag``."""
        frame = self.gen_changing_typebox_handler(event, attacker_tag)
        # destroy this frame specifically, so a popup opened in the meantime survives
        self.after(self.typebox_lifetime_ms, lambda: frame.winfo_exists() and frame.destroy())

    def setup_rep_bind_tag_attacker(self, attacker_tag, target_tags, parent_tag):
        """Bind the click actions and set the cosmetics of one child tag.

        :param attacker_tag: child tag we are binding to
        :param target_tags: child tags whose text an option click replaces
        :param parent_tag: parent of the children
        """
        self.tag_bind(
            attacker_tag, self.right_click_seq, lambda e: self.gen_options(e, parent_tag, target_tags, attacker_tag)
        )
        self.tag_bind(attacker_tag, self.shift_right_click_seq, lambda e: self.gen_changing_typebox(e, attacker_tag))
        self.tag_bind(attacker_tag, "<Shift-Button-1>", lambda e: self.change_sync(e, attacker_tag, parent_tag))
        underline_color = self.get_replace_type_color(attacker_tag)
        self.tag_config(
            attacker_tag, underline=True, underlinefg=underline_color, foreground=utils.make_darker(underline_color)
        )
        self.update_idletasks()

    def setup_rep_bind_tag(self, parent_tag):
        """Bind every child of ``parent_tag``.

        Synced children target all synced siblings; unsynced children target
        only themselves.
        """
        attacker_tags = self.rep_replace_tags[parent_tag]
        syncd_tags = self.get_synced_tags(attacker_tags)
        for tag in attacker_tags:
            target_tags = list(syncd_tags) if tag in syncd_tags else [tag]
            self.setup_rep_bind_tag_attacker(tag, target_tags, parent_tag)

    def append_child_tags(self, parent_tag, child_tag):
        """Register ``child_tag`` under ``parent_tag`` (no duplicates)."""
        utils.append_no_dup(child_tag, self.rep_replace_tags.setdefault(parent_tag, []))

    def add_tag_rep(self, pattern, opt_list, sync=None):
        """Tag every occurrence of ``pattern`` and offer ``opt_list`` as replacements.

        :param pattern: exact text to search for; each occurrence gets its own child tag
        :param opt_list: replacement options
        :param sync: whether the children start synced (default ``self.default_sync``)
        """
        parent_tag = self.get_parent_rep_tag(pattern)
        synctag = self.interp_sync_arg(sync)
        self.append_options(parent_tag, opt_list)
        start_id = self.get_init_rep_id(pattern)
        for i, start in enumerate(utils.return_matches(self, pattern)):
            ctag_i = self.get_child_rep_tag(start_id + i, synctag, pattern)
            self.append_child_tags(parent_tag, ctag_i)
            self.tag_add(ctag_i, start, f"{start}+{len(pattern)}c")
        self.setup_rep_bind_tag(parent_tag)

    def counter(self):
        """Return the current count and increment it (used for unnamed parents)."""
        self.count += 1
        return self.count - 1

    def add_tag_idcs(self, idcs_list, opt_list, name=None, sync=None):
        """Tag explicit spans and offer ``opt_list`` as replacements.

        :param idcs_list: flat list of 'line.col' indices, (start, end) pairs
        :param opt_list: replacement options
        :param name: parent name (an auto-incremented int if None)
        :param sync: whether the children start synced
        """
        if len(idcs_list) % 2:
            raise ValueError("idcs_list must hold (start, end) pairs")
        if name is None:
            name = str(self.counter())
        parent_tag = self.get_parent_rep_tag(name)
        synctag = self.interp_sync_arg(sync)
        self.append_options(parent_tag, opt_list)
        start_id = self.get_init_rep_id(name)
        for i in range(len(idcs_list) // 2):
            ctag_i = self.get_child_rep_tag(start_id + i, synctag, name)
            self.append_child_tags(parent_tag, ctag_i)
            self.tag_add(ctag_i, idcs_list[2 * i], idcs_list[2 * i + 1])
        self.setup_rep_bind_tag(parent_tag)


# Backwards-compatible name from the original project
paraText = ParaText
