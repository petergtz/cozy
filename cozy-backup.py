#!/usr/bin/python

import sys

from cozy.configuration import Configuration
from cozy.backupprovider import BackupProvider
from cozy.backup import Backup

class Data(object):

    def __init__(self, config):
        self.config = config
        if self.config.data_path is None:
            sys.exit('Error: Aborting doing backup because location of data is not configured.')

    def back_up_to(self, backup):

        if self.config.full_backup_path is None or self.config.backup_id is None:
            exit('Error: Aborting doing backup because getting the backup configuration failed')
        try:
            filesystem = backup.mount_latest(config.full_backup_path, config.backup_id)

            errors = filesystem.sync_with(config.data_path)

            if len(errors) > 0:
                sys.stderr.write(str(errors))
                sys.exit(1)

        except Backup.MountException, e:
            sys.stderr.write(str(e) + "\n"
                             'Error: Aborting backup because mounting failed')
            sys.exit(2)
        except Exception, e:
            sys.stderr.write(str(e) + "\n"
                             'Error: Aborting backup')
            sys.exit(3)

        backup.clone(config.full_backup_path, config.backup_id)


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

