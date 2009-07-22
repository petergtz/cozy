from cozy.backuplocation import PathBasedBackupLocation, RemoveableBackupLocation

import dbus.service

class LocationManager(dbus.service.Object):

    def __init__(self, config, session_bus, system_bus):
        dbus.service.Object.__init__(self, session_bus, '/org/freedesktop/Cozy/LocationManager')

        if config.backup_location_type == 'absolute_path':
            self.backup_location = PathBasedBackupLocation(config.backup_location_identifier, session_bus)
        elif config.backup_location_type == 'removeable_volume':
            uuid, rel_path = config.backup_location_identifier.split(':')
            self.backup_location = RemoveableBackupLocation(uuid, rel_path, session_bus, system_bus)
        else:
            raise Exception('Unknown location type.')

    @dbus.service.method(dbus_interface='org.freedesktop.Cozy.LocationManager',
                         in_signature='', out_signature='o')
    def get_backup_location(self):
        return self.backup_location
