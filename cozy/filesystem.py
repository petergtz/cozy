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

class FileSystem(object):

    def __init__(self, mount_point):
        self.__mount_point = mount_point

    def __del__(self):
        self._unmount()
        self._remove_mount_point_dir(self.mount_point)

    def __enter__(self):
        return self


    def __exit__(self, exc_type, exc_val, exc_tb):
        self._unmount()
        self._remove_mount_point_dir(self.mount_point)


    def _unmount(self):
        if self._is_mounted():
            subprocess.call(['fusermount', '-z', '-u', self.mount_point])

    def _remove_mount_point_dir(self, mount_point):
        if os.path.exists(mount_point):
            os.rmdir(mount_point)
        if os.path.exists(os.path.dirname(mount_point)) and len(os.listdir(os.path.dirname(mount_point))) == 0:
            os.rmdir(os.path.dirname(mount_point))

    def _is_mounted(self):
        return os.path.exists(self.mount_point) and os.path.ismount(self.mount_point)

    def __get_mount_point(self):
        return self.__mount_point

    mount_point = property(__get_mount_point)

    def has_relative_path(self, relative_path):
        return os.path.exists(os.path.join(self.mount_point, relative_path))

    def full_path(self, relative_path):
        return os.path.join(self.mount_point, relative_path)


class SymlinkedFileSystem(FileSystem):
    def _unmount(self):
       pass

    def _remove_mount_point_dir(self, mount_point):
        if os.path.exists(mount_point):
            os.unlink(mount_point)
        if os.path.exists(os.path.dirname(mount_point)) and len(os.listdir(os.path.dirname(mount_point))) == 0:
            os.rmdir(os.path.dirname(mount_point))

    def _is_mounted(self):
        return os.path.exists(self.mount_point)

