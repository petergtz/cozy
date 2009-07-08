#!/usr/bin/python

from __future__ import with_statement

import os.path
import ConfigParser
import dbus

import random

class VolumeManager(object):

    class VolumeNotConnectedException(Exception): pass

    def __init__(self):
        self.bus = dbus.SystemBus()
        self.manager = self.bus.get_object('org.freedesktop.Hal', '/org/freedesktop/Hal/Manager')

    def get_volume_mount_point(self, volume_uuid):
        devices = self.manager.FindDeviceStringMatch('info.udi', volume_uuid, dbus_interface='org.freedesktop.Hal.Manager')
        if len(devices) == 0:
            raise VolumeNotConnectedException('Info: The backup volume specified in the cozy configuration does not exist. '
                        'this usually means, that the volume (usb-harddisk or similar) is not '
                        ' connected to the computer')
        [device_name] = devices
        device = self.bus.get_object('org.freedesktop.Hal', device_name)
        return device.GetPropertyString('volume.mount_point', dbus_interface='org.freedesktop.Hal.Device')

    def get_volume_uuid(self, mount_point):
        while True:
            devices = self.manager.FindDeviceStringMatch('volume.mount_point', mount_point, dbus_interface='org.freedesktop.Hal.Manager')
            if len(devices) == 1:
                break
            (mount_point, tail) = os.path.split(mount_point)
        [device_name] = devices
        return device_name


class Configuration(object):

    def __init__(self, filename=None, volume_manager=None):
        if volume_manager is None:
            self.volume_manager = VolumeManager()
        else:
            self.volume_manager = volume_manager
        self.parser = ConfigParser.SafeConfigParser()
        if filename is None:
            result = self.parser.read(os.path.expanduser('~/.cozy'))
        else:
            result = self.parser.read(filename)
        if len(result) == 0:
            self.parser.add_section('globals')
            self.backup_id = random.randint(1, 100000)

        self.backup_id_changed = False
        self.backup_enabled_changed = False
        self.data_path_changed = False
        self.backup_path_changed = False
        self.backup_volume_removeable_changed = False

    def write(self):
        with open(os.path.expanduser('~/.cozy'), 'w') as fp:
            self.parser.write(fp)

    def __get_backup_enabled(self):
        try:
            return self.parser.getboolean('globals', 'backup_enabled')
        except ConfigParser.Error, e:
            return None

    def __set_backup_enabled(self, enable):
        self.backup_enabled_changed = self.backup_enabled != enable
        self.parser.set('globals', 'backup_enabled', str(enable))

#    def set_backup_enabled(self, enable):
#        self.parser.set('globals', 'backup_enabled', str(enable))
#        self.backup_enabled_changed = True

    def __get_data_path(self):
        try:
            return self.parser.get('globals', 'data_path').rstrip('/')
        except ConfigParser.Error, e:
            return None

    def __set_data_path(self, data_path):
        self.data_path_changed = self.data_path != data_path
        self.parser.set('globals', 'data_path', data_path)

    def __get_backup_volume_uuid(self):
        try:
            return self.parser.get('globals', 'backup_volume_uuid')
        except ConfigParser.Error, e:
            None

    def __set_backup_volume_uuid(self, uuid):
        self.parser.set('globals', 'backup_volume_uuid', uuid)


    def __get_relative_backup_path(self):
        try:
            return self.parser.get('globals', 'relative_backup_path').rstrip('/')
        except ConfigParser.Error, e:
            None

    def __set_relative_backup_path(self, relative_backup_path):
        self.parser.set('globals', 'relative_backup_path', relative_backup_path)

    def __set_backup_volume_removeable(self, value):
        self.backup_volume_removeable_changed = self.backup_volume_removeable != value
        self.parser.set('globals', 'backup_volume_removeable', str(value))
#        if value == True:
#            self.parser.remove_option('globals', 'backup_path')
#        else:
#            self.parser.remo

    def __get_backup_volume_removeable(self):
        try:
            return self.parser.getboolean('globals', 'backup_volume_removeable')
        except ConfigParser.Error, e:
            None


    def __get_full_backup_path(self):
        if self.backup_volume_removeable:
            if self.backup_volume_uuid is None:
                return None
            mount_point = self.volume_manager.get_volume_mount_point(self.backup_volume_uuid)
            return os.path.join(mount_point, self.relative_backup_path)
        else:
            try:
                return self.parser.get('globals', 'backup_path')
            except ConfigParser.Error, e:
                None

    def __set_full_backup_path(self, backup_path):
        self.backup_path_changed = True #self.full_backup_path != backup_path
        if self.backup_volume_removeable:
           volume_uuid = self.volume_manager.get_volume_uuid(backup_path.rstrip('/'))
           mount_path = self.volume_manager.get_volume_mount_point(volume_uuid)

           self.__set_relative_backup_path(backup_path.replace(mount_path, '', 1).lstrip('/'))
           self.__set_backup_volume_uuid(volume_uuid)
           self.parser.remove_option('globals', 'backup_path')
        else:
            self.parser.set('globals', 'backup_path', backup_path)
            self.parser.remove_option('globals', 'relative_backup_path')
            self.parser.remove_option('globals', 'backup_volume_uuid')


    def __get_backup_id(self):
        try:
            return self.parser.getint('globals', 'backup_id')
        except ConfigParser.Error, e:
            None

    def __set_backup_id(self, backup_id):
        self.backup_id_changed = self.backup_id != backup_id
        if not isinstance(backup_id, int):
            raise TypeError()
        self.parser.set('globals', 'backup_id', str(backup_id))

    def changed(self):
        return self.backup_id_changed or self.backup_enabled_changed or self.data_path_changed or self.backup_path_changed or self.backup_volume_removeable_changed

    backup_enabled = property(__get_backup_enabled, __set_backup_enabled)
    data_path = property(__get_data_path, __set_data_path)
    backup_volume_uuid = property(__get_backup_volume_uuid)
    relative_backup_path = property(__get_relative_backup_path)
    full_backup_path = property(__get_full_backup_path, __set_full_backup_path)
    backup_volume_removeable = property(__get_backup_volume_removeable, __set_backup_volume_removeable)
    backup_id = property(__get_backup_id, __set_backup_id)

if __name__ == '__main__':
    config = Configuration()
    try:
        print config.get_full_backup_path()
    except Exception, e:
        exit(e)
