# Cozy Backup Solution
# Copyright (C) 2009  Peter Goetz
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as published by
# the Free Software Foundation.
#  
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#    
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

from os.path import join as join_path

class RestoreBackend(object):

    VERSION_PRESENT = -1
    VERSION_NONE = 0

    def __init__(self, config, backup_provider, backup_location):
        self.config = config

        self.filesystems = dict()
        self.backup_provider = backup_provider

        self.signal_handlers = dict()

        self.set_backup_location(backup_location)

    def set_backup_location(self, backup_location):
        self.backup_location = backup_location
        self.backup_location.connect_to_signal('unavailable', self.__set_backup_location_unavailable)
        self.backup_location.connect_to_signal('available', self.__set_backup_location_available)

        if self.is_backup_location_available():
            self.backup = self.backup_provider.get_backup(self.backup_location.get_path(), self.config)
        else:
            self.backup = None

    def __enter__(self):
        return self

    def __exit__(self, a, b, c):
        self.unmount_filesystems()

    def __del__(self):
        self.unmount_filesystems()

    def unmount_filesystems(self):
        self.filesystems.clear()

    def get_all_versions(self):
        if self.is_backup_location_available():
            result = self.backup.get_all_versions()
            result.insert(0, self.VERSION_PRESENT)
            return result
        else:
            return [self.VERSION_PRESENT]

    def get_previous_version(self, version):
        assert self.is_backup_location_available(), \
            'Backup is not connected to the system'
        previous_versions = self.backup.get_previous_versions(version)
        if len(previous_versions) == 0:
            return self.VERSION_NONE
        else:
            return previous_versions[0]

    def get_next_version(self, version):
        assert self.is_backup_location_available(), \
            'Backup is not connected to the system'

        next_versions = self.backup.get_next_versions(version)
        if len(next_versions) == 0 :
            return self.VERSION_NONE
        else:
            return next_versions[0]

    def is_backup_location_available(self):
        return self.backup_location.is_available()

    def __set_backup_location_available(self):
        self.backup = self.backup_provider.get_backup(self.backup_location.get_path(), self.config)
        self._emit_signal('available')

    def __set_backup_location_unavailable(self):
        self.unmount_filesystems()
        self.backup = None
        self._emit_signal('unavailable')

    def connect_to_signal(self, signal_name, handler_function):
        if not self.signal_handlers.has_key(signal_name):
            self.signal_handlers[signal_name] = []
        self.signal_handlers[signal_name].append(handler_function)

    def _emit_signal(self, signal):
        if self.signal_handlers.has_key(signal):
            for handler_func in self.signal_handlers[signal]:
                handler_func()


    def get_equivalent_path_for_different_version(self, path, version):
        assert self.is_backup_location_available(), \
            'Backup is not connected to the system'

        relative_path = self.__get_relative_path_of(path)
        if version == self.VERSION_PRESENT:
            return self.__full_path_in_present(relative_path)
        else:
            filesystem = self._get_mounted_filesystem(version)
            return filesystem.full_path_from(relative_path)

    def __full_path_in_present(self, relative_path):
        return join_path(self.config.data_path, relative_path)

    def __get_relative_path_of(self, path):
        if path.startswith(self.config.data_path):
            path = path.replace(self.config.data_path, '')
            return path.lstrip('/')
        else:
            for backup_version, filesystem in self.filesystems.items():
                if path.startswith(filesystem.mount_point):
                    path = path.replace(filesystem.mount_point , '')
                    return path.lstrip('/')
        raise Exception('Error: Requested path neither specifies your data nor your data in the past')

    def _get_mounted_filesystem(self, version):
        if not self.filesystems.has_key(version):
            filesystem = self.backup.mount(version, as_readonly=True)
            self.filesystems[version] = filesystem
        return self.filesystems[version]

