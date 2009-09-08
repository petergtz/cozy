#!/usr/bin/python

from __future__ import with_statement

import sys
import os
import shutil
import subprocess
import cozy.configuration
import dbus
from time import sleep
import stat

TC_DIR = os.path.abspath(os.path.dirname(__file__))
ROOT_DIR = os.path.join(TC_DIR, '..')


COZY_MKFS_PATH = os.path.join(ROOT_DIR, 'mkfs.cozyfs.py')
COZY_BACKUP_PATH = os.path.join(ROOT_DIR, 'cozy-backup.py')
COZY_RESTORE_BACKEND_PATH = os.path.join(ROOT_DIR, 'cozy-restore-backend.py')
COZY_LOCATION_MANAGER = os.path.join(ROOT_DIR, 'cozy-location-manager.py')
TEST_DATA = os.path.join(TC_DIR, 'TestData')

DOT_COZY = os.path.expanduser('~/.cozy')
DOT_COZY_BACKUP = os.path.expanduser('~/.cozy.orig.tc')
DATA = os.path.expanduser('~/Cozy-TC-Data')
BACKUP_DIR = os.path.expanduser('~/Cozy-TC-Backup-Dir')
#BACKUP_DIR = os.path.expanduser('/media/KINGSTON/Cozy-TC-Backup-Dir')


class Setup:
    def __enter__(self):
        self.create_configuration()
        self.make_cozyfs()
        return self

    def create_configuration(self):
        if os.path.exists(DOT_COZY) and not os.path.exists(DOT_COZY_BACKUP):
            os.rename(DOT_COZY, DOT_COZY_BACKUP)

        config = cozy.configuration.Configuration()
        config.backup_enabled = True
#        config.backup_type = 'PlainFS'
        config.backup_type = 'CozyFS'
        #config.set_backup_id(BACKUP_ID)
        config.backup_location_type = 'absolute_path'
        config.backup_location_identifier = BACKUP_DIR
        config.data_path = DATA
        config.write()

        self.backup_id = config.backup_id

    def make_cozyfs(self):
        os.mkdir(BACKUP_DIR)

#        cmdline = [COZY_MKFS_PATH, BACKUP_DIR, str(self.backup_id)]
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
#        return stdout

    def __exit__(self, type, value, traceback):
        if os.path.exists(DOT_COZY_BACKUP):
            os.rename(DOT_COZY_BACKUP, DOT_COZY)

        if os.path.exists(BACKUP_DIR):
            shutil.rmtree(BACKUP_DIR)

def create_data(path):
    shutil.copytree(TEST_DATA, path, True)


def delete_two_files(path):
    files = ['extensions', 'GlTransition.csharp']
    for file in files:
        if os.path.isfile(os.path.join(path, file)):
            print 'removing file', os.path.join(path, file)
            os.remove(os.path.join(path, file))
        elif os.path.isdir(os.path.join(path, file)):
            print 'removing dir', os.path.join(path, file)
            shutil.rmtree(os.path.join(path, file))

def add_symlinks_and_copies(path):
    os.symlink('TextureDisplay-bessere-loesung.csharp', os.path.join(path, 'shorty'))
    os.utime(os.path.join(path, 'shorty'), (1000000, 2000000))
    os.symlink('ordner', os.path.join(path, 'ordner.symlink'))
    os.utime(os.path.join(path, 'ordner.symlink'), (1000000, 2000000))

#    shutil.copytree(os.path.join(path, 'ordner'), os.path.join(path, 'ordner.copy'))

def change_to_same_size(path):
    content = ''
    with open(os.path.join(path, 'small_textures.diff')) as f:
        content = f.read()
        content = content.replace('+++', 'rrr')
    with open(os.path.join(path, 'small_textures.diff'), 'w') as f:
        f.write(content)

    os.chmod(os.path.join(path, 'white_trans.diff'), stat.S_IWGRP | stat.S_IWUSR | stat.S_IRUSR)


def delete_everything(path):
    files = os.listdir(path)
    for file in files:
        if os.path.isfile(os.path.join(path, file)) or os.path.islink(os.path.join(path, file)):
            os.remove(os.path.join(path, file))
        elif os.path.isdir(os.path.join(path, file)):
            shutil.rmtree(os.path.join(path, file))

