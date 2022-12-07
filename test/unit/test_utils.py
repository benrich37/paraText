import unittest
import os
import sys
import random
sys.path.append("../../libs/")
import utils as u

class TestUtils(unittest.TestCase):
    
    def test_make_darker(self):
        # test that string returned has been changed accordingly
        hex_color = '#123456'
        dark_fac = 2
        expected_hex = '#91a2b'
        test_hex = u.make_darker(hex_color, dark_fac)
        
        # positive test
        self.assertEqual(test_hex, expected_hex)
        
        # negative test
        self.assertNotEqual(test_hex, hex_color)
        
        # error handling: handles invalid hex code being parsed
        # invalid code: doesn't start with #
        with self.assertRaises(ValueError):
            u.make_darker('12346', dark_fac)
    
    def test_get_short_hex(self):
        # create data for tests
        dec_value = random.randint(0,100)
        hex_value = str(hex(dec_value))
        short_hex = hex_value[hex_value.index('x') + 1:]
        test_short_hex = u.get_short_hex(dec_value)

        # positive test
        self.assertEqual(test_short_hex, short_hex)
        
        # negative test
        self.assertNotEqual(test_short_hex, hex(255))

    def test_short_hex_to_dec(self):
        hex_vals = ['13', '57', '99']
        dec_vals = [19, 87, 153]

        # positive test
        test_dec = []
        for he in hex_vals:
            test_dec.append(u.short_hex_to_dec(he))
        
        self.assertEqual(dec_vals, test_dec)
        
        # negative test
        self.assertNotEqual(test_dec, hex_vals)

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

    def test_add_to_char_idx(self):
        # positive test for adding
        expected_add = ('1.5')
        test_add = u.add_to_char_idx('1.2', 3, add=True)
        self.assertEqual(expected_add, test_add)
        
        # negative test for adding
        self.assertNotEqual('1.2', test_add)
        
        # positive test for subtracting
        expected_sub = ('1.1')
        test_sub = u.add_to_char_idx('1.2', 1, add=False)
        self.assertEqual(expected_sub, test_sub)
        
        # negative test for subtracting
        self.assertNotEqual('1.2', test_sub)
