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

from plainfsbackup import PlainFSBackup
from cozy.fileupdatestrategy import ChangeReplacesFileUpdateStrategy

import shutil


class HardlinkedFSBackup(PlainFSBackup):

    def clone(self, version):

        new_version = str(int(time()))
        os.makedirs(os.path.join(self.backup_path, str(self.backup_id), new_version))

        for (dirpath, dirnames, filenames) in os.walk(os.path.join(self.backup_path, str(self.backup_id), str(version))):
            for dirname in dirnames:
                src = os.path.join(dirpath, dirname)
                dst = src.replace(os.path.join(self.backup_path, str(self.backup_id), str(version)), os.path.join(self.backup_path, str(self.backup_id), new_version))
                if os.path.islink(src):
                    os.link(src, dst)
                else:
                    os.mkdir(dst)
                    shutil.copystat(src, dst)
            for filename in filenames:
                src = os.path.join(dirpath, filename)
                dst = src.replace(os.path.join(self.backup_path, str(self.backup_id), str(version)), os.path.join(self.backup_path, str(self.backup_id), new_version))
                os.link(src, dst)


    def get_file_update_strategy(self, mounted_filesystem, logger):
        return ChangeReplacesFileUpdateStrategy(mounted_filesystem.mount_point, logger)
