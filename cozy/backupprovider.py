import cozyfsbackup
import plainbackup

class BackupProvider:

    def get_backup(self, backup_path, config):
        if config.backup_type == 'PlainFS':
            return plainbackup.PlainBackup(backup_path, config.backup_id)
        elif config.backup_type == 'CozyFS':
            return cozyfsbackup.CozyFSBackup(backup_path, config.backup_id)
        else:
            return Exception('Backup type does not exist')
