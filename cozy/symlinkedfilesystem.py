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

from cozy.filesystem import FileSystem
import os

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

