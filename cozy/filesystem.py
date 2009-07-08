import subprocess
import os
import warnings

class FileSystem(object):

    def __init__(self, mount_point):
        self.__mount_point = mount_point

    def __del__(self):
        self.__unmount()
        self.__remove_mount_point_dir(self.mount_point)

    def __unmount(self):
        if self.__is_mounted():
            subprocess.call(['fusermount', '-z', '-u', self.mount_point])
        else:
            warnings.warn('Tried to unmount a backup which is not mounted.')


    def __remove_mount_point_dir(self, mount_point):
        if os.path.exists(mount_point):
            os.rmdir(mount_point)
        else:
            warnings.warn('Tried to remove a mount point that does not exits.')
        if len(os.listdir(os.path.dirname(mount_point))) == 0:
            os.rmdir(os.path.dirname(mount_point))

    def __is_mounted(self):
        if os.path.exists(os.path.join(self.mount_point)) and \
            os.path.ismount(os.path.join(self.mount_point)):
            return True

        return False

    def __get_mount_point(self):
        return self.__mount_point

    mount_point = property(__get_mount_point)

    def has_relative_path(self, relative_path):
        return os.path.exists(os.path.join(self.mount_point, relative_path))

    def full_path(self, relative_path):
        return os.path.join(self.mount_point, relative_path)
