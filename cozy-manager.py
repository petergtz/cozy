#!/usr/bin/python

import os
import tempfile

from cozy.mount import mount, umount, MountException
from cozy.configutils import Configuration
from dbus.mainloop.glib import DBusGMainLoop
import gobject

import logging
import sys

import sqlite3

import dbus
import dbus.service
from time import strptime, mktime, strftime, localtime

import daemon


def epoche2date(epoche):
    return strftime('%Y-%m-%d_%H-%M-%S', localtime(epoche))

def date2epoche(date):
    return int(mktime(strptime(date, '%Y-%m-%d_%H-%M-%S')))


DBFILE = 'fsdb'

class Manager(dbus.service.Object):

    class ConfigLoadException(Exception):
        pass

    def __init__(self, bus, path):
        dbus.service.Object.__init__(self, bus, path)

        try:
            self.config = Configuration()
            if not self.config.is_backup_enabled():
                sys.stderr.write("Backup is not enabled in configuration")
                sys.exit(1)
            self.src_path = self.config.get_source_path()
            self.backup_id = self.config.get_backup_id()
            if self.config.is_removeable_target_volume():
                self.target_uuid = self.config.get_target_uuid()
            else:
                self.target_uuid = ''
        except Configuration.ConfigFileIncompleteError, e:
            sys.stderr.write(str(e) + "\n")
            sys.exit(1)
        except Exception, e:
            sys.stderr.write(str(e) + "\n")
            sys.exit(2)

        self.temp_mount_dir = tempfile.mkdtemp(prefix='cozy')

        if self.config.is_removeable_target_volume():
            self.system_bus = dbus.SystemBus()
        #bus.add_signal_receiver(on_device_added, 'DeviceAdded', 'org.freedesktop.Hal.Manager', 'org.freedesktop.Hal', '/org/freedesktop/Hal/Manager')

            self.system_bus.add_signal_receiver(self.on_device_removed, 'DeviceRemoved', 'org.freedesktop.Hal.Manager', 'org.freedesktop.Hal', '/org/freedesktop/Hal/Manager')
            self.system_bus.add_signal_receiver(self.on_mount_point_set, 'PropertyModified', 'org.freedesktop.Hal.Device', 'org.freedesktop.Hal', self.target_uuid)

        self.load_config()

        if self.config.is_removeable_target_volume():
            if self.is_backup_volume_connected():
                self.removeable_volume_connected_signal()


    def load_config(self):
        try:
            self.target_path = self.config.get_full_target_path()

            self.db = sqlite3.connect(os.path.join(self.target_path, DBFILE))
            self.db.row_factory = sqlite3.Row
            self.db.text_factory = str
            return True
        except Configuration.VolumeNotConnectedException, e:
            # this exception is meant to be raised when this dbus object is intantiated. meaning, at session start
            # this means it's available on the session bus.
            return False
#            raise Manager.ConfigLoadException("Error when starting Restore-DBus (Todo:add DB errors):\n"+str(e))


    def __del__(self):
        self.close_restore_mode()

    def _backup_id_exists_in_backup(self):
        try:
            cursor = self.db.execute('select count(*) from Versions where backup_id=?', (self.backup_id,))
            if cursor.fetchone()[0] >= 1:
                return True
            else:
                return False
        except sqlite3.OperationalError, e:
            print 'Cozy Warning: Database probably does not exist'
            return False

    def _get_relative_path(self, path):
        log.debug("PARAMS: path=%s", path)
#        for src_path in self.src_paths:
        if path.startswith(self.src_path):
            rel_path = path.replace(os.path.normpath(self.src_path), '').lstrip('/')
            log.debug("returning %s", rel_path)
            return rel_path

        if path.startswith(self.temp_mount_dir):
            try:
                rel_path = path.replace(self.temp_mount_dir + '/', '').split('/', 1)[1]
            except IndexError:
                rel_path = ''
            log.debug("returning %s", rel_path)
            return rel_path

        return None

    def _get_version_of_path(self, path):
        log.debug("PARAMS: path=%s", path)
#        for src_path in self.src_paths:
        if path.startswith(self.src_path):
            log.debug("returning None")
            return None

        if path.startswith(self.temp_mount_dir):
#            path = path.replace('%20', ' ')
            result = str(int(date2epoche(path.replace(self.temp_mount_dir + '/', '').split('/', 1)[0])))
            log.debug("returning %s", result)
            return result

    def _get_versions_from_before(self, backup_id, current_version):
        if current_version is None:
            cursor = self.db.execute("select max(version) from Versions where backup_id=?", (backup_id,))
            cursor = self.db.execute("select based_on_version from Versions where backup_id=? and version=?", (backup_id, cursor.fetchone()[0]))

        else:
            cursor = self.db.execute("select based_on_version from Versions where backup_id=? and version=?", (backup_id, current_version))

        version = cursor.fetchone()[0]
        versions = []
        while version != None:
            versions.append(version)
            cursor.execute("select based_on_version from Versions where backup_id=? and version=?", (backup_id, version))
            version = cursor.fetchone()[0]

