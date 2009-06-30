#!/usr/bin/python

import unittest
from cozy.configuration import Configuration, VolumeManager

class FakeVolumeManager(VolumeManager):

    def __init__(self):
        pass

    def set_volume_mount_point(self, mount_point):
        self.mount_point = mount_point

    def get_volume_mount_point(self, volume_uuid):
        return self.mount_point

    def set_volume_uuid(self, volume_uuid):
        self.volume_uuid = volume_uuid

    def get_volume_uuid(self, mount_point):
        return self.volume_uuid


class TestConfiguration(unittest.TestCase):

    def setUp(self):
        self.volume_manager = FakeVolumeManager()
        self.volume_manager.set_volume_mount_point('/my')
        self.volume_manager.set_volume_uuid('1234567')

        self.config = Configuration('not-existing-cozy-unittest-configfile', self.volume_manager)
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


    def test_set_full_backup_path(self):
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





class TestVolumeManager(unittest.TestCase):

    def setUp(self):
        self.manager = VolumeManager()

    def test_get_volume_mount_point(self):
        self.assertEqual(self.manager.get_volume_mount_point('/org/freedesktop/Hal/devices/volume_uuid_64887a2f_343c_42a0_941f_b7aa42d08088'), '/')

    def test_get_volume_uuid(self):
        self.assertEqual(self.manager.get_volume_uuid('/etc'), '/org/freedesktop/Hal/devices/volume_uuid_64887a2f_343c_42a0_941f_b7aa42d08088')

if __name__ == '__main__':
    unittest.main()
