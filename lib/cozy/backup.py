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

import pwd
import os
import tempfile

from cozy.fileupdatestrategy import ChangeChangesFileUpdateStrategy

class Backup(object):

    VERSION_PRESENT = -1
    VERSION_NONE = 0

    class MountException(Exception):
        pass

    def __init__(self, backup_path, backup_id):
        self.backup_path = backup_path
        self.backup_id = backup_id
        self.__temp_mount_dir = ''

    def __del__(self):
        if os.path.exists(self.__temp_mount_dir):
            os.rmdir(self.__temp_mount_dir)

    def _temp_dir(self):
        if self.__temp_mount_dir == '':
            loginname = pwd.getpwuid(os.getuid())[0]
            self.__temp_mount_dir = tempfile.mkdtemp(prefix='cozy-' + loginname)
        return self.__temp_mount_dir

    def mount(self, version, as_readonly=False):
        ''' 
        mounts a filesystem and returns Backup object that holds its mount point 
        '''
        raise NotImplementedError()


    def mount_latest_version(self, as_readonly=False):
        '''
        mounts a filesystem and returns Backup object that holds its mount point 
        '''
        return self.mount(self.get_latest_version(), as_readonly)

    def clone(self, version):
        '''
        takes a snapshot of the specified filesystem and returns the new version
        '''
        raise NotImplementedError()

    def clone_latest_version(self):
        '''
        takes a snapshot of the specified filesystem and returns the new version
        '''
        return self.clone(self.get_latest_version())

    def _get_base_version_of(self, current_version):
        raise NotImplementedError()

    def _get_version_with(self, base_version):
        raise NotImplementedError()

    def get_previous_versions(self, current_version):
        '''
        returns all versions this version is built up on
        '''
        versions = []
        if current_version == self.VERSION_PRESENT:
            current_version = self.get_latest_version()
            versions.append(current_version)

        version = self._get_base_version_of(current_version)
        while version != self.VERSION_NONE:
            versions.append(version)
            version = self._get_base_version_of(version)

        return versions


    def get_next_versions(self, current_version):
        '''
        returns all versions that are built up on this version
        '''

        if current_version == self.VERSION_PRESENT:
            return []

        versions = []
        current_version = self._get_version_with(base_version=current_version)

        while current_version != self.VERSION_PRESENT:
            versions.append(current_version)
            current_version = self._get_version_with(base_version=current_version)

        versions.append(self.VERSION_PRESENT)
        return versions

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

    def get_file_update_strategy(self, mounted_filesystem, logger):
        return ChangeChangesFileUpdateStrategy(mounted_filesystem.mount_point, logger)
