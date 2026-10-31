import importlib.util

from conftest import REPO_DIR

from paratext.bst import BST

WORDS = {
    "apple": ["fruit", "orb", "yummy"],
    "dawn": ["morning", "start"],
    "pants": ["clothes", "fashion"],
}


def make_tree():
    tree = BST()
    for key, val in WORDS.items():
        tree.insert(key, val)
    return tree


def test_constructor():
    assert BST().root is None


def test_inorder_sorted():
    assert make_tree().inorder() == sorted(WORDS.items())


def test_search():
    tree = make_tree()
    for key, val in WORDS.items():
        assert tree.search(key) == val
        assert key in tree
    assert tree.search("missing") == []
    assert "missing" not in tree


def test_insert_existing_key_replaces_value():
    tree = make_tree()
    tree.insert("dawn", ["sunrise"])
    assert tree.search("dawn") == ["sunrise"]
    assert len(tree.inorder()) == len(WORDS)


def test_delete_everything():
    tree = make_tree()
    tree.deleteAllComplete()
    assert tree.root is None
    assert tree.inorder() == []


def test_synonym_lookup_demo_loads_word_file():
    spec = importlib.util.spec_from_file_location("synonym_lookup", REPO_DIR / "demos" / "synonym_lookup.py")
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    tree = demo.load_synonyms()
    assert tree.search("chili") == ["food", "meal", "dinner"]
