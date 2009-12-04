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
import subprocess
import sqlite3
import time
import logging

from filesystem import FileSystem

from backup import Backup

from cozyutils.date_helper import epoche2date, date2epoche


DBFILE = 'fsdb'

COZY_MKFS_PATH = 'mkfs.cozyfs.py'
COZYFS_PATH = 'cozyfs.py'
COZYFSSNAPHOT_PATH = 'cozyfssnapshot.py'

SUCCESSFUL_MOUNT_TIMEOUT = 2

class CozyFSBackup(Backup):

    def __init__(self, backup_path, backup_id,
                 subprocess_factory=subprocess, db_connection_factory=sqlite3):
        Backup.__init__(self, backup_path, backup_id)
        self.subprocess_factory = subprocess_factory
        self.db_connection_factory = db_connection_factory
        self.__make_cozy_fs()

    def __make_cozy_fs(self):
        cmdline = [COZY_MKFS_PATH, self.backup_path, str(self.backup_id)]
        rc = self.subprocess_factory.call(cmdline)
        if rc != 0:
            raise Exception('Call to mkfs.cozy.py failed.')

    def get_all_versions(self):
        return self.get_previous_versions(self.VERSION_PRESENT)

    def mount(self, version, as_readonly=False):
        mount_point = os.path.join(self._temp_dir(), epoche2date(version))
        self.__make_mount_point_dir(mount_point)
        self.__mount_cozyfs(mount_point, version, as_readonly)
        return FileSystem(mount_point)

    def __make_mount_point_dir(self, mount_point):
        if not os.path.exists(mount_point):
            logging.getLogger('cozy.backup').debug('make mountpoint ' + mount_point)
            os.makedirs(mount_point)

    def __mount_cozyfs(self, mount_point, version, as_readonly):
        cmdline = self.__build_cmdline(mount_point, version, as_readonly)
        logging.getLogger('cozy.backup').debug(' '.join(cmdline))
        process = self.subprocess_factory.Popen(cmdline)
        process.args = cmdline
        self.__wait_until_filesystem_is_mounted(process, mount_point)

    def __build_cmdline(self, mount_point, version, as_readonly):
        cmdline = [COZYFS_PATH, self.backup_path, mount_point, '-b', str(self.backup_id), '-v', str(version)]
        if as_readonly:
            cmdline.append('-r')
        return cmdline

    def __wait_until_filesystem_is_mounted(self, process, mount_point):
        start_time = time.time()
        time_passed = 0

        while (time_passed < SUCCESSFUL_MOUNT_TIMEOUT):
            mtab_file = open('/etc/mtab', 'r')
            mtab_string = mtab_file.read()
            mtab_file.close()
            if mtab_string.find(mount_point) != -1:
                return
            time_passed = time.time() - start_time
        self.__handle_return_code_of(process)

    def __handle_return_code_of(self, process):
        if  process.returncode == 3:
            raise Backup.MountException('Error: Mount failed because database couldn''t be found.')
        elif  process.returncode == 4:
            raise Backup.MountException('Error: Mount failed because filesystem is locked.')
        else:
            (stdoutdata, stderrdata) = process.communicate()
            raise Backup.MountException('Error: Mount cmd :  ' + ' '.join(process.args) + 'failed due to errors: ' + stderrdata + stdoutdata)


    def clone(self, version):
        cmdline = [COZYFSSNAPHOT_PATH, self.backup_path, str(self.backup_id), str(version)]
        logging.getLogger('cozy.backup').debug(' '.join(cmdline))
        self.subprocess_factory.call(cmdline)


    def get_latest_version(self):
        db = self.__connect_to_db()
        latest_version = db.execute("select max(version) from Versions where backup_id=?", (self.backup_id,)).fetchone()[0]
        db.close()
        return latest_version

    def _get_base_version_of(self, current_version):
        db = self.__connect_to_db()
        row = db.execute("select based_on_version from Versions where backup_id=? and version=?", (self.backup_id, current_version)).fetchone()
        base_version = row[0]
        db.close()
        if base_version is None:
            return self.VERSION_NONE
        return base_version

    def _get_version_with(self, base_version):
        db = self.__connect_to_db()
        row = db.execute("select version from Versions where backup_id=? and based_on_version=?", (self.backup_id, base_version)).fetchone()
        db.close()
        if row is None:
            return self.VERSION_PRESENT
        return row[0]

    def __connect_to_db(self):
        db = self.db_connection_factory.connect(os.path.join(self.backup_path, DBFILE))
        db.row_factory = self.db_connection_factory.Row
        db.text_factory = str
        return db


