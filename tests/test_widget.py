"""Tests for the original ParaText widget (need a Tk display)."""

import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

import pytest
from conftest import pump_events

from paratext import testing as event_gen
from paratext import textutils as utils
from paratext.widget import ParaText

SYNONYMS = ["concise", "terse"]
SAMPLE_LINE = "abcdefghijklmnopqrstuvwxyz"
PHRASE_CONCISE = "I will be concise. I want to be concise. I hope to one day be concise."
PHRASE_TERSE = "I will be terse. I want to be terse. I hope to one day be terse."

ISO = "_ISO_foobar"
PARENT = "_REP_foobar"
REP_S1 = "_REP_1_CNT_True_SNC_foobar"
REP_U1 = "_REP_1_CNT_False_SNC_foobar"
REP_S2 = "_REP_2_CNT_True_SNC_foobar"
REP_U2 = "_REP_2_CNT_False_SNC_foobar"


@pytest.fixture
def env(tk_root):
    ex = ParaText(tk_root)
    ex.insert("1.0", PHRASE_CONCISE + "\n")
    ex.insert("2.0", SAMPLE_LINE)
    ex.grid(column=0, row=0, padx=5, pady=5)
    pump_events(tk_root)
    # record a real click event to feed handlers that take an event
    saved = {}
    ex.bind("<Button-1>", lambda e: saved.setdefault("event", e))
    event_gen.left_click_coord(ex, (0, 0))
    ex.unbind("<Button-1>")
    return SimpleNamespace(root=tk_root, ex=ex, event=saved["event"])


def assert_bound(ex, tags):
    for t in tags:
        seqs = ex.tag_bind(t, None, None)
        for s in ex.bound_seqs:
            assert s in seqs


def test_clear_widget_holder(env):
    ex = env.ex
    assert len(ex.winfo_children()) == 0
    ex.widget_holder = tk.Label(master=ex)
    assert len(ex.winfo_children()) == 1
    ex.clear_widget_holder()
    assert len(ex.winfo_children()) == 0
    # clearing an empty holder is a no-op
    ex.clear_widget_holder()


def test_get_replace_type(env):
    ex = env.ex
    assert [ex.get_replace_type(t) for t in (ISO, REP_S1, REP_U1)] == ex.replace_types
    with pytest.raises(ValueError):
        ex.get_replace_type("not_a_tag")


def test_get_parent_rep_tag(env):
    assert env.ex.get_parent_rep_tag("test") == env.ex.repFlag + "test"


def test_get_child_rep_tag(env):
    ex = env.ex
    expected = ex.repFlag + "1" + ex.repIdFlag + "True" + ex.syncFlag + SYNONYMS[0]
    assert ex.get_child_rep_tag(1, True, SYNONYMS[0]) == expected
    assert ex.get_child_rep_tag("1", "True", SYNONYMS[0]) == expected


def test_parse_child_rep_tag(env):
    ex = env.ex
    assert ex.parse_child_rep_tag(ex.get_child_rep_tag(1, True, SYNONYMS[0])) == (1, "True", SYNONYMS[0])
    with pytest.raises(ValueError):
        ex.parse_child_rep_tag(PARENT)


def test_interp_sync_arg(env):
    ex = env.ex
    assert ex.interp_sync_arg(None) == ex.default_sync
    assert ex.interp_sync_arg(True) == ex.syncTrue
    assert ex.interp_sync_arg(False) == ex.syncFalse


def test_get_synced_tags(env):
    ex = env.ex
    assert ex.get_synced_tags([]) == []
    assert ex.get_synced_tags([REP_S1, REP_S1]) == [REP_S1, REP_S1]
    assert ex.get_synced_tags([REP_U1, REP_S1]) == [REP_S1]
    assert ex.get_synced_tags([REP_S1, REP_U1]) == [REP_S1]
    assert ex.get_synced_tags([REP_U1, REP_U1]) == []
    # iso tags are never synced (used to crash)
    assert ex.get_synced_tags([ISO, REP_S1]) == [REP_S1]


def test_change_child_tag_sync_flag(env):
    ex = env.ex
    ex.tag_add(REP_S1, "1.0", "1.5")
    ex.append_child_tags(PARENT, REP_S1)
    assert ex.rep_replace_tags[PARENT][0] == REP_S1
    ex.change_child_tag_sync_flag(REP_S1, ex.syncFalse, PARENT)
    assert ex.rep_replace_tags[PARENT][0] == REP_U1
    assert ex.tag_ranges(REP_U1)
    assert not ex.tag_ranges(REP_S1)


