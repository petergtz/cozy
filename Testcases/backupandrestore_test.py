#!/usr/bin/python

import sys
import os
import shutil
import subprocess
import cozy.configutils
import dbus
from time import sleep

TC_DIR = os.path.abspath(os.path.dirname(__file__))
ROOT_DIR = os.path.join(TC_DIR, '..')


COZY_MKFS_PATH = os.path.join(ROOT_DIR, 'mkfs.cozyfs.py')
COZY_BACKUP_PATH = os.path.join(ROOT_DIR, 'cozy-backup.py')
COZY_MANAGER_PATH = os.path.join(ROOT_DIR, 'cozy-manager.py')
TEST_DATA = os.path.join(TC_DIR, 'TestData')

DOT_COZY = os.path.expanduser('~/.cozy')
DOT_COZY_BACKUP = os.path.expanduser('~/.cozy.orig.tc')
DATA = os.path.expanduser('~/Cozy-TC-Data')
BACKUP_DIR = os.path.expanduser('~/Cozy-TC-Backup-Dir')


class Setup:
    def set_up(self):
        self.create_configuration()
        self.make_cozyfs()

    def create_configuration(self):
        if os.path.exists(DOT_COZY):
            os.rename(DOT_COZY, DOT_COZY_BACKUP)

        config = cozy.configutils.Configuration()
        config.set_backup_enabled(True)
        #config.set_backup_id(BACKUP_ID)
        config.set_removeable_target_volume(False)
        config.set_full_target_path(BACKUP_DIR)
        config.set_source_path(DATA)
        config.write()

        self.backup_id = config.get_backup_id()

    def make_cozyfs(self):
        os.mkdir(BACKUP_DIR)

        cmdline = [COZY_MKFS_PATH, BACKUP_DIR, str(self.backup_id)]
        print '### MAKING FS: ' + ' '.join(cmdline)
        try:
            process = subprocess.Popen(cmdline, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception, e:
            print e
            raise

        (stdout, stderr) = process.communicate()

        print stdout
        return stdout

    def cleanup_configuration(self):
        if os.path.exists(DOT_COZY_BACKUP):
            os.rename(DOT_COZY_BACKUP, DOT_COZY)

        if os.path.exists(DATA):
            shutil.rmtree(DATA)
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
        self.changes = [delete_two_files, add_symlinks_and_copies, delete_everything]
        self.change_counter = 0

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
                    if not stat1.st_mtime == stat2.st_mtime:
                        sys.exit('### FAILED file ' + abs_dir_path2 + ' does not have same mtime')


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
                    if not stat1.st_mtime == stat2.st_mtime:
                        sys.exit('### FAILED file ' + abs_file_path2 + ' does not have same mtime')


    def cleanup(self):
        shutil.rmtree(self.data_dir)
        for change_number in range(len(self.changes) + 1):
            shutil.rmtree(self.data_dir + str(change_number))

class CozyBackup:

    def set_up(self):
        subprocess.call([COZY_MANAGER_PATH, 'start'])

        self.session_bus = dbus.SessionBus()
        self.manager = self.session_bus.get_object('org.freedesktop.Cozy', '/org/freedesktop/Cozy/Manager')


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
            prev_version_path = self.manager.get_previous_version_path(path, dbus_interface='org.freedesktop.Cozy.Manager')
            print '### PASSED get_pre_version_path'
            return prev_version_path
        except Exception, e:
            sys.exit('### FAILED get_pre_version_path: ' + str(e))

    def get_next_version_path(self, path):
        try:
            next_version_path = self.manager.get_next_version_path(path, dbus_interface='org.freedesktop.Cozy.Manager')
            print '### PASSED get_next_version_path'
            return next_version_path
        except Exception, e:
            sys.exit('### FAILED get_next_version_path: ' + str(e))


    def close_restore_mode(self):
        self.manager.close_restore_mode(dbus_interface='org.freedesktop.Cozy.Manager')

    def cleanup(self):
        subprocess.call([COZY_MANAGER_PATH, 'stop'])


try:

    setup = Setup()
    setup.set_up()

    cozy_backup = CozyBackup()
    cozy_backup.set_up()

    data_handler = DataHandler(DATA)
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

finally: # clean up in any case!
    try:
        data_handler.cleanup()
    except Exception, e:
        print str(e)
    try:
        cozy_backup.close_restore_mode()
        cozy_backup.cleanup()
    except Exception, e:
        print e
    try:
        setup.cleanup_configuration()
    except Exception, e:
        print e
#    clean_tmp_dir()

print '### EXITING SUCCESSFULLY'
