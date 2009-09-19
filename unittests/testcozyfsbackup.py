#!/usr/bin/python

import unittest
import os.path
import cozy.cozyfsbackup

from cozy.filesystem import FileSystem

class MockSubprocessModule:
    PIPE = 'pipe_dummy'

    def call(self, cmd):
        self.execute_string = 'Executing: ' + ' '.join(cmd)
        return self.returncode

    def Popen(self, cmd, stderr='std_dummy', stdout='std_dummy'):
        self.mock_process.execute_string = 'Executing: ' + ' '.join(cmd)
        return self.mock_process

class MockProcess:
    def poll(self):
        return self.returncode

    def communicate(self):
        return ('stderror', 'stdout')


class CozyFSBackupStubbed(cozy.cozyfsbackup.CozyFSBackup):

    def _temp_dir(self):
        return '/a/tempfile/generated/dir'

    def _CozyFSBackup__make_mount_point_dir(self, mount_point):
        self.mount_point_to_make = mount_point

def stub(*args):
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

#BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#COZYFS_PATH = os.path.join(BASE_DIR, 'cozyfs', 'cozyfs.py')
COZYFS_PATH = 'cozyfs.py'

class TestCozyFSBackup(unittest.TestCase):

    def setUp(self):
        cozy.cozyfsbackup.sleep = stub
        self.fake_db_factory = FakeDBFactory
        self.subprocess = MockSubprocessModule()
        self.subprocess.returncode = 0

        self.backup = CozyFSBackupStubbed('/the/backup/path', 12345 , self.subprocess, self.fake_db_factory)

    def test_mount_fail_db(self):
        self.subprocess.mock_process = MockProcess()
        self.subprocess.mock_process.returncode = 3

        self.failUnlessRaises(cozy.cozyfsbackup.CozyFSBackup.MountException, self.backup.mount, 1234567890)

    def test_mount_fail_unknown(self):
        self.subprocess.mock_process = MockProcess()
        self.subprocess.mock_process.returncode = 1
        self.failUnlessRaises(cozy.cozyfsbackup.CozyFSBackup.MountException, self.backup.mount, 1234567890)

    def test_mount(self):

        self.subprocess.mock_process = MockProcess()
        self.subprocess.mock_process.returncode = None

        filesystem = self.backup.mount(1234567890)
        filesystem._FileSystem__unmount = stub
        filesystem._FileSystem__remove_mount_point_dir = stub

        self.expected_mount_point = '/a/tempfile/generated/dir/2009-02-14_00-31-30'
        self.expected_mount_command = COZYFS_PATH + ' /a/tempfile/generated/dir/2009-02-14_00-31-30 -o target_dir=/the/backup/path,backup_id=12345,version=1234567890 -f'

        self.assertEqual(self.subprocess.mock_process.execute_string, 'Executing: ' + self.expected_mount_command)
        self.assertEqual(self.backup.mount_point_to_make, self.expected_mount_point)
        self.assertEqual(filesystem.mount_point, self.expected_mount_point)
        self.assertTrue(isinstance(filesystem, FileSystem))


    def test_clone(self):
        self.backup.clone(1234567890)
        self.assertEqual(self.subprocess.execute_string, 'Executing: cozyfssnapshot.py /the/backup/path 12345 1234567890')

    def test_get_previous_versions(self):
        self.fake_db_factory.set_fetchone_result(None)
        self.assertRaises(Exception, self.backup.get_previous_versions, None)
        self.fake_db_factory.set_fetchone_result([None])
        self.assertRaises(Exception, self.backup.get_previous_versions, None)



if __name__ == '__main__':
    unittest.main()
