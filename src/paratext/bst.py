"""A minimal binary search tree mapping words to synonym lists (used by demos/synonym_lookup.py)."""

from __future__ import annotations


class Node:
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.left = None
        self.right = None


class BST:
    def __init__(self):
        self.root = None

    def insertBST(self, root, key, value):
        """Insert under ``root`` and return the (possibly new) subtree root.

        Inserting an existing key replaces its value.
        """
        if root is None:
            return Node(key, value)
        if key < root.key:
            root.left = self.insertBST(root.left, key, value)
        elif key > root.key:
            root.right = self.insertBST(root.right, key, value)
        else:
            root.value = value
        return root

    def insert(self, key, value):
        self.root = self.insertBST(self.root, key, value)

    def inorderBST(self, node, out):
        if node is not None:
            self.inorderBST(node.left, out)
            out.append((node.key, node.value))
            self.inorderBST(node.right, out)
        return out

    def inorder(self):
        """Return ``[(key, value), ...]`` sorted by key."""
        return self.inorderBST(self.root, [])

    def searchBST(self, root, key):
        if root is None:
            return []
        if key == root.key:
            return root.value
        if key > root.key:
            return self.searchBST(root.right, key)
        return self.searchBST(root.left, key)

    def search(self, key):
        """Return the value stored under ``key``, or ``[]`` if absent."""
        return self.searchBST(self.root, key)

    def __contains__(self, key):
        node = self.root
        while node is not None:
            if key == node.key:
                return True
            node = node.left if key < node.key else node.right
        return False

    def deleteAllComplete(self):
        """Remove every node."""
        self.root = None
