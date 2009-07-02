import tempfile
import os
from time import strptime, mktime, strftime, localtime, sleep
import subprocess
import pwd

from filesystem import FileSystem

from backup import Backup

from cozyfssnapshot import snapshot

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

    def __init__(self, shell=Shell()):
        Backup.__init__(self)
        self.shell = shell

    def __temp_dir(self):
        loginname = pwd.getpwuid(os.getuid())[0]
        return tempfile.mkdtemp(prefix='cozy-' + loginname)

    def __make_mount_point_dir(self, mount_point):
        if not os.path.exists(mount_point):
            os.makedirs(mount_point)

    def mount_latest(self, backup_path, backup_id):
        return self.mount(backup_path, backup_id, None)

    def mount(self, backup_path, backup_id, version):
        mount_point = os.path.join(self.__temp_dir(), epoche2date(version))

        self.__make_mount_point_dir(mount_point)

        cmdline = ['cozyfs.py', mount_point, '-o', 'target_dir=' + backup_path + ',backup_id=' + str(backup_id), '-f']

        if version is not None:
            cmdline[-2] = cmdline[-2] + ',version=' + str(version)

        process = self.shell.call(cmdline)
        if not self.shell.is_running(process):
            if self.shell.return_code(process) == 3:
                raise CozyFSBackup.MountException('Error: Mount failed because database couldn''t be found')
            else:
                raise CozyFSBackup.MountException('Error: Mount failed due to unknown reasons')

        return FileSystem(mount_point)


    def clone(self, backup_path, backup_id, version=None):
        '''
        takes a snapshot of the specified filesystem and returns the new version
        '''
        snapshot(backup_path, backup_id, version)


