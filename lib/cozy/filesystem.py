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

import subprocess
import os
from os.path import join as join_path
import time

SUCCESSFUL_MOUNT_TIMEOUT = 2

class FileSystem(object):

    def __init__(self, mount_point, os_=os):
        self.__mount_point = mount_point
        self.os = os_

    def __del__(self):
        self._unmount()
        self._remove_mount_point_dir()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._unmount()
        self._remove_mount_point_dir()

    def _unmount(self):
        if self._is_mounted():
            subprocess.check_call(['fusermount', '-z', '-u', self.mount_point])
            self.__wait_until_filesystem_is_unmounted(self.mount_point)

    def __wait_until_filesystem_is_unmounted(self, mount_point):
        start_time = time.time()
        time_passed = 0

        while (time_passed < SUCCESSFUL_MOUNT_TIMEOUT):
            mtab_file = open('/etc/mtab', 'r')
            mtab_string = mtab_file.read()
            mtab_file.close()
            if mtab_string.find(mount_point) == -1 and not os.path.ismount(mount_point):
                time.sleep(1) # FIXME: unfortunately cozyfs takes a bit of time to close itself, after fusermount -u was called.
                              # This should be fixed, because a second not be enough. However, if we don't start the next backup
                              # immediately, it doesn't matter. So far it's only critical during tests!
                return
            time_passed = time.time() - start_time

    def _remove_mount_point_dir(self):
        if self.os.path.exists(self.mount_point):
            self.os.rmdir(self.mount_point)

    def _is_mounted(self):
        return self.os.path.exists(self.mount_point) and self.os.path.ismount(self.mount_point)

    def __get_mount_point(self):
        return self.__mount_point

    mount_point = property(__get_mount_point)

    def has_relative_path(self, relative_path):
        return self.os.path.exists(join_path(self.mount_point, relative_path))

    def full_path_from(self, relative_path):
        return join_path(self.mount_point, relative_path)
