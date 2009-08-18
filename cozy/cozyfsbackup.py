import os
from time import strptime, mktime, strftime, localtime, sleep
import subprocess
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

TC_DIR = os.path.abspath(os.path.dirname(__file__))
ROOT_DIR = os.path.join(TC_DIR, '..')
COZY_MKFS_PATH = os.path.join(ROOT_DIR, 'mkfs.cozyfs.py')
COZYFS_PATH = os.path.join(ROOT_DIR, 'cozyfs.py')

class CozyFSBackup(Backup):

    def __init__(self, backup_path, backup_id, shell=Shell(), db=sqlite3):
        Backup.__init__(self, backup_path, backup_id)
        self.shell = shell

        cmdline = [COZY_MKFS_PATH, self.backup_path, str(self.backup_id)]
        rc = subprocess.call(cmdline)
        if rc != 0:
            raise Exception('Call to mkfs.cozy.py failed.')

        self.db = db.connect(os.path.join(self.backup_path, DBFILE))
        self.db.row_factory = db.Row
        self.db.text_factory = str

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
#        Backup.__del__(self)
        if hasattr(self, 'db'): # this is necessary because destructor can be called although object not completely initialized
            self.db.close()


    def __make_mount_point_dir(self, mount_point):
        if not os.path.exists(mount_point):
            os.makedirs(mount_point)

    def mount(self, version):
        mount_point = os.path.join(self._temp_dir(), epoche2date(version))

        self.__make_mount_point_dir(mount_point)

        cmdline = [COZYFS_PATH, mount_point, '-o', 'target_dir=' + self.backup_path + ',backup_id=' + str(self.backup_id), '-f']
        cmdline[-2] = cmdline[-2] + ',version=' + str(version)

        process = self.shell.call(cmdline)
        if not self.shell.is_running(process):
            return_code = self.shell.return_code(process)
            if  return_code == 3:
                raise Backup.MountException('Error: Mount failed because database couldn''t be found.')
            elif  return_code == 4:
                raise Backup.MountException('Error: Mount failed because filesystem is locked.')
            else:
                raise Backup.MountException('Error: Mount failed due to unknown reasons.')

        return FileSystem(mount_point)


    def clone(self, version):
        snapshot(self.backup_path, self.backup_id, version)


    def get_latest_version(self):
        latest_version = self.db.execute("select max(version) from Versions where backup_id=?", (self.backup_id,)).fetchone()[0]
        assert latest_version is not None
        return latest_version

    def _get_base_version_of(self, current_version):
        result = self.db.execute("select based_on_version from Versions where backup_id=? and version=?", (self.backup_id, current_version)).fetchone()
        assert result is not None
        base_version = result[0]
#        assert base_version is not None
        return base_version

    def _get_version_with(self, base_version):
        ret = self.db.execute("select version from Versions where backup_id=? and based_on_version=?", (self.backup_id, base_version)).fetchone()
        if ret is None:
            return None
        return ret[0]

