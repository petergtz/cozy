# Cozy Backup Solution
# Copyright (C) 2009  peter
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

import dbus #@UnusedImport
import dbus.service #@Reimport @UnusedImport
import sys

class RestoreControlCenter(object):

    def __init__(self, restore_backend):
        self.restore_backend = restore_backend
        self.restore_client = None
        self.__current_version = restore_backend.VERSION_PRESENT

    def __del__(self):
        self.go_to_present()

    def __enter__(self):
        return self

    def __exit__(self, a, b, c):
        self.go_to_present()

    def go_to_present(self):
        try:
            self.go_to_version(self.restore_backend.VERSION_PRESENT)
        except Exception, e:
            print >> sys.stderr, e
        self.restore_backend.unmount_filesystems()



    def set_restore_client(self, restore_client):
        self.restore_client = restore_client

    def go_to_previous_version(self):
        previous_version = self.restore_backend.get_previous_version(self.current_version)
        if self.__version_is_not_none(previous_version):
            self.go_to_version(previous_version)

    def go_to_next_version(self):
        next_version = self.restore_backend.get_next_version(self.current_version)
        if self.__version_is_not_none(next_version):
            self.go_to_version(next_version)

    def __version_is_not_none(self, version):
        return version != self.restore_backend.VERSION_NONE

    def go_to_version(self, version):
        if self.restore_client is not None:
            path = self.restore_client.get_path().replace('file://', '')
            path_for_different_version = self.restore_backend.get_equivalent_path_for_different_version(path, version)
            self.restore_client.go_to_path('file://' + path_for_different_version)
            self.__current_version = version

    def get_all_versions(self):
        return self.restore_backend.get_all_versions()

    def __get_current_version(self):
        return self.__current_version

    current_version = property(__get_current_version)
