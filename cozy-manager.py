#!/usr/bin/python

import os

from cozy.backupprovider import BackupProvider
from dbus.mainloop.glib import DBusGMainLoop

import gobject

import logging
import sys

import dbus
import dbus.service

import cozy.configuration
import utils.daemon

class Manager(dbus.service.Object):

    def __init__(self, config, backup_provider, session_bus, system_bus):
        dbus.service.Object.__init__(self, session_bus, '/org/freedesktop/Cozy/Manager')

        self.config = config
        if not self.config.backup_enabled:
            sys.stderr.write("Backup is not enabled in configuration")
            sys.exit(1)

        self.filesystems = dict()
        self.backup_provider = backup_provider
        self.system_bus = dbus.SystemBus()

        if self.config.backup_volume_removeable:
            self.system_bus.add_signal_receiver(self.on_device_removed, 'DeviceRemoved', 'org.freedesktop.Hal.Manager', 'org.freedesktop.Hal', '/org/freedesktop/Hal/Manager')
            self.system_bus.add_signal_receiver(self.on_mount_point_set, 'PropertyModified', 'org.freedesktop.Hal.Device', 'org.freedesktop.Hal', self.config.backup_volume_uuid)

            if self.is_backup_volume_connected():
                self.removeable_volume_connected_signal()
        else:
            self.backup = self.backup_provider.get_backup(self.config)


    def __del__(self):
        self.close_restore_mode()

    def __get_version_from(self, path):
        if path.startswith(self.config.data_path):
            return None
        else:
            for backup_version, filesystem in self.filesystems.items():
                if path.startswith(filesystem.mount_point):
                    return backup_version
        return (-1)

    def __get_relative_path_of(self, path):
        if path.startswith(self.config.data_path):
            path = path.replace(self.config.data_path, '')
            return path.lstrip('/')
        else:
            for backup_version, filesystem in self.filesystems.items():
                if path.startswith(filesystem.mount_point):
                    path = path.replace(filesystem.mount_point , '')
                    return path.lstrip('/')
        return (-1)

    @dbus.service.method(dbus_interface='org.freedesktop.Cozy.Manager',
                         in_signature='s', out_signature='s')
    def get_previous_version_path(self, path):
        log.debug("Params: %s", path)

        current_version = self.__get_version_from(path)
        if current_version == -1:
            return ''

        relative_path = self.__get_relative_path_of(path)

        for backup_version in self.backup.get_previous_versions(current_version):
            if self.filesystems.has_key(backup_version):
                filesystem = self.filesystems[backup_version]
            else:
                filesystem = self.backup.mount(backup_version)
                self.filesystems[backup_version] = filesystem
            if filesystem.has_relative_path(relative_path):
                return filesystem.full_path(relative_path)

        return ''

    @dbus.service.method(dbus_interface='org.freedesktop.Cozy.Manager',
                         in_signature='s', out_signature='s')
    def get_next_version_path(self, path):
        log.debug("Params: %s", path)

        current_version = self.__get_version_from(path)
        if current_version == -1:
            return ''

        relative_path = self.__get_relative_path_of(path)

        for backup_version in self.backup.get_next_versions(current_version):
            if backup_version is None:
                return os.path.join(self.config.data_path, relative_path)
            if self.filesystems.has_key(backup_version):
                filesystem = self.filesystems[backup_version]
            else:
                filesystem = self.backup.mount(backup_version)
                self.filesystems[backup_version] = filesystem
            if filesystem.has_relative_path(relative_path):
                return filesystem.full_path(relative_path)

        return ''

    @dbus.service.method(dbus_interface='org.freedesktop.Cozy.Manager',
                         in_signature='s', out_signature='s')
    def get_newest_version_path(self, path):
        relative_path = self.__get_relative_path_of(path)
        newest_path = os.path.join(self.config.data_path, relative_path)
        return newest_path


    # FIXME: this should have some kind of a reference counter
    # when the counter is zero, unmount all cozy fs and delete all directories
    @dbus.service.method(dbus_interface='org.freedesktop.Cozy.Manager',
                         in_signature='', out_signature='')
    def close_restore_mode(self):
        log.debug('')
        self.__unmount_filesystems()


    @dbus.service.signal(dbus_interface='org.freedesktop.Cozy.Manager')
    def removeable_volume_connected_signal(self):
        log.debug('')
        self.backup = self.backup_provider.get_backup(self.config)

    @dbus.service.signal(dbus_interface='org.freedesktop.Cozy.Manager')
    def removeable_volume_disconnected_signal(self):
        log.debug('')
        self.__unmount_filesystems()
        del self.backup

    def on_mount_point_set(self, num_changes, properties):
        log.debug('')
        device = self.system_bus.get_object('org.freedesktop.Hal', self.target_uuid)
        mount_point = device.GetPropertyString('volume.mount_point', dbus_interface='org.freedesktop.Hal.Device')
        if mount_point == '':
            return
        self.removeable_volume_connected_signal()

    def __unmount_filesystems(self):
        self.filesystems.clear()

    def on_device_removed(self, udi):
        log.debug('')
        if udi == self.config.backup_volume_uuid:
            self.removeable_volume_disconnected_signal()


    @dbus.service.method(dbus_interface='org.freedesktop.Cozy.Manager',
                         in_signature='', out_signature='b')
    def is_backup_volume_connected(self):
        # FIXME: if we have a temporary device, then this function must do something different. see get_full_target_path
        log.debug('')

        manager = self.system_bus.get_object('org.freedesktop.Hal', '/org/freedesktop/Hal/Manager')
        devices = manager.FindDeviceStringMatch('info.udi', self.config.backup_volume_uuid, dbus_interface='org.freedesktop.Hal.Manager')
        if len(devices) == 0:
            return False
        [device_name] = devices
        device = self.system_bus.get_object('org.freedesktop.Hal', device_name)
        mount_point = device.GetPropertyString('volume.mount_point', dbus_interface='org.freedesktop.Hal.Device')
        if mount_point == '':
            return False

        return True



log = logging.getLogger('restore-dbus')
log.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('  Line %(lineno)-3d %(levelname)-7s Fnc: %(funcName)-10s: %(message)s'))
log.addHandler(handler)

class ManagerDaemon(utils.daemon.Daemon):
    def run(self):

        DBusGMainLoop(set_as_default=True)

        config = cozy.configuration.Configuration()

        backup_provider = BackupProvider()

        session_bus = dbus.SessionBus()
        system_bus = dbus.SystemBus()

        name = dbus.service.BusName("org.freedesktop.Cozy", session_bus)
        object = Manager(config, backup_provider, session_bus, system_bus)

        mainloop = gobject.MainLoop()
        mainloop.run()


if __name__ == '__main__':
    daemon = ManagerDaemon('/tmp/cozy-manager.pid', stdout='/tmp/cozy-manager-stdout', stderr='/tmp/cozy-manager-stderr')
    if len(sys.argv) == 2:
        if 'start' == sys.argv[1]:
            daemon.start()
        elif 'stop' == sys.argv[1]:
            daemon.stop()
        elif 'restart' == sys.argv[1]:
            daemon.restart()
        elif 'nodaemon' == sys.argv[1]:
            daemon.run()
        else:
            print "Unknown command"
            sys.exit(2)
        sys.exit(0)
    else:
        print "usage: %s start|stop|restart" % sys.argv[0]
        sys.exit(2)
