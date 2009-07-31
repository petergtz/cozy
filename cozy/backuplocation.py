#import dbus.service
import os.path
import dbus


#from utils.md5sum import md5sum_from_string

class BackupLocation(object):#dbus.service.Object):

#    def __init__(self, session_bus, object_path):
#        dbus.service.Object.__init__(self, session_bus, object_path)

    def get_path(self):
        pass

    def is_available(self):
        pass

    def available(self):
        pass

    def unavailable(self):
        pass

    def connect_to_signal(self, signal_name, handler_function):
        pass

    def serialize(self):
        pass


class RemoveableBackupLocation(BackupLocation):

#    def __init__(self, uuid, rel_path, session_bus, system_bus):
    def __init__(self, uuid=None, rel_path=None, arbitrary_path=None, system_bus=None):
#        BackupLocation.__init__(self, session_bus, '/org/freedesktop/Cozy/BackupLocations/' + md5sum_from_string(uuid + ':' + rel_path))
        if system_bus is None:
            self.system_bus = dbus.SystemBus()
        else:
            self.system_bus = system_bus

        if arbitrary_path is not None:
            self.uuid, self.rel_path = self.__get_identifiers_from(arbitrary_path)
        else:
            if uuid is None or rel_path is None:
                raise Exception('uuid or rel_path not specified')
            self.uuid = uuid
            self.rel_path = rel_path

        self.handlers = dict()
        self.system_bus.add_signal_receiver(self.__on_device_removed, 'DeviceRemoved', 'org.freedesktop.Hal.Manager', 'org.freedesktop.Hal', '/org/freedesktop/Hal/Manager')
        self.system_bus.add_signal_receiver(self.__on_mount_point_set, 'PropertyModified', 'org.freedesktop.Hal.Device', 'org.freedesktop.Hal', self.uuid)

    def __get_identifiers_from(self, arbitrary_path):
        mount_path = arbitrary_path
        manager = self.system_bus.get_object('org.freedesktop.Hal', '/org/freedesktop/Hal/Manager')
        while True:
            devices = manager.FindDeviceStringMatch('volume.mount_point', mount_path, dbus_interface='org.freedesktop.Hal.Manager')
            if len(devices) == 1:
                break
            (mount_path, tail) = os.path.split(mount_path)
        [device_name] = devices
        relative_path = arbitrary_path.replace(mount_path, '', 1).lstrip('/')
        return device_name, relative_path

    def serialize(self):
        return self.uuid + ':' + self.rel_path

#    @dbus.service.method(dbus_interface='org.freedesktop.Cozy.BackupLocation',
#                         in_signature='', out_signature='s')
    def get_path(self):
        if not self.is_available():
            raise Exception('Backup locaiton is not available')

        manager = self.system_bus.get_object('org.freedesktop.Hal', '/org/freedesktop/Hal/Manager')
        devices = manager.FindDeviceStringMatch('info.udi', self.uuid, dbus_interface='org.freedesktop.Hal.Manager')
        [device_name] = devices
        device = self.system_bus.get_object('org.freedesktop.Hal', device_name)
        mount_point = device.GetPropertyString('volume.mount_point', dbus_interface='org.freedesktop.Hal.Device')

        return os.path.join(mount_point, self.rel_path)

#    @dbus.service.method(dbus_interface='org.freedesktop.Cozy.BackupLocation',
#                         in_signature='', out_signature='b')
    def is_available(self):
        manager = self.system_bus.get_object('org.freedesktop.Hal', '/org/freedesktop/Hal/Manager')
        devices = manager.FindDeviceStringMatch('info.udi', self.uuid, dbus_interface='org.freedesktop.Hal.Manager')
        if len(devices) == 0:
            return False
        [device_name] = devices
        device = self.system_bus.get_object('org.freedesktop.Hal', device_name)
        mount_point = device.GetPropertyString('volume.mount_point', dbus_interface='org.freedesktop.Hal.Device')
        if mount_point == '':
            return False

        return True

    def connect_to_signal(self, signal_name, handler_function):
        if not self.handlers.has_key(signal_name):
            self.handlers[signal_name] = []
        self.handlers[signal_name].append(handler_function)

#    @dbus.service.signal(dbus_interface='org.freedesktop.Cozy.BackupLocation')
    def available(self):
        if self.handlers.has_key('available'):
            for func in self.handlers['available']:
                func()

#    @dbus.service.signal(dbus_interface='org.freedesktop.Cozy.BackupLocation')
    def unavailable(self):
        if self.handlers.has_key('unavailable'):
            for func in self.handlers['unavailable']:
                func()

    def __on_mount_point_set(self, num_changes, properties):
        device = self.system_bus.get_object('org.freedesktop.Hal', self.uuid)
        mount_point = device.GetPropertyString('volume.mount_point', dbus_interface='org.freedesktop.Hal.Device')
        if mount_point != '':
            self.available()

    def __on_device_removed(self, udi):
        if udi == self.uuid:
            self.unavailable()

class PathBasedBackupLocation(BackupLocation):
#    def __init__(self, path, session_bus):
    def __init__(self, path):
#        BackupLocation.__init__(self, session_bus, '/org/freedesktop/Cozy/BackupLocations/' + md5sum_from_string(path))
        self.path = path


#    @dbus.service.method(dbus_interface='org.freedesktop.Cozy.BackupLocation',
#                         in_signature='', out_signature='s')
    def get_path(self):
        return self.path

#    @dbus.service.method(dbus_interface='org.freedesktop.Cozy.BackupLocation',
#                         in_signature='', out_signature='b')
    def is_available(self):
        return os.path.lexists(self.path)

    def serialize(self):
        return self.path
