import dbus.service
import os.path

class RestoreBackend(dbus.service.Object):


    def __init__(self, config, backup_provider, session_bus, location_manager):
        dbus.service.Object.__init__(self, session_bus, '/org/freedesktop/Cozy/RestoreBackend')

        self.config = config
        if not self.config.backup_enabled:
            raise Exception("Backup is not enabled in configuration")

        self.filesystems = dict()
        self.backup_provider = backup_provider

        self.backup_location = location_manager.get_backup_location()
        self.backup_location.connect_to_signal('unavailable', self.__backup_location_unavailable)
        self.backup_location.connect_to_signal('available', self.__backup_location_available)


        self.backup = None
        if self.backup_location.is_available():
            self.backup = self.backup_provider.get_backup(self.backup_location.get_path(), self.config)


    def __backup_location_available(self):
        self.backup = self.backup_provider.get_backup(self.backup_location.get_path(), self.config.backup_id)


    def __backup_location_unavailable(self):
        self.__unmount_filesystems()
        self.backup = None


    # FIXME: this should have some kind of a reference counter
    # when the counter is zero, unmount all cozy fs and delete all directories
    @dbus.service.method(dbus_interface='org.freedesktop.Cozy.RestoreBackend',
                         in_signature='', out_signature='')
    def close_restore_mode(self):
        self.__unmount_filesystems()


    def __del__(self):
        self.__unmount_filesystems()


    def __unmount_filesystems(self):
        self.filesystems.clear()


    def __get_version_from(self, path):
        if path.startswith(self.config.data_path):
            return None
        else:
            for backup_version, filesystem in self.filesystems.items():
                if path.startswith(filesystem.mount_point):
                    return backup_version
        return (-1)


    def __get_relative_path_of(self, path):
        if path.startswith(self.config.data_path):
            path = path.replace(self.config.data_path, '')
            return path.lstrip(' / ')
        else:
            for backup_version, filesystem in self.filesystems.items():
                if path.startswith(filesystem.mount_point):
                    path = path.replace(filesystem.mount_point , '')
                    return path.lstrip(' / ')
        return (-1)


    @dbus.service.method(dbus_interface='org.freedesktop.Cozy.RestoreBackend',
                         in_signature='s', out_signature='s')
    def get_previous_version_path(self, path):
        if self.backup is None:
            return ''
        current_version = self.__get_version_from(path)
        if current_version == -1:
            return ''

        relative_path = self.__get_relative_path_of(path)

        for backup_version in self.backup.get_previous_versions(current_version):
            if self.filesystems.has_key(backup_version):
                filesystem = self.filesystems[backup_version]
            else:
                filesystem = self.backup.mount(backup_version)
                self.filesystems[backup_version] = filesystem
            if filesystem.has_relative_path(relative_path):
                return filesystem.full_path(relative_path)

        return ''

    @dbus.service.method(dbus_interface='org.freedesktop.Cozy.RestoreBackend',
                         in_signature='s', out_signature='s')
    def get_next_version_path(self, path):
        if self.backup is None:
            return ''
        current_version = self.__get_version_from(path)
        if current_version == -1:
            return ''

        relative_path = self.__get_relative_path_of(path)

        for backup_version in self.backup.get_next_versions(current_version):
            if backup_version is None:
                return os.path.join(self.config.data_path, relative_path)
            if self.filesystems.has_key(backup_version):
                filesystem = self.filesystems[backup_version]
            else:
                filesystem = self.backup.mount(backup_version)
                self.filesystems[backup_version] = filesystem
            if filesystem.has_relative_path(relative_path):
                return filesystem.full_path(relative_path)

        return ''

    @dbus.service.method(dbus_interface='org.freedesktop.Cozy.RestoreBackend',
                         in_signature='s', out_signature='s')
    def get_newest_version_path(self, path):
        relative_path = self.__get_relative_path_of(path)
        if relative_path == -1: # if we're completely out of the backup data just stay where we are.
            return path
        newest_path = os.path.join(self.config.data_path, relative_path)
        return newest_path


    @dbus.service.method(dbus_interface='org.freedesktop.Cozy.RestoreBackend',
                         in_signature='', out_signature='b')
    def backup_location_available(self):
        return self.backup_location.is_available()