def test_append_options(env):
    ex = env.ex
    parent_tag = ex.get_parent_rep_tag(SYNONYMS[0])
    assert parent_tag not in ex.replace_tags
    ex.append_options(parent_tag, SYNONYMS)
    assert ex.replace_tags[parent_tag] == SYNONYMS
    ex.append_options(parent_tag, SYNONYMS)
    assert ex.replace_tags[parent_tag] == SYNONYMS


def test_get_init_and_last_rep_id(env):
    ex = env.ex
    parent_tag = ex.get_parent_rep_tag(SYNONYMS[0])
    assert ex.get_init_rep_id(SYNONYMS[0]) == 0
    ex.add_tag_rep(SYNONYMS[0], SYNONYMS)
    n_children = len(ex.rep_replace_tags[parent_tag])
    assert n_children == 3
    assert ex.get_init_rep_id(SYNONYMS[0]) == n_children
    assert ex.get_last_rep_id(SYNONYMS[0]) == n_children - 1


def test_append_child_tags(env):
    ex = env.ex
    assert PARENT not in ex.rep_replace_tags
    ex.append_child_tags(PARENT, REP_S1)
    ex.append_child_tags(PARENT, REP_S1)
    assert ex.rep_replace_tags[PARENT] == [REP_S1]
    ex.append_child_tags(PARENT, REP_U1)
    assert ex.rep_replace_tags[PARENT] == [REP_S1, REP_U1]


def test_right_click_opens_options(env):
    ex, root = env.ex, env.root
    ex.add_tag_rep(SYNONYMS[0], SYNONYMS)
    parent_tag = ex.get_parent_rep_tag(SYNONYMS[0])
    ex.update_idletasks()
    for t in ex.rep_replace_tags[parent_tag]:
        assert len(root.winfo_children()) == 1
        event_gen.click_char(ex, ex.tag_ranges(t)[0], event_gen.right_click_coord)
        assert len(root.winfo_children()) == 2
        option_list = root.winfo_children()[1]
        assert option_list.winfo_class() == "TFrame"
        option_list.destroy()


def test_second_right_click_replaces_popup(env):
    ex, root = env.ex, env.root
    ex.add_tag_rep(SYNONYMS[0], SYNONYMS)
    first, second = ex.rep_replace_tags[ex.get_parent_rep_tag(SYNONYMS[0])][:2]
    event_gen.click_char(ex, ex.tag_ranges(first)[0], event_gen.right_click_coord)
    event_gen.click_char(ex, ex.tag_ranges(second)[0], event_gen.right_click_coord)
    assert len(root.winfo_children()) == 2


def test_gen_options(env):
    ex, root = env.ex, env.root
    parent_tag = ex.get_parent_rep_tag(SYNONYMS[0])
    ex.add_tag_rep(SYNONYMS[0], SYNONYMS)
    target_tags = ex.rep_replace_tags[parent_tag]
    attacker_tag = target_tags[0]
    ex.gen_options(env.event, parent_tag, target_tags, attacker_tag)
    option_list = root.winfo_children()[1]
    assert option_list.winfo_class() == "TFrame"
    *options, typebox = option_list.winfo_children()
    assert typebox.cget("text") == ex.get_replace_type(attacker_tag)[0]
    assert [o.cget("text") for o in options] == SYNONYMS


def test_popup_offset_by_widget_position(tk_root):
    ex = ParaText(tk_root)
    ex.insert("1.0", "concise")
    ex.grid(column=0, row=0, padx=30, pady=20)
    ex.add_tag_rep("concise", SYNONYMS)
    tk_root.update()
    tag = ex.rep_replace_tags["_REP_concise"][0]
    event_gen.click_char(ex, "1.2", event_gen.right_click_coord)
    tk_root.update()
    popup = ex.widget_holder
    assert popup is not None
    bbox = ex.bbox("1.2")
    assert popup.winfo_x() == bbox[0] + ex.winfo_x()
    assert tag in ex.rep_replace_tags["_REP_concise"]