class DataHandler:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.changes = [delete_two_files, add_symlinks_and_copies, change_to_same_size, delete_everything]
        self.change_counter = 0

    def __enter__(self):
        return self

    def create_data(self):
        self.change_counter = 0
        print 'creating data'
        create_data(self.data_dir)
        sleep(1)
        create_data(self.data_dir + str(self.change_counter))

    def change_data(self):
        shutil.copytree(self.data_dir + str(self.change_counter), self.data_dir + str(self.change_counter + 1), True)
        self.change_counter += 1
        print 'making change number', self.change_counter
        self.changes[self.change_counter - 1](self.data_dir)
        self.changes[self.change_counter - 1](self.data_dir + str(self.change_counter))

    def undo_change_data(self):
        if self.change_counter == 0:
            sys.exit('### FAILED: change counter already 0')
        self.change_counter -= 1

    def redo_change_data(self):
        if self.change_counter == len(self.changes):
            sys.exit('### FAILED: change counter already at max')
        self.change_counter += 1

    def compare_data_with(self, path2):
        path1 = self.data_dir + str(self.change_counter)

        for dirpath, dirnames, filenames in os.walk(path1):

            for dirname in dirnames:
                abs_dir_path1 = os.path.join(dirpath, dirname)
                abs_dir_path2 = os.path.normpath(os.path.join(dirpath.replace(path1, path2), dirname))
                if not os.path.lexists(abs_dir_path2):
                    sys.exit('### FAILED dir or symlink ' + abs_dir_path2 + ' is missing')
                if os.path.islink(abs_dir_path1) != os.path.islink(abs_dir_path2):
                    sys.exit('### FAILED one dir is a symlink while the other is real dir')
                stat1 = os.lstat(abs_dir_path1)
                stat2 = os.lstat(abs_dir_path2)
                if not stat1.st_uid == stat2.st_uid:
                    sys.exit('### FAILED file ' + abs_dir_path2 + ' does not have same uid')
                if not stat1.st_gid == stat2.st_gid:
                    sys.exit('### FAILED file ' + abs_dir_path2 + ' does not have same gid')
                if os.path.islink(abs_dir_path1):
                    if not (stat1.st_size == stat2.st_size):
                        sys.exit('### FAILED file ' + abs_dir_path2 + ' does not have same size')
                    if os.readlink(abs_dir_path1) != os.readlink(abs_dir_path2):
                        sys.exit('### FAILED dir links do not link to the same location')
                else:
                # Note: only compare the mode if it's not a symlink, because the symlink could be broken due
                #    to different relative paths. Symlinks' mode is not used anywhere. They always inherit 
                #    their targets' mode.
                    if not stat1.st_mode == stat2.st_mode:
                        sys.exit('### FAILED file ' + abs_dir_path2 + ' does not have same mode')
                # Note: we can also not compare mtime, since we cannot explicitely set it for the symlink with utime
                #    so there's no way for the comparison to have equal mtimes

#                    if not stat1.st_mtime == stat2.st_mtime:
#                        sys.exit('### FAILED file ' + abs_dir_path2 + ' does not have same mtime')

            for filename in filenames:
                abs_file_path1 = os.path.join(dirpath, filename)
                abs_file_path2 = os.path.normpath(os.path.join(dirpath.replace(path1, path2), filename))
                print 'Comparing', abs_file_path1, '***', abs_file_path2
                if not os.path.lexists(abs_file_path2):
                    sys.exit('### FAILED file or symlink ' + abs_file_path2 + ' is missing')
                stat1 = os.lstat(abs_file_path1)
                stat2 = os.lstat(abs_file_path2)
                if not stat1.st_uid == stat2.st_uid:
                    sys.exit('### FAILED file ' + abs_file_path2 + ' does not have same uid')
                if not stat1.st_gid == stat2.st_gid:
                    sys.exit('### FAILED file ' + abs_file_path2 + ' does not have same gid')
                if not stat1.st_size == stat2.st_size:
                    sys.exit('### FAILED file ' + abs_file_path2 + ' does not have same size')
