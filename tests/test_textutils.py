import tkinter as tk

import pytest

from paratext import textutils as u


def test_str_not():
    assert u.str_not("True") == "False"
    assert u.str_not("False") == "True"


def test_make_darker():
    # every channel is halved and zero-padded back to 2 hex digits
    assert u.make_darker("#123456", 2) == "#091a2b"
    assert u.make_darker("#FFBCBC") == "#7f5e5e"
    # lowercase input works
    assert u.make_darker("#ffbcbc") == "#7f5e5e"
    with pytest.raises(ValueError):
        u.make_darker("12346", 2)
    with pytest.raises(ValueError):
        u.make_darker("#1234", 2)


@pytest.mark.parametrize("dec_value", [0, 7, 16, 100, 255])
def test_get_short_hex(dec_value):
    assert u.get_short_hex(dec_value) == hex(dec_value)[2:]


def test_short_hex_to_dec():
    assert [u.short_hex_to_dec(h) for h in ["13", "57", "99", "ff", "FF"]] == [19, 87, 153, 255, 255]


def test_char_idx_to_ints():
    assert u.char_idx_to_ints("1.2") == (1, 2)
    assert u.char_idx_to_ints("12.34") == (12, 34)


def test_ints_to_char_idx():
    assert u.ints_to_char_idx(1, 2) == "1.2"


def test_add_to_char_idx():
    assert u.add_to_char_idx("1.2", 3, add=True) == "1.5"
    assert u.add_to_char_idx("1.2", 1, add=False) == "1.1"


def test_append_no_dup():
    items = ["a"]
    u.append_no_dup("a", items)
    u.append_no_dup("b", items)
    assert items == ["a", "b"]


def test_del_fn_ignores_none():
    u.del_fn(None)


@pytest.fixture
def text(tk_root):
    t = tk.Text(tk_root)
    t.insert("1.0", "aaa bb aaa\nsecond aaa")
    return t


def test_return_matches(text):
    # non-overlapping, and found across lines
    assert u.return_matches(text, "aa") == ["1.0", "1.7", "2.7"]
    assert u.return_matches(text, "zzz") == []
    assert u.return_matches(text, "") == []


def test_get_text_by_tagname(text):
    text.tag_add("t", "1.4", "1.6")
    assert u.get_text_by_tagname(text, "t") == "bb"
    with pytest.raises(KeyError):
        u.get_text_by_tagname(text, "missing")


@pytest.mark.parametrize("new", ["x", "longer text"])
def test_replace_tagged_text_keeps_tags(text, new):
    text.tag_add("t", "1.4", "1.6")
    text.tag_add("other", "1.4", "1.6")
    u.replace_tagged_text(text, "t", new)
    assert text.get("1.0", "1.end") == f"aaa {new} aaa"
    assert u.get_text_by_tagname(text, "t") == new
    assert u.get_text_by_tagname(text, "other") == new


def test_replace_tagged_text_single_char(text):
    text.tag_add("t", "1.4")
    u.replace_tagged_text(text, "t", "QQ")
    assert u.get_text_by_tagname(text, "t") == "QQ"


def test_replace_tagged_text_missing_tag(text):
    u.replace_tagged_text(text, "missing", "QQ")
    assert text.get("1.0", "1.end") == "aaa bb aaa"
