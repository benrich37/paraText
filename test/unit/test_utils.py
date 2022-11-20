import unittest
import os
import sys
sys.path.append("../../libs/")
import utils as u

class TestUtils(unittest.TestCase):
#     @classmethod
#     def setUpClass(cls):
#         # create temporary data structures
    
#     @classmethod
#     def tearDownClass(cls):
#         # kill temporary data structures
    
    def test_char_idx_to_ints(self):
        idxs = [1.2]
        idx1, idx2 = u.char_idx_to_ints('1.2')
        
        # positive test
        self.assertEqual(idx1, 1)
        self.assertEqual(idx2, 2)
        
        # negative test
        self.assertNotEqual(idx1, 4)
        self.assertNotEqual(idx2, 5)

    def test_ints_to_char_idx(self):
        expected = ('1.2')
        test = u.ints_to_char_idx(1, 2)

        # positive test
        self.assertEqual(expected, test)
        
        # negative test
        self.assertNotEqual('7.8', test)
