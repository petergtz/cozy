#!/usr/bin/python

from __future__ import with_statement

import sys

from cozy.configuration import Configuration
from cozy.backupprovider import BackupProvider
import cozy.data
from cozy.locationmanager import LocationManager
from cozy.filesystemfunctions import FileSystemFunctions
from cozy.backup import Backup

import logging
import logging.config

import dbus
import time

import os.path


if __name__ == '__main__':

    if len(sys.argv) > 2:
        exit("USAGE: " + __name__ + "[-f]; -f = start immediately backing up data")


    if len(sys.argv) == 2 and sys.argv[1] == '-f':
        answer = 'y'
    else:
        answer = raw_input("Do you really want to back up your data?")

    if answer in ['y', 'Y', 'yes']:

        logging.config.fileConfig(os.path.expanduser('~/.cozy.logging.conf'))

        logger = logging.getLogger('cozy.backup')

        try:
            logger.info('STARTING BACKUP SESSION')
            config = Configuration()

            backup_provider = BackupProvider()

            system_bus = dbus.SystemBus()

            location_manager = LocationManager(config, system_bus)

            backup_location = location_manager.get_backup_location()

            backup = backup_provider.get_backup(backup_location.get_path(), config)
            logger.info('Version Number: %d', backup.get_latest_version())

            with backup.mount_latest() as filesystem:

                filesystem_functions = FileSystemFunctions(filesystem.mount_point, logger)

                logger.info('Backing up data from ' + config.data_path + ' to ' + filesystem.mount_point + ': ')
                cozy.data.sync(config.data_path, filesystem.mount_point, filesystem_functions)

            time.sleep(1)

            backup.clone_latest()

            logger.info('ENDING BACKUP SESSION properly with new version number: %d', backup.get_latest_version())

        except Backup.MountException, e:
            logger.error(str(e))
        except Exception, e:
#            logger.error(str(e))
            logger.exception(str(e))
#            raise
