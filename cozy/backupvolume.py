


class BackupVolume(object):

    def __init__(self, uuid, session_bus, system_bus):
        dbus.service.Object.__init__(self, session_bus, '/org/freedesktop/Cozy/Manager')

        self.__uuid = uuid

        self.system_bus = system_bus

        self.system_bus.add_signal_receiver(self.__on_device_removed, 'DeviceRemoved', 'org.freedesktop.Hal.Manager', 'org.freedesktop.Hal', '/org/freedesktop/Hal/Manager')
        self.system_bus.add_signal_receiver(self.__on_mount_point_set, 'PropertyModified', 'org.freedesktop.Hal.Device', 'org.freedesktop.Hal', self.uuid)

        if self.is_connected():
            self.connected_signal()

    def __get_mount_point(self):
        pass

    def __get_uuid(self):
        return self.__uuid

    mount_point = property(__get_mount_point)
    uuid = property(__get_uuid)

    @dbus.service.signal(dbus_interface='org.freedesktop.Cozy.BackupVolume')
    def connected_signal(self):
        log.debug('')

    @dbus.service.signal(dbus_interface='org.freedesktop.Cozy.BackupVolume')
    def disconnected_signal(self):
        log.debug('')



    @dbus.service.method(dbus_interface='org.freedesktop.Cozy.BackupVolume',
                         in_signature='', out_signature='b')
    def is_connected(self):
        log.debug('')

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

    def __on_mount_point_set(self, num_changes, properties):
        log.debug('')
        device = self.system_bus.get_object('org.freedesktop.Hal', self.uuid)
        mount_point = device.GetPropertyString('volume.mount_point', dbus_interface='org.freedesktop.Hal.Device')
        if mount_point != '':
            self.connected_signal()

    def __on_device_removed(self, udi):
        log.debug('')
        if udi == self.uuid:
            self.disconnected_signal()