def test_new_option(env):
    ex = env.ex
    ex_parent = ex.get_parent_rep_tag(SYNONYMS[0])
    ex.add_tag_rep(SYNONYMS[0], SYNONYMS, sync=ex.syncTrue)
    assert ex.get("1.0", "end").splitlines()[0] == PHRASE_CONCISE
    ex_frame = ttk.Frame(ex.master)
    ex_opt = ex.new_option(ex_frame, ex_parent, ex.rep_replace_tags[ex_parent], 1)
    ex_opt.grid(row=0, column=1, sticky=tk.W)
    ex_frame.place(x=10, y=10)
    ex.update_idletasks()
    event_gen.left_click_coord(ex_opt, [ex_opt.winfo_x(), ex_opt.winfo_y()])
    assert ex.get("1.0", "end").splitlines()[0] == PHRASE_TERSE


def test_gen_typebox(env):
    ex = env.ex
    ex_frame = ttk.Frame(ex.master)
    for s in ex.replace_types:
        typebox = ex.gen_typebox(s, ex_frame)
        assert typebox.cget("text") == s[0]
        utils.del_fn(typebox)


def test_gen_changing_typebox_get_to_fro(env):
    ex = env.ex
    iso, synced, unsynced = ex.replace_types
    assert ex.gen_changing_typebox_get_to_fro(ISO) == (iso, iso)
    assert ex.gen_changing_typebox_get_to_fro(REP_S1) == (synced, unsynced)
    assert ex.gen_changing_typebox_get_to_fro(REP_U1) == (unsynced, synced)
    with pytest.raises(ValueError):
        ex.gen_changing_typebox_get_to_fro("not_a_tag")


def test_gen_changing_typebox_handler(env):
    ex, root = env.ex, env.root
    for t in (ISO, REP_S1, REP_U1):
        t_r1, t_r2 = ex.gen_changing_typebox_get_to_fro(t)
        assert len(root.winfo_children()) == 1
        changing_typebox = ex.gen_changing_typebox_handler(env.event, t)
        assert root.winfo_children()[1] is changing_typebox
        assert changing_typebox.winfo_class() == "TFrame"
        labels = changing_typebox.winfo_children()
        assert [w.winfo_class() for w in labels] == ["Label"] * 3
        assert [w.cget("text") for w in labels] == [t_r1[0], "-->", t_r2[0]]
        utils.del_fn(changing_typebox)


def test_changing_typebox_timer_spares_newer_popup(env):
    """The sync-indicator timer must only destroy its own frame."""
    ex, root = env.ex, env.root
    ex.typebox_lifetime_ms = 1
    ex.add_tag_rep(SYNONYMS[0], SYNONYMS)
    parent_tag = ex.get_parent_rep_tag(SYNONYMS[0])
    tag = ex.rep_replace_tags[parent_tag][0]
    ex.gen_changing_typebox(env.event, tag)
    ex.gen_options(env.event, parent_tag, [tag], tag)
    options_popup = ex.widget_holder
    root.after(20)
    root.update()
    assert options_popup.winfo_exists()


def test_change_sync_worker(env):
    ex = env.ex
    ex.append_child_tags(PARENT, REP_S1)
    ex.append_child_tags(PARENT, REP_U2)
    ex.tag_add(REP_S1, "2.0", "2.10")
    ex.tag_add(REP_U2, "2.10", "2.20")
    assert ex.rep_replace_tags[PARENT] == [REP_S1, REP_U2]
    ex.change_sync_worker(REP_S1, PARENT)
    assert ex.rep_replace_tags[PARENT] == [REP_U1, REP_U2]
    ex.change_sync_worker(REP_U2, PARENT)
    assert ex.rep_replace_tags[PARENT] == [REP_U1, REP_S2]
    ex.change_sync_worker(REP_S2, PARENT)
    assert ex.rep_replace_tags[PARENT] == [REP_U1, REP_U2]


def test_replace_text(env):
    ex = env.ex
    assert ex.get("2.0", "end-1c") == SAMPLE_LINE
    ex.replace_text("foo", ISO)
    assert ex.get("2.0", "end-1c") == SAMPLE_LINE
    ex.tag_add(ISO, "2.0", "2.10")
    ex.replace_text("foo", ISO)
    assert ex.get("2.0", "end-1c") == "foo" + SAMPLE_LINE[10:]
    ex.replace_text("foo", ISO)
    assert ex.get("2.0", "end-1c") == "foo" + SAMPLE_LINE[10:]
    ex.replace_text("bar", ISO)
    assert ex.get("2.0", "end-1c") == "bar" + SAMPLE_LINE[10:]


