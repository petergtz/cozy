import os
import shutil

import utils.md5sum


write_on_user_data_string = 'Tried to write user data during backup: '

class FileSystemFunctions(object):
    def __init__(self, write_path, logger):
        self.logger = logger
        self.write_path = write_path

    def __assert_writing_to_write_path(self, path):
        if not path.startswith(self.write_path):
            self.logger.critical(write_on_user_data_string + path)
            raise Exception(write_on_user_data_string + path)

    def __copy_file(self, src, src_stat, dst):
        shutil.copy(src, dst)
        os.chmod(dst, src_stat.st_mode)
        os.chown(dst, src_stat.st_uid, src_stat.st_gid)
        os.utime(dst, (src_stat.st_atime, src_stat.st_mtime))

    def update_file(self, src, dst):
        self.__assert_writing_to_write_path(dst)
        info_string = 'File: ' + src + ': '
        try:
            src_stat = os.stat(src)

            if not os.path.exists(dst):
                self.__copy_file(src, src_stat, dst)
                self.logger.info(info_string + 'Copied')
                return

            dst_stat = os.stat(dst)
            skipped = True
            if src_stat.st_size != dst_stat.st_size:
                self.logger.debug(info_string + 'source-size(%d) != target-size(%d)', src_stat.st_size, dst_stat.st_size)
                self.__copy_file(src, src_stat, dst)
                skipped = False
            elif utils.md5sum.md5sum(src) != utils.md5sum.md5sum(dst):
                self.logger.debug(info_string + 'file content changed')
                self.__copy_file(src, src_stat, dst)
                skipped = False
            if src_stat.st_mode != dst_stat.st_mode:
                self.logger.debug(info_string + 'source-mode(%d) != target-mode(%d)', src_stat.st_mode, dst_stat.st_mode)
                os.chmod(dst, src_stat.st_mode)
                skipped = False
            if src_stat.st_gid != dst_stat.st_gid or src_stat.st_uid != dst_stat.st_uid:
                self.logger.debug(info_string + 'source-GID(%d) != target-GID(%d) or source-UID(%d) != target-UID(%d)',
                                  src_stat.st_gid, dst_stat.st_gid, src_stat.st_uid, dst_stat.st_uid)
                os.chown(dst, src_stat.st_uid, src_stat.st_gid)
                skipped = False
    # TODO: IMPORTANT: FILE CONTENT WAS NOT COMPARED!!!            

            if skipped:
                self.logger.debug(info_string + 'Skipped')
            else:
                self.logger.info(info_string + 'Updated')

                    # Note: if we use ctime as a comparison, the backup will always be done for all files
                    # because ctime will never be the same, since we're changing it directly after we
                    # copied a file into the backup. So we don't compare ctime!
                    # TODO: reintroduce this again, to track at least mtime
                    # but for now for simplicity reason comment it out.
    #                and src_stat.st_mtime == dst_stat.st_mtime
                    # we're not interested in comparing atime, because that's the access time. Only accessing it, does not mean we need to back it up
        except Exception, e:
            self.logger.error(info_string + str(e))


    def update_symlink(self, src, dst):
        self.__assert_writing_to_write_path(dst)

        info_string = 'Symlink: ' + src + ': '

        try:
            linkto = os.readlink(src)
            info_string += 'pointing to: ' + linkto + ': '
            src_stat = os.lstat(src)

            if not os.path.lexists(dst):
                os.symlink(linkto, dst)
                os.lchown(dst, src_stat.st_uid, src_stat.st_gid)
                self.logger.info(info_string + 'Copied')
                return
            if not os.path.islink(dst) or os.readlink(dst) != linkto:
                os.remove(dst)
                os.symlink(linkto, dst)
                os.lchown(dst, src_stat.st_uid, src_stat.st_gid)
                self.logger.debug(info_string + 'symlink targets different')
                self.logger.info(info_string + 'Updated')
                return
            dst_stat = os.lstat(dst)
            if dst_stat.st_gid != src_stat.st_gid or dst_stat.st_uid != src_stat.st_uid:
                os.lchown(dst, src_stat.st_uid, src_stat.st_gid)
                self.logger.debug(info_string + 'source-GID(%d) != target-GID(%d) or source-UID(%d) != target-UID(%d)',
                                  rc_stat.st_gid, dst_stat.st_gid, rc_stat.st_uid, dst_stat.st_uid)
                self.logger.info(info_string + 'Updated')
                return

            self.logger.debug(info_string + 'Skipped')

    # new in python 2.6:    
    #    os.lchmod(dst, src_stat.st_mode)
    # TODO: maybe reintroduce this call again. 2 things to consider:
    # 1. does this call change the symlinks time or the symlink's target's time
    # 2. correct cozyfs to handle a "touch" correctly!
#        os.utime(dst, (src_stat.st_atime, src_stat.st_mtime))

        except Exception, e:
            self.logger.exception(info_string + str(e))


    def update_dir(self, src, dst):
        self.__assert_writing_to_write_path(dst)
        info_string = 'Dir: ' + src + ': '
        try:
            src_stat = os.stat(src)

            if not os.path.exists(dst):
                os.mkdir(dst)
                os.chmod(dst, src_stat.st_mode)
                os.chown(dst, src_stat.st_uid, src_stat.st_gid)
                os.utime(dst, (src_stat.st_atime, src_stat.st_mtime))
                self.logger.info(info_string + 'Created')
                return

            dst_stat = os.stat(dst)
            skipped = True
            if src_stat.st_mode != dst_stat.st_mode:
                self.logger.debug(info_string + 'source-mode(%d) != target-mode(%d)', rc_stat.st_mode, dst_stat.st_mode)
                os.chmod(dst, src_stat.st_mode)
                skipped = False
            if src_stat.st_gid != dst_stat.st_gid or src_stat.st_uid != dst_stat.st_uid:
                self.logger.debug(info_string + 'source-GID(%d) != target-GID(%d) or source-UID(%d) != target-UID(%d)',
                                  rc_stat.st_gid, dst_stat.st_gid, rc_stat.st_uid, dst_stat.st_uid)
                os.chown(dst, src_stat.st_uid, src_stat.st_gid)
                skipped = False

            if skipped:
                self.logger.debug(info_string + 'Skipped')
            else:
                self.logger.info(info_string + 'Updated')

        except Exception, e:
            self.logger.exception(str(e))

    def remove(self, path):
        self.__assert_writing_to_write_path(path)

        self.logger.info('Removing file in target: ' + path)
        try:
            os.remove(path)
        except Exception, e:
            logger.error(str(e))

    def remove_dir(self, path):
        self.__assert_writing_to_write_path(path)

        self.logger.info('Removing dir in target: ' + path)
        try:
            shutil.rmtree(path)
        except Exception, e:
            logger.error(str(e))

    def islink(self, path):
        return os.path.islink(path)

    def isdir(self, path):
        return os.path.isdir(path)

    def isfile(self, path):
        return os.path.isfile(path)

    def walk(self, path):
        return os.walk(path)

    def listdir(self, path):
        return os.listdir(path)
