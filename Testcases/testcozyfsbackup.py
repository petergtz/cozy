#!/usr/bin/python

import unittest
from cozy.cozyfsfactory import CozyFSFactory, Shell

class FakeShell(Shell):
    def call(self, cmdline):
        self.execute_string = 'Executing: ' + ' '.join(cmdline)

    def is_running(self, process):
        return self.running

    def set_is_running(self, value):
        self.running = value

    def set_return_code(self, value):
        self.rc = value

    def return_code(self, process):
        return self.rc

    def call_and_wait(self, cmdline):
        self.execute_and_wait_string = 'Executing and waiting for: ' + cmdline


class CozyFSFactoryStubbed(CozyFSFactory):

    def _CozyFSFactory__temp_dir(self):
        return '/a/tempfile/generated/dir'

    def _CozyFSFactory__make_mount_point_dir(self, mount_point):
        self.mount_point_to_make = mount_point


class TestCozyFSFactory(unittest.TestCase):

    def setUp(self):
        self.shell = FakeShell()
        self.factory = CozyFSFactoryStubbed(self.shell)
        self.expected_mount_point = '/a/tempfile/generated/dir/2009-02-14_00-31-30'
        self.expected_mount_command = 'cozyfs.py /a/tempfile/generated/dir/2009-02-14_00-31-30 -o target_dir=/the/backup/path,backup_id=12345,version=1234567890 -f'

    def tearDown(self):
        pass

    def test_mount_fail_db(self):
        self.shell.set_is_running(False)
        self.shell.set_return_code(3)
        try:
            self.factory.get_backup('/the/backup/path', 12345, 1234567890)
            self.assert_(False)
        except CozyFSFactory.MountException:
            self.assert_(True)

    def test_mount_fail_unknown(self):
        self.shell.set_is_running(False)
        self.shell.set_return_code(1)
        try:
            self.factory.get_backup('/the/backup/path', 12345, 1234567890)
            self.assert_(False)
        except CozyFSFactory.MountException:
            self.assert_(True)

    def test_mount(self):


        self.shell.set_is_running(True)
        backup = self.factory.get_backup('/the/backup/path', 12345, 1234567890)

        self.assertEqual(self.shell.execute_string, 'Executing: ' + self.expected_mount_command)
        self.assertEqual(self.factory.mount_point_to_make, self.expected_mount_point)
        self.assertEqual(backup.mount_point, self.expected_mount_point)

        backup._Backup__unmount = myfunc
        del backup

#        self.assertEqual(self.shell.execute_and_wait_string, 'Executing and waiting for: fusermount -z -u ' + self.expected_mount_point)



if __name__ == '__main__':
    unittest.main()