# Note: time is a complicated thing here:
#     ctime cannot be changed at all, so there's no easy way to have equal ctimes in both directories to compare.
#     atime changes as well too. Although it is possible to change, we leave that out here, because atime does 
#     not matter a lot anyway. It's just the accesstime and has nothing to do with backup.
                if os.path.islink(abs_file_path1):
                    if os.readlink(abs_file_path1) != os.readlink(abs_file_path2):
                        sys.exit('### FAILED file links do not link to the same location')
                else:
                    if not stat1.st_mode == stat2.st_mode:
                        sys.exit('### FAILED file ' + abs_file_path2 + ' does not have same mode')
                    file1 = open(abs_file_path1, 'rb')
                    file2 = open(abs_file_path2, 'rb')
                    if file1.read() != file2.read():
                        sys.exit('### FAILED file ' + abs_file_path2 + ' does not have same content')
#                    if not stat1.st_mtime == stat2.st_mtime:
#                        sys.exit('### FAILED file ' + abs_file_path2 + ' does not have same mtime')


    def __exit__(self, type, value, traceback):
        shutil.rmtree(self.data_dir)
        for change_number in range(len(self.changes) + 1):
            if os.path.lexists(self.data_dir + str(change_number)):
                shutil.rmtree(self.data_dir + str(change_number))

class CozyBackup:

    def __enter__(self):
#        subprocess.call([COZY_LOCATION_MANAGER, 'start'])
#        sleep(1)
#        if not self.__manager_running(COZY_LOCATION_MANAGER):
#            msg = open('/tmp/cozy-location-manager-stderr').read()
#            os.remove('/tmp/cozy-location-manager-stderr')
#            raise Exception(msg)

        subprocess.call([COZY_RESTORE_BACKEND_PATH, 'start'])
        sleep(1)
        if not self.__manager_running(COZY_RESTORE_BACKEND_PATH):
            msg = open('/tmp/cozy-restore-backend-stderr').read()
            os.remove('/tmp/cozy-restore-backend-stderr')
            raise Exception(msg)


        self.session_bus = dbus.SessionBus()
        self.manager_object = self.session_bus.get_object('org.freedesktop.Cozy.RestoreBackend', '/org/freedesktop/Cozy/RestoreBackend')
        self.manager = dbus.Interface(self.manager_object, dbus_interface='org.freedesktop.Cozy.RestoreBackend')

        return self

    def __manager_running(self, daemon):
        a = os.system("ps -ef | grep -v grep | grep " + daemon)
        if a != 0:
            return False
        return True

    def backup_data(self):
        cmdline = [COZY_BACKUP_PATH, '-f']
        print '### BACKING UP DATA: ' + ' '.join(cmdline)
        ret = subprocess.call(cmdline)
        if ret != 0:
            sys.exit('### FAILED backup_data')
        else:
            print '### PASSED backup_data'

    def get_prev_version_path(self, path):
        try:
            prev_version_path = self.manager.get_previous_version_path(path)
            print '### PASSED get_pre_version_path'
            return prev_version_path
        except Exception, e:
            sys.exit('### FAILED get_pre_version_path: ' + str(e))

    def get_next_version_path(self, path):
        try:
            next_version_path = self.manager.get_next_version_path(path)
            print '### PASSED get_next_version_path'
            return next_version_path
        except Exception, e:
            sys.exit('### FAILED get_next_version_path: ' + str(e))


    def close_restore_mode(self):
        self.manager.close_restore_mode()

    def __exit__(self, type, value, traceback):
        self.close_restore_mode()
        subprocess.call([COZY_RESTORE_BACKEND_PATH, 'stop'])
#        subprocess.call([COZY_LOCATION_MANAGER, 'stop'])


with Setup() as setup:
    with CozyBackup() as cozy_backup:

        with DataHandler(DATA) as data_handler:

            data_handler.create_data()

            for change_number in range(len(data_handler.changes)):
                cozy_backup.backup_data()
                data_handler.change_data()

            prev_version_path = DATA
            for change_number in range(len(data_handler.changes)):
                data_handler.undo_change_data()
                prev_version_path = cozy_backup.get_prev_version_path(prev_version_path)
                data_handler.compare_data_with(prev_version_path)

            next_version_path = prev_version_path
            for change_number in range(len(data_handler.changes)):
                data_handler.redo_change_data()
                next_version_path = cozy_backup.get_next_version_path(next_version_path)
                data_handler.compare_data_with(next_version_path)


print '### EXITING SUCCESSFULLY'
