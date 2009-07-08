class Backup(object):

    class MountException(Exception):
        pass

    def __init__(self, config):
        self.backup_path = config.full_backup_path
        self.backup_id = config.backup_id

    def mount(self, version):
        ''' 
        mounts a filesystem and returns Backup object that holds its mount point 
        '''
        raise NotImplementedError()

    def mount_latest(self):
        '''
        mounts a filesystem and returns Backup object that holds its mount point 
        '''
        self.mount(None)

    def clone(self, version):
        '''
        takes a snapshot of the specified filesystem and returns the new version
        '''
        raise NotImplementedError()

    def clone_latest(self):
        '''
        takes a snapshot of the specified filesystem and returns the new version
        '''
        self.clone(None)

    def get_previous_versions(self, current_version):
        '''
        returns all versions this version is built up on
        '''
        raise NotImplementedError()

    def get_next_versions(self, current_version):
        '''
        returns all versions that are built up on this version
        '''
        raise NotImplementedError()

    def get_all_versions(self):
        '''
        returns all versions this backup contains
        '''
        raise NotImplementedError()

    def get_latest_version(self):
        '''
        returns the latest version this backup contains
        '''
        raise NotImplementedError()
