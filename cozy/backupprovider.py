import cozyfsbackup

class BackupProvider:

    def get_backup(self, backup_path, backup_id):
        return cozyfsbackup.CozyFSBackup(backup_path, backup_id)
