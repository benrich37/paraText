import sys
import unittest
from BSTTree import *
​
class BSTtest(unittest.TestCase):
    def constructor(self):
        test_bst = BST()
        self.assertEqual(None, test_bst.root)
    def BSTinsert(self):
        words = {'apple': ['fruit', 'orb', 'yummy'],
                'dawn': ['morning', 'start'],
                'pants': ['clothes', 'fashion']}
        test_bst = BST()
        
        for key, val in words.items():
            test_bst.insert(key, val)
        self.assertEqual(None, test_bst.inorder())
    
    def searchFunction(self):
        words = {'apple': ['fruit', 'orb', 'yummy'],
                'dawn': ['morning', 'start'],
                'pants': ['clothes', 'fashion']}
        test_bst = BST()
        
        for key, val in words.items():
            test_bst.insert(key, val)
        
        self.assertEqual(['fruit', 'orb', 'yummy'], test_bst.search('apple'))
        self.assertEqual(['morning', 'start'], test_bst.search('dawn'))
        self.assertEqual(['clothes', 'fashion'],test_bst.search('pants'))
    
    def deleteEverything(self):
        words = {'apple': ['fruit', 'orb', 'yummy'],
                'dawn': ['morning', 'start'],
                'pants': ['clothes', 'fashion']}
        test_bst = BST()
        
        for key, val in words.items():
            test_bst.insert(key, val)
        
        self.assertEqual(None,test_bst.deleteAllComplete())
        
        
if __name__ =="__main__":
    bst_test = BSTtest()
    print(bst_test.constructor()) 
    print(bst_test.BSTinsert()) 
    print(bst_test.searchFunction())
    print(bst_test.deleteEverything())