def test_replace_text_restores_state(env):
    ex = env.ex
    ex.tag_add(ISO, "2.0", "2.10")
    assert ex.cget("state") == tk.NORMAL
    ex.replace_text("foo", ISO)
    assert ex.cget("state") == tk.NORMAL
    ex.config(state=tk.DISABLED)
    ex.replace_text("bar", ISO)
    assert ex.cget("state") == tk.DISABLED
    assert ex.get("2.0", "end-1c") == "bar" + SAMPLE_LINE[10:]


def test_replace_texts(env):
    ex = env.ex
    assert ex.get("2.0", "end-1c") == SAMPLE_LINE
    ex.replace_texts("foo", [ISO])
    assert ex.get("2.0", "end-1c") == SAMPLE_LINE
    ex.tag_add(ISO, "2.0", "2.10")
    ex.tag_add(REP_S1, "2.10", "2.20")
    ex.tag_add(REP_U1, "2.20", "end-1c")
    ex.replace_texts("foo", [ISO])
    assert ex.get("2.0", "end-1c") == "foo" + SAMPLE_LINE[10:]
    ex.replace_texts("bar", [ISO, REP_S1])
    assert ex.get("2.0", "end-1c") == "barbar" + SAMPLE_LINE[20:]
    ex.replace_texts("foo", [ISO, REP_S1, REP_U1])
    assert ex.get("2.0", "end-1c") == "foofoofoo"
    ex.replace_texts("bar", [ISO, REP_U1])
    assert ex.get("2.0", "end-1c") == "barfoobar"


def test_add_tag_rep(env):
    ex = env.ex
    ex_parent = ex.get_parent_rep_tag(SYNONYMS[0])
    ex.add_tag_rep(SYNONYMS[0], SYNONYMS, sync=ex.syncTrue)
    assert len(ex.rep_replace_tags[ex_parent]) == 3
    assert_bound(ex, ex.rep_replace_tags[ex_parent])


def test_add_tag_rep_across_lines(tk_root):
    ex = ParaText(tk_root)
    ex.insert("1.0", "a long phrase\nanother long phrase")
    ex.add_tag_rep("long phrase", ["short"])
    starts = [str(ex.tag_ranges(t)[0]) for t in ex.rep_replace_tags["_REP_long phrase"]]
    assert starts == ["1.2", "2.8"]


def test_setup_rep_bind_tag_attacker(env):
    ex = env.ex
    ex.tag_add(REP_U1, "1.0")
    ex.setup_rep_bind_tag_attacker(REP_U1, [REP_U1], PARENT)
    assert_bound(ex, [REP_U1])


def test_middle_click_not_bound_off_macos(env):
    ex = env.ex
    ex.tag_add(REP_U1, "1.0")
    ex.setup_rep_bind_tag_attacker(REP_U1, [REP_U1], PARENT)
    middle = "<Button-3>" if ex.right_button == 2 else "<Button-2>"
    assert middle not in ex.tag_bind(REP_U1, None, None)


def test_setup_rep_bind_tag(env):
    ex = env.ex
    ex.rep_replace_tags[PARENT] = [REP_S1, REP_S2]
    ex.tag_add(REP_S1, "1.1")
    ex.tag_add(REP_S2, "1.2")
    ex.setup_rep_bind_tag(PARENT)
    assert_bound(ex, ex.rep_replace_tags[PARENT])


def test_counter(env):
    ex = env.ex
    initial = ex.count
    assert ex.counter() == initial
    assert ex.count == initial + 1


def test_add_tag_idcs(env):
    ex = env.ex
    initial = ex.count
    ex.add_tag_idcs(["2.0", "2.2"], SYNONYMS, name="ex_name")
    ex.add_tag_idcs(["2.3", "2.5"], SYNONYMS)
    ex.add_tag_idcs(["2.6", "2.8", "2.9", "2.11"], SYNONYMS)
    parents = [ex.get_parent_rep_tag(n) for n in ("ex_name", str(initial), str(initial + 1))]
    for p in parents:
        assert_bound(ex, ex.rep_replace_tags[p])
    with pytest.raises(ValueError):
        ex.add_tag_idcs(["2.0"], SYNONYMS)


def test_shift_click_toggles_sync(env):
    ex = env.ex
    ex.add_tag_rep(SYNONYMS[0], SYNONYMS, sync=True)
    parent = ex.get_parent_rep_tag(SYNONYMS[0])
    first = ex.rep_replace_tags[parent][0]
    event_gen.click_char(ex, ex.tag_ranges(first)[0], event_gen.shift_left_click_coord)
    assert ex.rep_replace_tags[parent][0] == ex.get_child_rep_tag(0, ex.syncFalse, SYNONYMS[0])
