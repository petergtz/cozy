#!/usr/bin/python

import unittest
from cozy.data import Data
from cozy.backup import Backup


class ConfigurationMock(object):
    def __init__(self):
        self.data_path = '/data/path'
        self.full_backup_path = '/full/backup/path'
        self.backup_id = 12345


class BackupMock(Backup):
    def __init__(self):
        self.mount_latest_called = False

    def mount_latest(self):
       self.mount_latest_called = True
       return FileSystemMock()


class FileSystemMock(object):

    def __init__(self):
        self.sync_with_called = False
        self.errors = []
        self.mount_point = '/the/mount/point'


class TestData(unittest.TestCase):

    def setUp(self):
        self.config = ConfigurationMock()
        self.backup = BackupMock()

    def tearDown(self):
        pass

    def test_back_up_to(self):
        self.data = Data(self.config)
        self.data.back_up_to(self.backup)
        self.assert_(self.backup.mount_latest_called)

    def test_data_path_not_configured(self):
        self.data_path = None
        try:
            self.data = Data(self.config)
            self.data.back_up_to(backup)
            self.assert_(False)
        except:
            self.assert_(True)



if __name__ == '__main__':
    unittest.main()
