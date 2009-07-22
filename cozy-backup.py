#!/usr/bin/python

import sys

from cozy.configuration import Configuration
from cozy.backupprovider import BackupProvider
#from cozy.locationprovider import LocationProvider
from cozy.data import Data

import dbus


if __name__ == '__main__':

    if len(sys.argv) > 2:
        exit("USAGE: " + __name__ + "[-f]; -f = start immediately backing up data")


    if len(sys.argv) == 2 and sys.argv[1] == '-f':
        answer = 'y'
    else:
        answer = raw_input("Do you really want to back up your data?")

    if answer in ['y', 'Y', 'yes']:
        config = Configuration()

        backup_provider = BackupProvider()

        session_bus = dbus.SessionBus()
        location_manager = session_bus.get_object('org.freedesktop.Cozy.LocationManager', '/org/freedesktop/Cozy/LocationManager')

        backup_location_object = session_bus.get_object('org.freedesktop.Cozy.LocationManager', location_manager.get_backup_location(dbus_interface='org.freedesktop.Cozy.LocationManager'))
        backup_location = dbus.Interface(backup_location_object, dbus_interface='org.freedesktop.Cozy.BackupLocation')

        if not backup_location.is_available():
            sys.exit('Backup location not available')

        backup = backup_provider.get_backup(backup_location.get_path(), config.backup_id)

        data = Data(config.data_path)
        data.back_up_to(backup)

        backup.clone_latest()
