import tempfile
import os
from time import strptime, mktime, strftime, localtime, sleep
import subprocess
import pwd
import sqlite3

from filesystem import FileSystem

from backup import Backup

from cozyfssnapshot import snapshot

DBFILE = 'fsdb'

def epoche2date(epoche):
    return strftime('%Y-%m-%d_%H-%M-%S', localtime(epoche))

def date2epoche(date):
    return int(mktime(strptime(date, '%Y-%m-%d_%H-%M-%S')))

class Shell(object):
    def call(self, cmdline):
        process = subprocess.Popen(cmdline)
        sleep(2)
        return process

    def is_running(self, process):
        return process.poll() is None

    def return_code(self, process):
        return process.poll()


class CozyFSBackup(Backup):

    def __init__(self, config, shell=Shell(), db=sqlite3):
        Backup.__init__(self, config)
        self.shell = shell

        self.db = db.connect(os.path.join(self.backup_path, DBFILE))
        self.db.row_factory = db.Row
        self.db.text_factory = str

        self.__temp_mount_dir = None

    def __del__(self):
#        Backup.__del__(self)
        if hasattr(self, 'db'): # this is necessary because destructor can be called although object not completely initialized
            self.db.close()


    def __temp_dir(self):
        if self.__temp_mount_dir is None:
            loginname = pwd.getpwuid(os.getuid())[0]
            self.__temp_mount_dir = tempfile.mkdtemp(prefix='cozy-' + loginname)
        return self.__temp_mount_dir

    def __make_mount_point_dir(self, mount_point):
        if not os.path.exists(mount_point):
            os.makedirs(mount_point)

    def mount(self, version):
        mount_point = os.path.join(self.__temp_dir(), epoche2date(version))

        self.__make_mount_point_dir(mount_point)

        cmdline = ['cozyfs.py', mount_point, '-o', 'target_dir=' + self.backup_path + ',backup_id=' + str(self.backup_id), '-f']

        if version is not None:
            cmdline[-2] = cmdline[-2] + ',version=' + str(version)

        process = self.shell.call(cmdline)
        if not self.shell.is_running(process):
            if self.shell.return_code(process) == 3:
                raise CozyFSBackup.MountException('Error: Mount failed because database couldn''t be found')
            else:
                raise CozyFSBackup.MountException('Error: Mount failed due to unknown reasons')

        return FileSystem(mount_point)


    def clone(self, version):
        '''
        takes a snapshot of the specified filesystem and returns the new version
        '''
        snapshot(self.backup_path, self.backup_id, version)


    def __get_latest_version_in_backup(self):
        latest_version = self.db.execute("select max(version) from Versions where backup_id=?", (self.backup_id,)).fetchone()[0]
        assert latest_version is not None
        return latest_version

    def __get_base_version_of(self, current_version):
        result = self.db.execute("select based_on_version from Versions where backup_id=? and version=?", (self.backup_id, current_version)).fetchone()
        assert result is not None
        base_version = result[0]
#        assert base_version is not None
        return base_version

    def get_previous_versions(self, current_version):
        '''
        returns all versions this version is built up on
        '''
        if current_version is None:
            current_version = self.__get_latest_version_in_backup()

        version = self.__get_base_version_of(current_version)
        versions = []
        while version != None:
            versions.append(version)
            version = self.__get_base_version_of(version)

        return versions

    def __get_version_with(self, base_version):
        return self.db.execute("select version from Versions where backup_id=? and based_on_version=?", (self.backup_id, base_version)).fetchone()

    def get_next_versions(self, current_version):
        '''
        returns all versions that are built up on this version
        '''
        if current_version is None:
            return []

        ret = self.__get_version_with(base_version=current_version)
        if ret is None:
            return [None]
        version = ret[0]
        versions = []
        while version != None:
            versions.append(version)
            ret = self.__get_version_with(base_version=version)
            if ret is None:
                versions.append(None)
                if len(versions) >= 2:
                    del versions[-2]
                return versions
            version = ret[0]

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

