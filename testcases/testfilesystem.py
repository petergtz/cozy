#!/usr/bin/python

from __future__ import with_statement

import unittest
from pymock import *
import cozy.filesystem


class MockOS:
    def __init__(self, paths=[]):
        self.paths = paths

    def rmdir(self, path):
        del self.paths[self.paths.index(path)]

    def ismount(self, path):
        return True

    def exists(self, path):
        try:
            self.paths.index(path)
            return True
        except:
            return False

    def listdir(self, path):
        return []

def stubbed_call(dummy):
    pass


class TestFileSystem(unittest.TestCase):

    def setUp(self):
        self.mock_os = MockOS(['/path/to/mountpoint', '/path/to/mountpoint/rel_path', '/path/to' ])
        cozy.filesystem.os.rmdir = self.mock_os.rmdir
        cozy.filesystem.os.listdir = self.mock_os.listdir
        cozy.filesystem.os.path.ismount = self.mock_os.ismount
        cozy.filesystem.os.path.exists = self.mock_os.exists
        cozy.filesystem.subprocess.call = stubbed_call

    def test_init_delete(self):
        self.filesystem = cozy.filesystem.FileSystem('/path/to/mountpoint')
        del self.filesystem

    def test_enter_exit(self):
        with cozy.filesystem.FileSystem('/path/to/mountpoint') as self.filesystem:
            pass
        del self.filesystem

    def test_has_relative_path(self):
        filesystem = cozy.filesystem.FileSystem('/path/to/mountpoint')
        self.assertFalse(filesystem.has_relative_path('rel_path/not_existing'))
        self.assertTrue(filesystem.has_relative_path('rel_path'))

    def test_full_path_from(self):
        filesystem = cozy.filesystem.FileSystem('/path/to/mountpoint')
        self.assertEqual(filesystem.full_path_from('my/rel/path'), '/path/to/mountpoint/my/rel/path')


if __name__ == '__main__':
    unittest.main()
