import sys
import os
import shutil

class Data(object):
    def __init__(self, data_path):
        self.data_path = data_path

    def back_up_to(self, backup):
        filesystem = backup.mount_latest()
        errors = self.__sync_to(filesystem)
        if len(errors) != 0:
            raise Exception('Errors during syncing:\n' + str(errors))

    def __copyfile(self, src, dst):
        src_stat = os.stat(src)
        if os.path.exists(dst):
            src_stat = os.stat(src)
            dst_stat = os.stat(dst)
                # Note: if we use ctime as a comparison, the backup will always be done for all files
                # because ctime will never be the same, since we're changing it directly after we
                # copied a file into the backup. So we don't compare ctime!
            if src_stat.st_size == dst_stat.st_size and \
                src_stat.st_mode == dst_stat.st_mode and \
                src_stat.st_gid == dst_stat.st_gid and \
                src_stat.st_uid == dst_stat.st_uid and \
                src_stat.st_mtime == dst_stat.st_mtime:
                # we're not interested in comparing atime, because that's the access time. Only accessing it, does not mean we need to back it up
                return
        print 'Copy file to target:', dst
        shutil.copy2(src, dst)
        os.chown(dst, src_stat.st_uid, src_stat.st_gid)
        os.utime(dst, (src_stat.st_atime, src_stat.st_mtime))

    def __copysymlink(self, src, dst):
        linkto = os.readlink(src)
        src_stat = os.lstat(src)
        if os.path.lexists(dst):
            dst_stat = os.lstat(dst)
            if os.path.islink(dst) and os.readlink(dst) == linkto and \
                dst_stat.st_gid == src_stat.st_gid and \
                dst_stat.st_uid == src_stat.st_uid:
                return
            else:
                os.remove(dst)
        print 'Copy symlink:', dst, '->', linkto
        os.symlink(linkto, dst)
        os.lchown(dst, src_stat.st_uid, src_stat.st_gid)
    # new in python 2.6:    
    #    os.lchmod(dst, src_stat.st_mode)
        os.utime(dst, (src_stat.st_atime, src_stat.st_mtime))

    def __copydir(self, src, dst):
        src_stat = os.stat(src)
        if os.path.exists(dst):
            dst_stat = os.stat(dst)
            if src_stat.st_mode == dst_stat.st_mode and \
                src_stat.st_gid == dst_stat.st_gid and \
                src_stat.st_uid == dst_stat.st_uid and \
                src_stat.st_mtime == dst_stat.st_mtime:
    #            src_stat.st_ctime == dst_stat.st_ctime and \
                pass
            else:
                os.chmod(dst, src_stat.st_mode)
                os.chown(dst, src_stat.st_uid, src_stat.st_gid)
                os.utime(dst, (src_stat.st_atime, src_stat.st_mtime))
            return

        print 'Copy dir to target:', dst
        os.mkdir(dst)
        os.chmod(dst, src_stat.st_mode)
        os.chown(dst, src_stat.st_uid, src_stat.st_gid)
        os.utime(dst, (src_stat.st_atime, src_stat.st_mtime))


    def __sync_to(self, filesystem):
        target = filesystem.mount_point
        source = self.data_path

        errors = []

        for dirpath, dirnames, filenames in os.walk(source):

            rel_path = dirpath.replace(source, '').lstrip('/')

            for target_dir_file in os.listdir(os.path.join(target, rel_path)):
                try:
                    abs_target_path = os.path.join(target, rel_path, target_dir_file)
                    if (os.path.isfile(abs_target_path) or (os.path.islink(abs_target_path))) and \
                        target_dir_file not in filenames:

                        print 'Remove file in target:', abs_target_path
                        os.remove(abs_target_path)

                    if os.path.isdir(abs_target_path) and \
                        target_dir_file not in dirnames:

                        print 'Remove dir in target:', abs_target_path
                        shutil.rmtree(abs_target_path)
                except EnvironmentError, e:
                    errors.append(str(e))

            for dirname in dirnames:
                try:
                    src = os.path.join(dirpath, dirname)
                    dst = os.path.join(target, rel_path, dirname)
                    if os.path.islink(src):
                        self.__copysymlink(src, dst)
                    else:
                        self.__copydir(src, dst)
                except EnvironmentError, e:
                    errors.append(str(e))

            for filename in filenames:
                try:
                    src = os.path.join(dirpath, filename)
                    dst = os.path.join(target, rel_path, filename)
                    if os.path.islink(src):
                        self.__copysymlink(src, dst)
                    else:
                        self.__copyfile(src, dst)
                except EnvironmentError, e:
                    errors.append(str(e))

        return errors
