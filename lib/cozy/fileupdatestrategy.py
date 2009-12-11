# Cozy Backup Solution
# Copyright (C) 2009  peter
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

# Note 1 (scroll down to see where it belongs to): 
# if we use ctime as a comparison, the backup will always be done for all files
# because ctime will never be the same, since we're changing it directly after we
# copied a file into the backup. So we don't compare ctime!
# TODO: reintroduce this again, to track at least mtime
# but for now for simplicity reason comment it out.
# and src_stat.st_mtime == dst_stat.st_mtime
# we're not interested in comparing atime, because that's the access time. Only accessing it, does not mean we need to back it up

# Note 2 (scroll down to see where it belongs to):
# new in python 2.6:    
#    os.lchmod(dst, src_stat.st_mode)
# TODO: maybe reintroduce this call again. 2 things to consider:
# 1. does this call change the symlinks time or the symlink's target's time
# 2. correct cozyfs to handle a "touch" correctly!
#        os.utime(dst, (src_stat.st_atime, src_stat.st_mtime))

import os
import shutil
import cozyutils.md5sum

write_on_user_data_string = 'Tried to write user data during backup: '



class FileUpdateStrategy(object):
    def __init__(self, write_path, logger):
        self.write_path = write_path
        self.logger = logger

    def update_file(self, src, dst):
        raise NotImplementedError()

    def update_symlink(self, src, dst):
        raise NotImplementedError()

    def update_dir(self, src, dst):
        raise NotImplementedError()

    def remove(self, path):
        raise NotImplementedError()

    def remove_dir(self, path):
        raise NotImplementedError()

class ChangeChangesFileUpdateStrategy(FileUpdateStrategy):

    def __assert_writing_to_write_path(self, path):
        if not path.startswith(self.write_path):
            self.logger.critical(write_on_user_data_string + path)
            raise Exception(write_on_user_data_string + path)

    def __create_file_if_not_existent(self, src, src_stat, dst):
        self.__assert_writing_to_write_path(dst)
        if not os.path.exists(dst):
            self.logger.debug("File: %s: Creating.", dst)
            shutil.copy(src, dst)
            os.utime(dst, (src_stat.st_atime, src_stat.st_mtime))
            return True
        else:
            return False

    def __create_dir_if_not_existent(self, src, src_stat, dst):
        self.__assert_writing_to_write_path(dst)
        if not os.path.exists(dst):
            self.logger.debug("Dir: %s: Creating.", dst)
            os.mkdir(dst)
            os.utime(dst, (src_stat.st_atime, src_stat.st_mtime))
            return True
        else:
            return False

    def __create_symlink_if_not_existent(self, dst, linkto):
        self.__assert_writing_to_write_path(dst)
        if not os.path.lexists(dst):
            self.logger.debug("Symlink: %s: Creating.", dst)
            os.symlink(linkto, dst)
            return True
        else:
            return False

    def __sync_file_content(self, src, src_stat, dst, dst_stat):
        self.__assert_writing_to_write_path(dst)
        if (src_stat.st_size != dst_stat.st_size or
            cozyutils.md5sum.md5sum(src) != cozyutils.md5sum.md5sum(dst)):
            self.logger.debug("File: %s: updating file content.", dst)
            shutil.copy(src, dst)
            os.utime(dst, (src_stat.st_atime, src_stat.st_mtime))
            return True
        else:
            return False

    def __sync_symlink_target(self, dst, linkto):
        self.__assert_writing_to_write_path(dst)
        if not os.path.islink(dst) or os.readlink(dst) != linkto:
            os.remove(dst)
            os.symlink(linkto, dst)
            self.logger.debug("Symlink: %s: updating target to %s.", dst, linkto)
            return True
        else:
            return False

    def __sync_mode(self, src, src_stat, dst, dst_stat):
        self.__assert_writing_to_write_path(dst)
        if src_stat.st_mode != dst_stat.st_mode:
            self.logger.debug("File: %s: updating mode from %d to %d.", dst, dst_stat.st_mode, src_stat.st_mode)
            os.chmod(dst, src_stat.st_mode)
            return True
        else:
            return False

    def __sync_owner(self, src, src_stat, dst, dst_stat):
        self.__assert_writing_to_write_path(dst)
        if src_stat.st_gid != dst_stat.st_gid or src_stat.st_uid != dst_stat.st_uid:
            self.logger.debug("File: %s: updating owner from %d:%d to %d:%d.", src,
                              dst_stat.st_uid, dst_stat.st_gid, src_stat.st_uid, src_stat.st_gid)
            os.chown(dst, src_stat.st_uid, src_stat.st_gid)
            return True
        else:
            return False

    def update_file(self, src, dst):
        try:
            src_stat = os.stat(src)

            created_file = self.__create_file_if_not_existent(src, src_stat, dst)
            dst_stat = os.stat(dst)
            updated_content = created_file or self.__sync_file_content(src, src_stat, dst, dst_stat)
            updated_mode = self.__sync_mode(src, src_stat, dst, dst_stat)
            updated_owner = self.__sync_owner(src, src_stat, dst, dst_stat)

            if created_file or updated_content or updated_mode or updated_owner:
                self.logger.info('File: %s: Updated', src)
            else:
                self.logger.debug('File: %s: Skipped', src)
            # See note 1 at the top of the file
        except Exception, e:
            self.logger.error('File: ' + src + ': ' + str(e))


    def update_symlink(self, src, dst):
        try:
            linkto = os.readlink(src)
            src_stat = os.lstat(src)
            updated_symlink_target = self.__create_symlink_if_not_existent(dst, linkto) or \
                                     self.__sync_symlink_target(dst, linkto)
            dst_stat = os.lstat(dst)
            updated_owner = self.__sync_owner(src, src_stat, dst, dst_stat)

            if updated_symlink_target or updated_owner:
                self.logger.info('Symlink: %s: Updated', src)
            else:
                self.logger.debug('Symlink: %s: Skipped', src)
            # See note 2 at the top of the file
        except Exception, e:
            self.logger.error('Symlink: ' + src + ': ' + str(e))



    def update_dir(self, src, dst):
        try:
            src_stat = os.stat(src)
            created_dir = self.__create_dir_if_not_existent(src, src_stat, dst)
            dst_stat = os.stat(dst)
            updated_mode = self.__sync_mode(src, src_stat, dst, dst_stat)
            updated_owner = self.__sync_owner(src, src_stat, dst, dst_stat)

            if created_dir or updated_mode or updated_owner:
                self.logger.info('File: %s: Updated', src)
            else:
                self.logger.debug('File: %s: Skipped', src)

        except Exception, e:
            self.logger.exception('Error updating dir: ' + dst + ': ' + str(e))

    def remove(self, path):
        try:
            self.__assert_writing_to_write_path(path)
            os.remove(path)
            self.logger.info('Removed file in target: ' + path)
        except Exception, e:
            self.logger.error('Error removing file: ' + path + ': ' + str(e))

    def remove_dir(self, path):
        try:
            self.__assert_writing_to_write_path(path)
            shutil.rmtree(path)
            self.logger.info('Removed dir in target: ' + path)
        except Exception, e:
            self.logger.error('Error removing dir: ' + path + ': ' + str(e))



