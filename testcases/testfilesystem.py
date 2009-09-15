#!/usr/bin/python

from __future__ import with_statement

import sys
sys.path.append('/home/peter/Projects/Cozy')


import unittest
import cozy.filesystem

class MockPath:
    def __init__(self, paths):
        self.paths = paths

    def ismount(self, path):
        return True

    def exists(self, path):
        try:
            self.paths.index(path)
            return True
        except:
            return False

class MockOS:
    def __init__(self, paths=[]):
        self.paths = paths
        self.path = MockPath(self.paths)

    def rmdir(self, path):
        del self.paths[self.paths.index(path)]


    def listdir(self, path):
        return []

def stubbed_call(dummy):
    pass


class TestFileSystem(unittest.TestCase):

    def setUp(self):
        self.mock_os = MockOS(['/path/to/mountpoint', '/path/to/mountpoint/rel_path', '/path/to' ])
        cozy.filesystem.subprocess.call = stubbed_call
#
    def test_init_delete(self):
        self.filesystem = cozy.filesystem.FileSystem('/path/to/mountpoint', self.mock_os)
        del self.filesystem

    def test_enter_exit(self):
        with cozy.filesystem.FileSystem('/path/to/mountpoint', self.mock_os) as self.filesystem:
            pass
        del self.filesystem

    def test_has_relative_path(self):
        filesystem = cozy.filesystem.FileSystem('/path/to/mountpoint', self.mock_os)
        self.assertFalse(filesystem.has_relative_path('rel_path/not_existing'))
        self.assertTrue(filesystem.has_relative_path('rel_path'))

    def test_full_path_from(self):
        filesystem = cozy.filesystem.FileSystem('/path/to/mountpoint')
        self.assertEqual(filesystem.full_path_from('my/rel/path'), '/path/to/mountpoint/my/rel/path')

    def testdummy(self):
        self.assert_(True)


if __name__ == '__main__':
    unittest.main()
