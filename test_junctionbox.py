"""
Unit tests for junctionbox
@author Alan M Jackson & Bjoern Hassler
"""

import unittest
from junctionbox import *

class Test(unittest.TestCase):

    def test_format_time(self):

        self.assertTrue(format_time(0) == "00:00")
        self.assertTrue(format_time(1) == "00:01")
        self.assertTrue(format_time(60) == "01:00")
        self.assertTrue(format_time(121) == "02:01")
        self.assertTrue(format_time(-1) == "--:--")
        self.assertTrue(format_time(-100) == "--:--")
        self.assertTrue(format_time(None) == "--:--")
        self.assertTrue(format_time(3600) == "1:00:00")
        self.assertTrue(format_time(3661) == "1:01:01")
        self.assertTrue(format_time(36000) == "10:00:00")
        self.assertTrue(format_time(86400) == "1:00:00:00")
        self.assertTrue(format_time(31536000) == "365:00:00:00")



if __name__=="__main__":
    unittest.main()