class ChangeReplacesFileUpdateStrategy(FileUpdateStrategy):
    def __assert_writing_to_write_path(self, path):
        if not path.startswith(self.write_path):
            self.logger.critical(write_on_user_data_string + path)
            raise Exception(write_on_user_data_string + path)

    def __create_file_if_not_existent(self, src, src_stat, dst):
        if not os.path.exists(dst):
            self.__create_file(src, src_stat, dst)
            return True
        else:
            return False

    def __create_dir_if_not_existent(self, src, src_stat, dst):
        self.__assert_writing_to_write_path(dst)
        if not os.path.exists(dst):
            self.logger.debug("Dir: %s: Creating.", dst)
            os.mkdir(dst)
            os.utime(dst, (src_stat.st_atime, src_stat.st_mtime))
            return True
        else:
            return False

    def __create_symlink_if_not_existent(self, dst, linkto):
        self.__assert_writing_to_write_path(dst)
        if not os.path.lexists(dst):
            self.logger.debug("Symlink: %s: Creating.", dst)
            os.symlink(linkto, dst)
            return True
        else:
            return False

    def __sync_file_content(self, src, src_stat, dst, dst_stat):
        self.__assert_writing_to_write_path(dst)
        if (src_stat.st_size != dst_stat.st_size or
            cozyutils.md5sum.md5sum(src) != cozyutils.md5sum.md5sum(dst)):
            self.logger.debug("File: %s: updating file content.")
            shutil.copy(src, dst)
            os.utime(dst, (src_stat.st_atime, src_stat.st_mtime))
            return True
        else:
            return False

    def __sync_symlink_target(self, dst, linkto):
        self.__assert_writing_to_write_path(dst)
        if not os.path.islink(dst) or os.readlink(dst) != linkto:
            os.remove(dst)
            os.symlink(linkto, dst)
            self.logger.debug("Symlink: %s: updating target to %s.", linkto)
            return True
        else:
            return False

    def __sync_mode(self, src, src_stat, dst, dst_stat):
        self.__assert_writing_to_write_path(dst)
        if src_stat.st_mode != dst_stat.st_mode:
            self.logger.debug("File: %s: updating mode from %d to %d.", dst, dst_stat.st_mode, src_stat.st_mode)
            os.chmod(dst, src_stat.st_mode)
            return True
        else:
            return False

    def __sync_owner(self, src, src_stat, dst, dst_stat):
        self.__assert_writing_to_write_path(dst)
        if src_stat.st_gid != dst_stat.st_gid or src_stat.st_uid != dst_stat.st_uid:
            self.logger.debug("File: %s: updating owner from %d:%d to %d:%d.", src,
                              dst_stat.st_uid, dst_stat.st_gid, src_stat.st_uid, src_stat.st_gid)
            os.chown(dst, src_stat.st_uid, src_stat.st_gid)
            return True
        else:
            return False

    def __create_file(self, src, src_stat, dst):
        self.__assert_writing_to_write_path(dst)
        self.logger.debug("File: %s: Creating.", dst)
        shutil.copy(src, dst)
        os.utime(dst, (src_stat.st_atime, src_stat.st_mtime))


    def __create_file_and_sync_attributes(self, src, src_stat, dst):
        self.__create_file(src, src_stat, dst)
        dst_stat = os.stat(dst)
        self.__sync_mode(src, src_stat, dst, dst_stat)
        self.__sync_owner(src, src_stat, dst, dst_stat)
        self.logger.info('File: %s: Updated', src)

    def __files_differ(self, src, src_stat, dst, dst_stat):
        if src_stat.st_mode != dst_stat.st_mode or \
           src_stat.st_gid != dst_stat.st_gid or src_stat.st_uid != dst_stat.st_uid or \
           src_stat.st_size != dst_stat.st_size or \
           cozyutils.md5sum.md5sum(src) != cozyutils.md5sum.md5sum(dst):
            return True
        else:
            return False

    def update_file(self, src, dst):
        try:
            src_stat = os.stat(src)
            if os.path.exists(dst):
                dst_stat = os.stat(dst)
                if self.__files_differ(src, src_stat, dst, dst_stat):
                    self.remove(dst)
                    self.__create_file_and_sync_attributes(src, src_stat, dst)
                else:
                    self.logger.debug('File: %s: Skipped', src)
            else:
                self.__create_file_and_sync_attributes(src, src_stat, dst)
        except Exception, e:
            self.logger.error('File: ' + src + ': ' + str(e))


    def update_symlink(self, src, dst):
        try:
            linkto = os.readlink(src)
            src_stat = os.lstat(src)

            updated_symlink_target = self.__create_symlink_if_not_existent(dst, linkto) or \
                                     self.__sync_symlink_target(dst, linkto)

            dst_stat = os.lstat(dst)
            updated_owner = self.__sync_owner(src, src_stat, dst, dst_stat)

            if updated_symlink_target or updated_owner:
                self.logger.info('Symlink: %s: Updated', src)
            else:
                self.logger.debug('Symlink: %s: Skipped', src)
        except Exception, e:
            self.logger.error('Symlink: ' + src + ': ' + str(e))



    def update_dir(self, src, dst):
        try:
            src_stat = os.stat(src)
            created_dir = self.__create_dir_if_not_existent(src, src_stat, dst)
            dst_stat = os.stat(dst)
            updated_mode = self.__sync_mode(src, src_stat, dst, dst_stat)
            updated_owner = self.__sync_owner(src, src_stat, dst, dst_stat)

            if created_dir or updated_mode or updated_owner:
                self.logger.info('File: %s: Updated', src)
            else:
                self.logger.debug('File: %s: Skipped', src)

        except Exception, e:
            self.logger.exception('Error updating dir: ' + dst + ': ' + str(e))

    def remove(self, path):
        try:
            self.__assert_writing_to_write_path(path)
            os.remove(path)
            self.logger.info('Removed file in target: ' + path)
        except Exception, e:
            self.logger.error('Error removing file: ' + path + ': ' + str(e))

    def remove_dir(self, path):
        try:
            self.__assert_writing_to_write_path(path)
            shutil.rmtree(path)
            self.logger.info('Removed dir in target: ' + path)
        except Exception, e:
            self.logger.error('Error removing dir: ' + path + ': ' + str(e))