#        if len(versions) > 0:
#            del versions[0]
        return versions

    def _get_versions_from_after(self, backup_id, current_version):
        if current_version is None:
            return []
        else:
            cursor = self.db.execute("select version from Versions where backup_id=? and based_on_version=?", (backup_id, current_version))

        ret = cursor.fetchone()
        if ret is None:
            return [None]
        version = ret[0]
        versions = []
        while version != None:
            versions.append(version)
            cursor.execute("select version from Versions where backup_id=? and based_on_version=?", (backup_id, version))
            ret = cursor.fetchone()
            if ret is None:
                versions.append(None)
                if len(versions) >= 2:
                    del versions[-2]
                return versions
            version = ret[0]


        return versions

    def _is_mounted(self, version):
        if os.path.exists(os.path.join(self.temp_mount_dir, str(version))) and \
            os.path.ismount(os.path.join(self.temp_mount_dir, str(version))):
            return True

        return False

    def _mount(self, version):
        try:
            mount(self.target_path, os.path.join(self.temp_mount_dir, epoche2date(version)), self.backup_id, int(version))
        except MountException, e:
            print e


    def _rel_path_exists_in_backup(self, rel_path, version):
        return os.path.exists(os.path.join(self.temp_mount_dir, str(version), rel_path))

    def _backup_exists(self, path):
        log.debug("Params: %s", path)
        if self.config.is_removeable_target_volume() and not self.is_backup_volume_connected():
            log.debug("Backup volume is not connected. returning ''")
            return (False, '', '')
        log.debug("checking if backup_id exists in backup")
        if not self._backup_id_exists_in_backup():
            log.debug("no")
            return (False, '', '')
        log.debug("yes")

        rel_path = self._get_relative_path(path)
        if rel_path is None:
            return (False, '', '')

        current_version = self._get_version_of_path(path)
        return (True, rel_path, current_version)


    @dbus.service.method(dbus_interface='org.freedesktop.Cozy.Manager',
                         in_signature='s', out_signature='s')
    def get_previous_version_path(self, path):
        log.debug("Params: %s", path)

        (success, rel_path, current_version) = self._backup_exists(path)
        if  not success:
            return ''

        for version in self._get_versions_from_before(self.backup_id, current_version):
            if not self._is_mounted(epoche2date(version)):
                self._mount(version)
            if self._rel_path_exists_in_backup(rel_path, epoche2date(version)):
                return os.path.join(self.temp_mount_dir, epoche2date(version), rel_path)

        return ''

    @dbus.service.method(dbus_interface='org.freedesktop.Cozy.Manager',
                         in_signature='s', out_signature='s')
    def get_next_version_path(self, path):
        log.debug("Params: %s", path)

        (success, rel_path, current_version) = self._backup_exists(path)
        if  not success:
            return ''

        for version in self._get_versions_from_after(self.backup_id, current_version):
            if version is None:
                return os.path.join(self.src_path, rel_path)
            if not self._is_mounted(epoche2date(version)):
                self._mount(version)
            if self._rel_path_exists_in_backup(rel_path, epoche2date(version)):
                return os.path.join(self.temp_mount_dir, epoche2date(version), rel_path)

        return ''

    @dbus.service.method(dbus_interface='org.freedesktop.Cozy.Manager',
                         in_signature='s', out_signature='s')
    def get_newest_version_path(self, path):
        if self.config.is_removeable_target_volume() and not self.is_backup_volume_connected():
            log.debug("Backup volume is not connected. returning ''")
            return ''
        rel_path = self._get_relative_path(path)
        newest_path = os.path.join(self.src_path, rel_path)
        while not os.path.exists(newest_path):
            newest_path = os.path.dirname(newest_path)
        return newest_path


    # FIXME: this should have some kind of a reference counter
    # when the counter is zero, unmount all cozy fs and delete all directories
    @dbus.service.method(dbus_interface='org.freedesktop.Cozy.Manager',
                         in_signature='', out_signature='')
    def close_restore_mode(self):
        log.debug('')
        for dir in os.listdir(self.temp_mount_dir):
            path = os.path.join(self.temp_mount_dir, dir)
            umount(path)
        os.rmdir(self.temp_mount_dir)



    @dbus.service.signal(dbus_interface='org.freedesktop.Cozy.Manager')
    def removeable_volume_connected_signal(self):
        log.debug('')

    @dbus.service.signal(dbus_interface='org.freedesktop.Cozy.Manager')
    def removeable_volume_disconnected_signal(self):
        log.debug('')

    def on_mount_point_set(self, num_changes, properties):
    #    run_backup(mount_point + conf['rel_target_path'])
        log.debug('')
        device = self.system_bus.get_object('org.freedesktop.Hal', self.target_uuid)
        mount_point = device.GetPropertyString('volume.mount_point', dbus_interface='org.freedesktop.Hal.Device')
        if mount_point == '':
            return
        if self.load_config():
            if self.target_path != '':
                self.removeable_volume_connected_signal()

    def on_device_removed(self, udi):
        log.debug('')
        if udi == self.target_uuid:
            self.removeable_volume_disconnected_signal()

    @dbus.service.method(dbus_interface='org.freedesktop.Cozy.Manager',
                         in_signature='', out_signature='b')
    def is_backup_volume_connected(self):
        # FIXME: if we have a temporary device, then this function must do something different. see get_full_target_path
        log.debug('')

        manager = self.system_bus.get_object('org.freedesktop.Hal', '/org/freedesktop/Hal/Manager')
        devices = manager.FindDeviceStringMatch('info.udi', self.target_uuid, dbus_interface='org.freedesktop.Hal.Manager')
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

class ManagerDaemon(daemon.Daemon):
    def run(self):
        DBusGMainLoop(set_as_default=True)

        session_bus = dbus.SessionBus()

        name = dbus.service.BusName("org.freedesktop.Cozy", session_bus)
        object = Manager(session_bus, '/org/freedesktop/Cozy/Manager')

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
        else:
            print "Unknown command"
            sys.exit(2)
        sys.exit(0)
    else:
        print "usage: %s start|stop|restart" % sys.argv[0]
        sys.exit(2)
