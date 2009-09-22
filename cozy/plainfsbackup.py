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

import os
from time import sleep, time

from cozyutils.date_helper import epoche2date, date2epoche

from symlinkedfilesystem import SymlinkedFileSystem

from backup import Backup

import shutil


class PlainFSBackup(Backup):

    def __init__(self, backup_path, backup_id):
        Backup.__init__(self, backup_path, backup_id)
        if not os.path.exists(os.path.join(self.backup_path, str(self.backup_id), str(0))):
            os.makedirs(os.path.join(self.backup_path, str(self.backup_id), str(0)))


    def mount(self, version, as_readonly):
        mount_point = os.path.join(self._temp_dir(), epoche2date(version))

        os.symlink(os.path.join(self.backup_path, str(self.backup_id), str(version)), mount_point)

        return SymlinkedFileSystem(mount_point)


    def clone(self, version):
        new_version = str(int(time()))
        shutil.copytree(os.path.join(self.backup_path, str(self.backup_id), str(version)),
                        os.path.join(self.backup_path, str(self.backup_id), new_version),
                        True)


    def get_latest_version(self):
        versions = os.listdir(os.path.join(self.backup_path, str(self.backup_id)))
        versions.sort()
        return int(versions[-1])

    def _get_base_version_of(self, current_version):
        versions = os.listdir(os.path.join(self.backup_path, str(self.backup_id)))
        versions.sort()
        i = versions.index(str(current_version)) - 1
        if i == -1:
            return None
        else:
            return int(versions[i])

    def _get_version_with(self, base_version):
        versions = os.listdir(os.path.join(self.backup_path, str(self.backup_id)))
        versions.sort()
        i = versions.index(str(base_version)) + 1
        if i == len(versions):
            return None
        else:
            return int(versions[i])
