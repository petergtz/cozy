#!/usr/bin/python

from __future__ import with_statement

import sys
import os
import shutil
import subprocess
import dbus
from time import sleep
import stat
import traceback

TC_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TC_DIR)

sys.path.append(os.path.join(ROOT_DIR, 'lib'))

import cozy.configuration
import cozy.restorebackend
import cozy.backupprovider
import cozy.locationmanager

COZY_BACKUP_PATH = os.path.join(ROOT_DIR, 'cozy-backup')
TEST_DATA = os.path.join(TC_DIR, 'TestData')

DOT_COZY = os.path.expanduser('~/.cozy')
DOT_COZY_BACKUP = os.path.expanduser('~/.cozy.orig.tc')
DATA = os.path.expanduser('~/Cozy-TC-Data')
BACKUP_DIR = os.path.expanduser('~/Cozy-TC-Backup-Dir')

os.environ['PATH'] += ':' + os.path.join(ROOT_DIR, 'cozyfs')

MAKE_COZYFS = 'mkfs.cozyfs.py'
BACKUP_TYPE = 'CozyFS'

class Setup:
    def __enter__(self):
        os.mkdir(BACKUP_DIR)
        self.__create_configuration()
        self.__create_filestructure_in_backup_location()
        return self

    def __create_configuration(self):
        if os.path.exists(DOT_COZY) and not os.path.exists(DOT_COZY_BACKUP):
            os.rename(DOT_COZY, DOT_COZY_BACKUP)

        config = cozy.configuration.Configuration()
        config.backup_enabled = True
        config.backup_type = BACKUP_TYPE
        config.backup_location_type = 'absolute_path'
        config.backup_location_identifier = BACKUP_DIR
        config.data_path = DATA
        config.write()

        self.backup_id = config.backup_id


    def __create_filestructure_in_backup_location(self):
        if BACKUP_TYPE == 'CozyFS':
            subprocess.check_call([MAKE_COZYFS, '--no-version', BACKUP_DIR, str(self.backup_id)])
        elif BACKUP_TYPE == 'PlainFS':
            os.makedirs(os.path.join(BACKUP_DIR, str(self.backup_id), '0'))
        elif BACKUP_TYPE == 'HardlinkedFS':
            pass

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
        print 'manual copy of data from ' + self.data_dir + str(self.change_counter) + \
                ' to ' + self.data_dir + str(self.change_counter + 1)
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
        if os.path.exists(self.data_dir):
            shutil.rmtree(self.data_dir)
        for change_number in range(len(self.changes) + 1):
            if os.path.lexists(self.data_dir + str(change_number)):
                shutil.rmtree(self.data_dir + str(change_number))

class CozyBackup:

    def __enter__(self):
        config = cozy.configuration.Configuration()
        backup_provider = cozy.backupprovider.BackupProvider()
        backup_location = cozy.locationmanager.LocationManager(None).get_backup_location(config)
        self.restore_backend = cozy.restorebackend.RestoreBackend(config, backup_provider, backup_location)
        return self

    def backup_data(self):
        cmdline = [COZY_BACKUP_PATH, '-s']
        print '### BACKING UP DATA: ' + ' '.join(cmdline)

#        import cozy.back_up
#        cozy.back_up.back_up()
#        ret = 0
        ret = subprocess.call(cmdline)
        if ret != 0:
            sys.exit('### FAILED backup_data')
        else:
            print '### PASSED backup_data'

    def get_prev_version(self, version):
        try:
            prev_version = self.restore_backend.get_previous_version(version)
            print '### PASSED get_prev_version'
            return prev_version
        except Exception, e:
            sys.exit('### FAILED get_prev_version: ' + str(e))

    def get_next_version(self, version):
        try:
            next_version = self.restore_backend.get_next_version(version)
            print '### PASSED get_next_version'
            return next_version
        except Exception, e:
            sys.exit('### FAILED get_next_version: ' + str(e))

    def get_equivalent_path(self, path, version):
        try:
            equiv_path = self.restore_backend.get_equivalent_path_for_different_version(path, version)
            print '### PASSED get_equivalent_path'
            return equiv_path
        except Exception, e:
            traceback.print_exc(file=sys.stderr)
            sys.exit('### FAILED get_equivalent_path: ' + str(e))


    def __exit__(self, type, value, traceback):
        del self.restore_backend


with Setup():
    with CozyBackup() as cozy_backup:

        with DataHandler(DATA) as data_handler:

            data_handler.create_data()

            for change_number in range(len(data_handler.changes)):
                cozy_backup.backup_data()
                sleep(1) # See filesystem.py why this is here.
                data_handler.change_data()

            current_path = DATA
            current_version = cozy_backup.restore_backend.VERSION_PRESENT
            first_time = True
            for change_number in range(len(data_handler.changes)):
                data_handler.undo_change_data()
                current_version = cozy_backup.get_prev_version(current_version)
                current_path = cozy_backup.get_equivalent_path(current_path, current_version)
                data_handler.compare_data_with(current_path)
                if first_time:
                    print 'CHECKING PLAIN FILESYSTEM'
                    data_handler.compare_data_with(os.path.join(BACKUP_DIR, 'plain'))
                    print 'DONE CHECKING PLAIN FILESYSTEM'
                    first_time = False

            for change_number in range(len(data_handler.changes)):
                data_handler.redo_change_data()
                current_version = cozy_backup.get_next_version(current_version)
                current_path = cozy_backup.get_equivalent_path(current_path, current_version)
                data_handler.compare_data_with(current_path)


print '### EXITING SUCCESSFULLY'
