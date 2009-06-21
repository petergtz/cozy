#!/usr/bin/python

import sys
import os
import shutil
import subprocess
import cozy.configutils

TC_DIR = os.path.abspath(os.path.dirname(__file__))
ROOT_DIR = os.path.join(TC_DIR, '..')


COZY_MKFS_PATH = os.path.join(ROOT_DIR, 'cozy-mkfs.py')
COZY_BACKUP_PATH = os.path.join(ROOT_DIR, 'cozy-backup.py')
TEST_DATA = os.path.join(TC_DIR, 'TestData')

DOT_COZY = os.path.expanduser('~/.cozy')
DOT_COZY_BACKUP = os.path.expanduser('~/.cozy.orig.tc')
DATA = os.path.expanduser('~/Cozy-TC-Data')
DATA_CMP = os.path.expanduser('~/Cozy-TC-Data-CMP')
BACKUP_DIR = os.path.expanduser('~/Cozy-TC-Backup-Dir')


class Setup:
    def __init__(self):
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

class DataHandler:
    def __init__(self, data_dir):
        self.data_dir = data_dir

    def __do_it(self, data_dir):
        if self.change_counter == 0:
            shutil.copytree(TEST_DATA, data_dir, True)
        if self.change_counter == 1:
            pass

    def create_data(self):
        self.change_counter = 0
        self.__do_it(self.data_dir)
        self.__do_it(self.data_dir + str(self.change_counter))

    def change_data(self):
        shutil.copytree(self.data_dir + str(self.change_counter), self.data_dir + (self.change_counter + 1), True)
        self.change_counter += 1
        self.__do_it(self.data_dir)
        self.__do_it(self.data_dir + str(self.change_counter))

    def undo_change_data(self):
        if self.change_counter == 0:
            sys.exit('FAILED: change counter already 0')

        self.change_counter -= 1

    def __compare(self, path1, path2):
        pass

    def compare_data_with(self, path):
        self.__compare(self.data_dir + str(self.change_counter), path)

    def get_number_of_changes(self):
        return 1

    def cleanup(self):
        shutil.rmtree(self.data_dir)
        for change_number in range(self.get_number_of_changes()):
            shutil.rmtree(self.data_dir + str(change_number + 1))


def backup_data():
    cmdline = [COZY_BACKUP_PATH, '-f']
    print '### BACKING UP DATA: ' + ' '.join(cmdline)
    ret = subprocess.call(cmdline)
    if ret != 0:
        sys.exit('### FAILED backup_data')
    else:
        print '### PASSED backup_data'

def close_restore_mode():
    pass


try:
    setup = Setup()

    data_handler = DataHandler(DATA)

    data_handler.create_data()

    for change_number in range(data_handler.get_number_of_changes()):
        backup_data()
        data_handler.change_data()

    prev_version_path = DATA
    for change_number in range(data_handler.get_number_of_changes()):
        data_handler.undo_change_data()
        prev_version_path = get_prev_version_path(prev_version_path)
        data_handler.compare_data_with(prev_version_path)

finally: # clean up in any case!
    data_handler.cleanup()
    close_restore_mode()
    setup.cleanup_configuration()
#    clean_tmp_dir()

print '### EXITING SUCCESSFULLY'
