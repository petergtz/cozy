#!/usr/bin/python

import sys

from cozy.configuration import Configuration
from cozy.backupprovider import BackupProvider
from cozy.data import Data
from cozy.locationmanager import LocationManager

import dbus
import time


if __name__ == '__main__':

    if len(sys.argv) > 2:
        exit("USAGE: " + __name__ + "[-f]; -f = start immediately backing up data")


    if len(sys.argv) == 2 and sys.argv[1] == '-f':
        answer = 'y'
    else:
        answer = raw_input("Do you really want to back up your data?")

    file = open('/tmp/cozy-backup.log', 'w')
    if answer in ['y', 'Y', 'yes']:
        try:
            config = Configuration()

            backup_provider = BackupProvider()

            system_bus = dbus.SystemBus()

            location_manager = LocationManager(config, system_bus)

            backup_location = location_manager.get_backup_location()

            if not backup_location.is_available():
                sys.exit('Backup location not available')

            backup = backup_provider.get_backup(backup_location.get_path(), config)

            data = Data(config.data_path)
            try:
                data.back_up_to(backup)
            except Data.SyncError, e:
                file.write("Error backup sync: " + str(e))

#            file.write('Bis hierher geschaaft')

            time.sleep(1)

            backup.clone_latest()
        except Exception, e:
            file.write(str(e))




    file.close()
