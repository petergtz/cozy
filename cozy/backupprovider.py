import cozyfsbackup

class BackupProvider:

    def get_backup(self, config):
        return cozyfsbackup.CozyFSBackup()
