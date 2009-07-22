#!/usr/bin/python

import unittest
from cozy.cozyfsbackup import CozyFSBackup, Shell
from cozy.filesystem import FileSystem

class FakeShell(Shell):
    def call(self, cmdline):
        self.execute_string = 'Executing: ' + ' '.join(cmdline)

    def is_running(self, process):
        return self.running

    def return_code(self, process):
        return self.rc


class CozyFSBackupStubbed(CozyFSBackup):

    def _CozyFSBackup__temp_dir(self):
        return '/a/tempfile/generated/dir'

    def _CozyFSBackup__make_mount_point_dir(self, mount_point):
        self.mount_point_to_make = mount_point

def stub(dummy_self=None):
    pass


class MockCursor(object):


    def fetchone(self):
        return self.fetchone_result

class FakeDB(object):

    def __init__(self):
        self.mock_cursor = MockCursor()


    def execute(self, query, *args):
        return self.mock_cursor

    def close(self):
        pass

    def set_fetchone_result(self, value):
        self.mock_cursor.fetchone_result = value


class FakeDBFactory(object):

    Row = 'Row'
    db = FakeDB()

    @staticmethod
    def connect(filename):
        return FakeDBFactory.db

    @staticmethod
    def set_fetchone_result(value):
        FakeDBFactory.db.set_fetchone_result(value)



class TestCozyFSBackup(unittest.TestCase):

    def setUp(self):
        self.shell = FakeShell()
        self.fake_db_factory = FakeDBFactory
        self.backup = CozyFSBackupStubbed('/the/backup/path', 12345 , self.shell, self.fake_db_factory)
        self.expected_mount_point = '/a/tempfile/generated/dir/2009-02-14_00-31-30'
        self.expected_mount_command = 'cozyfs.py /a/tempfile/generated/dir/2009-02-14_00-31-30 -o target_dir=/the/backup/path,backup_id=12345,version=1234567890 -f'

    def tearDown(self):
        pass

    def test_mount_fail_db(self):
        self.shell.running = False
        self.shell.rc = 3
        try:
            self.backup.mount(1234567890)
            self.assert_(False)
        except CozyFSBackup.MountException:
            self.assert_(True)

    def test_mount_fail_unknown(self):
        self.shell.running = False
        self.shell.rc = 1
        try:
            self.backup.mount(1234567890)
            self.assert_(False)
        except CozyFSBackup.MountException:
            self.assert_(True)

    def test_mount(self):

        self.shell.running = True
        filesystem = self.backup.mount(1234567890)

        self.assertEqual(self.shell.execute_string, 'Executing: ' + self.expected_mount_command)
        self.assertEqual(self.backup.mount_point_to_make, self.expected_mount_point)
        self.assertEqual(filesystem.mount_point, self.expected_mount_point)
        self.assertTrue(isinstance(filesystem, FileSystem))

        filesystem._FileSystem__unmount = stub
        filesystem._FileSystem__remove_mount_point_dir = stub

    def pending_test_clone(self):
        self.backup.clone(version)

    def test_get_previous_versions(self):
        self.fake_db_factory.set_fetchone_result(None)
        try:
            self.backup.get_previous_versions(None)
            self.assert_(False)
        except:
            self.assert_(True)

        try:
            self.fake_db_factory.set_fetchone_result([None])
            self.backup.get_previous_versions(None)
            self.assert_(False)
        except:
            self.assert_(True)





if __name__ == '__main__':
    unittest.main()
