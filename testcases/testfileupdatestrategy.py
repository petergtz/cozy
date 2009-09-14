#!/usr/bin/python

import unittest

import cozy.fileupdatestrategy


class StubbedOS:

    def __getattr__(self, name):
        pass

class StubbedLogger:

    def __getattr__(self, name):
        pass


class TestFileUpdateStrategy(unittest.TestCase):

    def setUp(self):
        cozy.fileupdatestrategy.os = StubbedOS()
        strategy = cozy.fileupdatestrategy.ChangeChangesFileUpdateStrategy('/write/path', StubbedLogger())

    def test_dummy(self):
        pass

if __name__ == '__main__':
    unittest.main()
