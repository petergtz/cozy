class Backup(object):

    class MountException(Exception):
        pass

    def mount(self, backup_path, backup_id, version):
        ''' 
        mounts a filesystem and returns Backup object that holds its mount point 
        '''

    def mount_latest(self, backup_path, backup_id):
        '''
        mounts a filesystem and returns Backup object that holds its mount point 
        '''

    def clone(self, backup_path, backup_id, version=None):
        '''
        takes a snapshot of the specified filesystem and returns the new version
        '''

