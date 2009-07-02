#!/usr/bin/python

import sys

from cozy.configuration import Configuration
from cozy.backupprovider import BackupProvider


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
        backup = backup_provider.get_backup(config)

        data = Data(config)
        data.back_up_to(backup)

        backup.clone(config.full_backup_path, config.backup_id)
