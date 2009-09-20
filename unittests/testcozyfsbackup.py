#!/usr/bin/python

import unittest
import os.path
import cozy.cozyfsbackup

from cozy.filesystem import FileSystem
from cozy.fileupdatestrategy import ChangeChangesFileUpdateStrategy

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
    versions = [9, 8, 7, 6, 5, 4, 3, 2, 1]

    def _temp_dir(self):
        return '/a/tempfile/generated/dir'

    def _CozyFSBackup__make_mount_point_dir(self, mount_point):
        self.mount_point_to_make = mount_point

    def get_latest_version(self):
        return self.versions[0]

    def _get_base_version_of(self, version):
        if self.versions.index(version) == len(self.versions) - 1:
            return None
        return self.versions[self.versions.index(version) + 1]

    def _get_version_with(self, base_version):
        if self.versions.index(base_version) == 0:
            return None
        return self.versions[self.versions.index(base_version) - 1]

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

    def test_mount_readonly(self):

        self.subprocess.mock_process = MockProcess()
        self.subprocess.mock_process.returncode = None

        filesystem = self.backup.mount(1234567890, as_readonly=True)
        filesystem._FileSystem__unmount = stub
        filesystem._FileSystem__remove_mount_point_dir = stub

        self.expected_mount_point = '/a/tempfile/generated/dir/2009-02-14_00-31-30'
        self.expected_mount_command = COZYFS_PATH + ' /a/tempfile/generated/dir/2009-02-14_00-31-30 -o target_dir=/the/backup/path,backup_id=12345,version=1234567890,ro -f'

        self.assertEqual(self.subprocess.mock_process.execute_string, 'Executing: ' + self.expected_mount_command)
        self.assertEqual(self.backup.mount_point_to_make, self.expected_mount_point)
        self.assertEqual(filesystem.mount_point, self.expected_mount_point)
        self.assertTrue(isinstance(filesystem, FileSystem))


    def test_clone(self):
        self.backup.clone(1234567890)
        self.assertEqual(self.subprocess.execute_string, 'Executing: cozyfssnapshot.py /the/backup/path 12345 1234567890')

    def test_get_previous_versions(self):
#        versions = [9, 8, 7, 6, 5, 4, 3, 2, 1]
#
#        class DummyResult():
#            def fetchone(self):
#                return self.result
#
#        dummy_result = DummyResult()
#        dummy_result.result = [versions[0]]
#        self.backup.db.execute = lambda query, params: dummy_result

        self.assertEquals(self.backup.get_previous_versions(None), [9, 8, 7, 6, 5, 4, 3, 2, 1])
        self.assertEquals(self.backup.get_previous_versions(9), [8, 7, 6, 5, 4, 3, 2, 1])
        self.assertEquals(self.backup.get_previous_versions(6), [5, 4, 3, 2, 1])
        self.assertEquals(self.backup.get_previous_versions(1), [])

    def test_get_next_versions(self):
        self.assertEquals(self.backup.get_next_versions(None), [])
        self.assertEquals(self.backup.get_next_versions(1), [2, 3, 4, 5, 6, 7, 8, 9, None])
        self.assertEquals(self.backup.get_next_versions(5), [6, 7, 8, 9, None])
        self.assertEquals(self.backup.get_next_versions(9), [None])

    def test_get_file_update_strategy(self):
        class DummyFileSystem:
            pass
        mounted_filesystem = DummyFileSystem()
        mounted_filesystem.mount_point = 'dummy_mount_point'
        self.assert_(isinstance(self.backup.get_file_update_strategy(mounted_filesystem, None), ChangeChangesFileUpdateStrategy))



if __name__ == '__main__':
    unittest.main()
