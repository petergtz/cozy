#!/usr/bin/python

import unittest
from cozy.configuration import Configuration


class TestConfiguration(unittest.TestCase):

    def setUp(self):
#        self.volume_manager = FakeVolumeManager()
#        self.volume_manager.set_volume_mount_point('/my')
#        self.volume_manager.set_volume_uuid('1234567')

        self.config = Configuration('not-existing-cozy-unittest-configfile')
        self.assertFalse(self.config.changed())

    def tearDown(self):
        self.assertTrue(self.config.changed())


    def test_set_backup_enabled(self):
        self.assertTrue(self.config.backup_enabled is None)

        self.config.backup_enabled = True
        self.assertTrue(self.config.backup_enabled)

        self.config.backup_enabled = False
        self.assertFalse(self.config.backup_enabled)

    def test_set_data_path(self):
        self.assertTrue(self.config.data_path is None)

        self.config.data_path = '/my/data'
        self.assertEqual(self.config.data_path, '/my/data')

    def test_backup_id(self):
        self.config.backup_id = 12345
        self.assertEqual(self.config.backup_id, 12345)

        try:
            self.config.backup_id = '12345'
            self.assert_(False)
        except TypeError, e:
            self.assert_(True)


    def pending_test_set_full_backup_path(self):
        self.assertTrue(self.config.full_backup_path is None)

        self.config.backup_volume_removeable = True
        self.assertTrue(self.config.backup_volume_removeable)

        self.config.full_backup_path = '/my/test/path'

        self.assertEqual(self.config.full_backup_path, '/my/test/path')
        self.assertEqual(self.config.backup_volume_uuid, '1234567')
        self.assertEqual(self.config.relative_backup_path, 'test/path')

        self.config.full_backup_path = '/my/test/path/'

        self.assertEqual(self.config.full_backup_path, '/my/test/path')
        self.assertEqual(self.config.backup_volume_uuid, '1234567')
        self.assertEqual(self.config.relative_backup_path, 'test/path')

        self.config.backup_volume_removeable = False
        self.assertFalse(self.config.backup_volume_removeable)

        self.config.full_backup_path = '/my/test/path'

        self.assertEqual(self.config.full_backup_path, '/my/test/path')
        self.assertTrue(self.config.backup_volume_uuid is None)
        self.assertTrue(self.config.relative_backup_path is None)






if __name__ == '__main__':
    unittest.main()
