import os
from time import strptime, mktime, strftime, localtime, sleep, time

from filesystem import SymlinkedFileSystem

from backup import Backup

import shutil


def epoche2date(epoche):
    return strftime('%Y-%m-%d_%H-%M-%S', localtime(epoche))

def date2epoche(date):
    return int(mktime(strptime(date, '%Y-%m-%d_%H-%M-%S')))


class PlainBackup(Backup):

    def __init__(self, backup_path, backup_id):
        Backup.__init__(self, backup_path, backup_id)
        if not os.path.exists(os.path.join(self.backup_path, str(self.backup_id))):
            os.makedirs(os.path.join(self.backup_path, str(self.backup_id), str(int(time()))))


    def mount(self, version):

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
