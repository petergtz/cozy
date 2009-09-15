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
from time import sleep
import subprocess
import sqlite3

from filesystem import FileSystem

from backup import Backup

from cozyutils.date_helper import epoche2date, date2epoche

DBFILE = 'fsdb'

#PACKAGE_DIR = os.path.dirname(__file__)
#BASE_DIR = os.path.dirname(PACKAGE_DIR)
#COZY_MKFS_PATH = os.path.join(BASE_DIR, 'cozyfs/mkfs.cozyfs.py')
#COZYFS_PATH = os.path.join(BASE_DIR, 'cozyfs/cozyfs.py')
#COZYFSSNAPHOT_PATH = os.path.join(BASE_DIR, 'cozyfs/cozyfssnapshot.py')
COZY_MKFS_PATH = 'mkfs.cozyfs.py'
COZYFS_PATH = 'cozyfs.py'
COZYFSSNAPHOT_PATH = 'cozyfssnapshot.py'

class CozyFSBackup(Backup):

    def __make_cozy_fs(self):
        cmdline = [COZY_MKFS_PATH, self.backup_path, str(self.backup_id)]
        rc = self.subprocess_factory.call(cmdline)
        if rc != 0:
            raise Exception('Call to mkfs.cozy.py failed.')

    def __connect_to_db(self, db_connection_factory):
        self.db = db_connection_factory.connect(os.path.join(self.backup_path, DBFILE))
        self.db.row_factory = db_connection_factory.Row
        self.db.text_factory = str


    def __init__(self, backup_path, backup_id,
                 subprocess_factory=subprocess, db_connection_factory=sqlite3):
        Backup.__init__(self, backup_path, backup_id)
        self.subprocess_factory = subprocess_factory

        self.__make_cozy_fs()
        self.__connect_to_db(db_connection_factory)


#        print '### MAKING FS: ' + ' '.join(cmdline)
#        try:
#            process = subprocess.Popen(cmdline, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#        except Exception, e:
#            print e
#            raise
#
#        (stdout, stderr) = process.communicate()
#
#        print stdout

    def __del__(self):
        if hasattr(self, 'db'): # this is necessary because destructor can be called although object not completely initialized
            self.db.close()

    def __make_mount_point_dir(self, mount_point):
        if not os.path.exists(mount_point):
            os.makedirs(mount_point)

    def __is_process_running(self, process):
        if process.poll() is None:
            return True
        else:
            return False

    def __handle_return_code(self, return_code):
        if  return_code == 3:
            raise Backup.MountException('Error: Mount failed because database couldn''t be found.')
        elif  return_code == 4:
            raise Backup.MountException('Error: Mount failed because filesystem is locked.')
        else:
            raise Backup.MountException('Error: Mount failed due to unknown reasons.')

    def __build_cmdline(self, mount_point, version):
        cmdline = [COZYFS_PATH, mount_point, '-o', 'target_dir=' + self.backup_path + ',backup_id=' + str(self.backup_id), '-f']
        cmdline[-2] = cmdline[-2] + ',version=' + str(version)
        return cmdline

    def __mount_cozyfs(self, mount_point, version):
        cmdline = self.__build_cmdline(mount_point, version)
        process = self.subprocess_factory.Popen(cmdline)
        sleep(2)
        if not self.__is_process_running(process):
            self.__handle_return_code(process.returncode)

    def mount(self, version):
        mount_point = os.path.join(self._temp_dir(), epoche2date(version))
        self.__make_mount_point_dir(mount_point)
        self.__mount_cozyfs(mount_point, version)
        return FileSystem(mount_point)


    def clone(self, version):
        cmdline = [COZYFSSNAPHOT_PATH, self.backup_path, str(self.backup_id), str(version)]
        self.subprocess_factory.call(cmdline)


    def get_latest_version(self):
        latest_version = self.db.execute("select max(version) from Versions where backup_id=?", (self.backup_id,)).fetchone()[0]
        assert latest_version is not None
        return latest_version

    def _get_base_version_of(self, current_version):
        result = self.db.execute("select based_on_version from Versions where backup_id=? and version=?", (self.backup_id, current_version)).fetchone()
        assert result is not None
        base_version = result[0]
        return base_version

    def _get_version_with(self, base_version):
        ret = self.db.execute("select version from Versions where backup_id=? and based_on_version=?", (self.backup_id, base_version)).fetchone()
        if ret is None:
            return None
        return ret[0]

