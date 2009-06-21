#!/usr/bin/python

from __future__ import with_statement

import os.path
import ConfigParser
import dbus

import random

class Configuration:

    class VolumeNotConnectedException(Exception): pass
    class ConfigFileIncompleteError(Exception): pass

    def __init__(self):
        self.parser = ConfigParser.SafeConfigParser()
        result = self.parser.read(os.path.expanduser('~/.cozy'))
        if len(result) == 0:
            self.parser.add_section('globals')
            self.set_backup_id(random.randint(1, 100000))

        self.backup_enabled_changed = False
        self.source_path_changed = False
        self.target_path_changed = False
        self.removeable_target_volume_changed = False
#        self.make_config_complete()

#    def make_config_complete(self):
#        if not self.parser.has_option('globals', 'backup_enabled'):
#            self.parser.set('globals', 'backup_enabled', 'false')
#
#        if not self.parser.has_option('globals', 'source_path'):
#            self.parser.set('globals', 'source_path', '~')
#
#        if not self.parser.has_option('globals', 'is_removeable_target_volume'):
#            self.parser.set('globals', 'is_removeable_target_volume', 'false')
#        if not self.parser.has_option('globals', 'target_path'):
#            self.parser.set('globals', 'target_path', '~')

    def write(self):
        with open(os.path.expanduser('~/.cozy'), 'w') as fp:
            self.parser.write(fp)

    def is_backup_enabled(self):
        try:
            return self.parser.getboolean('globals', 'backup_enabled')
        except ConfigParser.Error, e:
            raise Configuration.ConfigFileIncompleteError("Configuration file incomplete. Error: " + str(e))

    def set_backup_enabled(self, enable):
        self.parser.set('globals', 'backup_enabled', str(enable))
        self.backup_enabled_changed = True

    def get_source_path(self):
        try:
            return self.parser.get('globals', 'source_path').rstrip('/')
        except ConfigParser.Error, e:
            raise Configuration.ConfigFileIncompleteError("Configuration file incomplete. Error: " + str(e))

#    def get_source_paths(self):
#        # FIXME: find a good separator
#        return self.parser.get('globals','source_paths').split(':')

    def set_source_path(self, source_path):
        self.parser.set('globals', 'source_path', source_path)
        self.source_path_changed = True

    def get_target_uuid(self):
        try:
            return self.parser.get('globals', 'target_uuid')
        except ConfigParser.Error, e:
            raise Configuration.ConfigFileIncompleteError("Configuration file incomplete. Error: " + str(e))

    def set_target_uuid(self, uuid):
        self.parser.set('globals', 'target_uuid', uuid)


    def get_relative_target_path(self):
        try:
            return self.parser.get('globals', 'relative_target_path').rstrip('/')
        except ConfigParser.Error, e:
            raise Configuration.ConfigFileIncompleteError("Configuration file incomplete. Error: " + str(e))

    def set_removeable_target_volume(self, value):
        self.parser.set('globals', 'is_removeable_target_volume', str(value))
#        if value == True:
#            self.parser.remove_option('globals', 'target_path')
#        else:
#            self.parser.remo


    def is_removeable_target_volume(self):
        try:
            return self.parser.getboolean('globals', 'is_removeable_target_volume')
        except ConfigParser.Error, e:
            raise Configuration.ConfigFileIncompleteError("Configuration file incomplete. Error: " + str(e))


    def get_full_target_path(self):
        if self.is_removeable_target_volume():
#            try:
            bus = dbus.SystemBus()
            manager = bus.get_object('org.freedesktop.Hal', '/org/freedesktop/Hal/Manager')
            devices = manager.FindDeviceStringMatch('info.udi', self.get_target_uuid(), dbus_interface='org.freedesktop.Hal.Manager')
            if len(devices) == 0:
                raise Configuration.VolumeNotConnectedException('Info: The target volume specified in the cozy configuration does not exist. '
                            'this usually means, that the volume (usb-harddisk or similar) is not '
                            ' connected to the computer')
            [device_name] = devices
            device = bus.get_object('org.freedesktop.Hal', device_name)
            mount_point = device.GetPropertyString('volume.mount_point', dbus_interface='org.freedesktop.Hal.Device')
#            except dbus.exceptions.DBusException, e:
#                print e
#                raise Exception('Error: The target volume specified in the cozy configuration does not exist. '
#                                'this usually means, that the volume (usb - harddisk or similar) is not '
#                                ' connected to the computer')

            return os.path.join(mount_point, self.parser.get('globals', 'relative_target_path'))
        else:
            try:
                return self.parser.get('globals', 'target_path')
            except ConfigParser.Error, e:
                raise Configuration.ConfigFileIncompleteError("Configuration file incomplete. Error: " + str(e))

    def set_full_target_path(self, target_path):
        if self.is_removeable_target_volume():
           mount_path = target_path.rstrip(' / ')
#           while not os.path.ismount(mount_path):
 #              (mount_path, tail) = os.path.split(mount_path)
  #         relative_path = target_path.replace(mount_path, '').lstrip(' / ')

           bus = dbus.SystemBus()
           manager = bus.get_object('org.freedesktop.Hal', '/org/freedesktop/Hal/Manager')

           while True:
               devices = manager.FindDeviceStringMatch('volume.mount_point', mount_path, dbus_interface='org.freedesktop.Hal.Manager')
               if len(devices) == 1:
                   break
               (mount_path, tail) = os.path.split(mount_path)
           [device_name] = devices
           relative_path = target_path.replace(mount_path, '', 1).lstrip(' / ')

           self.set_relative_target_path(relative_path)
           self.set_target_uuid(device_name)
           self.parser.remove_option('globals', 'target_path')
        else:
            self.parser.set('globals', 'target_path', target_path)
            self.parser.remove_option('globals', 'relative_target_path')
            self.parser.remove_option('globals', 'target_uuid')

        self.target_path_changed = True

    def set_relative_target_path(self, relative_target_path):
        self.parser.set('globals', 'relative_target_path', relative_target_path)

    def get_backup_id(self):
        try:
            return self.parser.getint('globals', 'backup_id')
        except ConfigParser.Error, e:
            raise Configuration.ConfigFileIncompleteError("Configuration file incomplete. Error: " + str(e))

    def set_backup_id(self, backup_id):
        self.parser.set('globals', 'backup_id', str(backup_id))

    def changed(self):
        return self.backup_enabled_changed or self.source_path_changed or self.target_path_changed or self.removeable_target_volume_changed

if __name__ == '__main__':
    config = Configuration()
    try:
        print config.get_full_target_path()
    except Exception, e:
        exit(e)
