#!/usr/bin/python

import sys
import os

import logging

import unittest
import utils
from utils import *


if len(sys.argv) == 2:
    assert sys.argv[1].startswith('--prefix=')
    ROOT_DIR = sys.argv[1].replace('--prefix=', '')
else:
    ROOT_DIR = os.path.dirname(os.getcwd())

DATA_DIR = os.path.join(ROOT_DIR, 'scenario-tests', 'SimpleCozyFSTestData')
def test_data_dir(filename):
    return os.path.join(DATA_DIR, filename)

utils.COZYFS_PATH = os.path.join(ROOT_DIR, 'cozyfs', 'cozyfs.py')
utils.MKFS_PATH = os.path.join(ROOT_DIR, 'cozyfs', 'mkfs.cozyfs.py')
utils.SNAPSHOT_PATH = os.path.join(ROOT_DIR, 'cozyfs', 'cozyfssnapshot.py')

TARGET_DIR = '/tmp/cozy-device-dir'
utils.TARGET_DIR = TARGET_DIR
MOUNT_PATH = '/tmp/cozy-mount-point'


def init_logger():
    log = logging.getLogger('cozyfs_test')
    log.setLevel(logging.DEBUG)
    formatter = logging.Formatter('  File "%(pathname)-10s", line %(lineno)-3d, in %(funcName)s: %(message)s')
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)
    log.addHandler(handler)

    debug_handler = logging.FileHandler('/tmp/cozyfs_test_log', 'w')
    debug_handler.setFormatter(formatter)
    debug_handler.setLevel(logging.DEBUG)
    log.addHandler(debug_handler)
    return log


def clean_up_env():
    if is_mounted(MOUNT_PATH):
        umount(MOUNT_PATH)
    shutil.rmtree(MOUNT_PATH, ignore_errors=True)
    shutil.rmtree(TARGET_DIR, ignore_errors=True)

utils.log = init_logger()

class CozyFSTest(unittest.TestCase):

    def setUp(self):
        clean_up_env()
        self.initial_version = make_cozyfs(target_dir=TARGET_DIR, backup_id=666)
        os.mkdir(MOUNT_PATH)

    def tear_down_after_successful_completion(self):
        check_tmp_dir(TARGET_DIR)
        clean_up_env()


    def test_lots_of_softlinks(self):
        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            copy(os.path.join(DATA_DIR, 'file1'), 'file1')
            for i in range(100):
                softlink('file1', 'a_new_softlink' + str(i))
        self.tear_down_after_successful_completion()

    def do_not_test_simple_file_functions(self):

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            mkdir('folder1')
            neg_mkdir('folder1')

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            neg_mkdir('folder1')
            rename('folder1', 'folder1_renamed')
            copy(os.path.join(DATA_DIR, 'file1'), 'file1')
            rename('file1', 'folder1_renamed/file1')

        version2 = snapshot(TARGET_DIR, 666)

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            mkdirs('folder2/folder3')
            copy(os.path.join(DATA_DIR, 'file1'), 'file2')
            copy(os.path.join(DATA_DIR, 'file2'), './folder1_renamed/file1')
            copy(os.path.join(DATA_DIR, 'file1'), 'overwriter')
            readdir('.', ['folder1_renamed', 'folder2', 'file2', 'overwriter'])

        snapshot(TARGET_DIR, 666)

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            add_string_to_file('overwriter', 'THIS IS THE MODIFICATION')
            copy(os.path.join(DATA_DIR, 'file1'), 'overwriter')
            mkdir('folder4')
            mkdir('folder5')
            chown('folder5', 1000, 1111)
            rmtree('folder5')
            rm('folder1_renamed/file1')
            copy(os.path.join(DATA_DIR, 'image1.jpg'), 'image.jpg')
            copy(os.path.join(DATA_DIR, 'long_text'), 'long_text')
            hardlink('long_text', 'folder4/hardlink_to_long_text')
            rm('long_text')
            assert_file_contents_equal(os.path.join(DATA_DIR, 'long_text'), 'folder4/hardlink_to_long_text')
            softlink('folder4/hardlink_to_long_text', 'softlink_to_long_text')
            hardlink('folder4/hardlink_to_long_text', 'a_new_hardlink')

        version = snapshot(TARGET_DIR, 666)

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            add_string_to_file('overwriter', 'AND THIS IS NUMBER 2')
            assert_file_contents_equal(os.path.join(DATA_DIR, 'long_text'), 'folder4/hardlink_to_long_text')
            assert_file_contents_equal('softlink_to_long_text', 'folder4/hardlink_to_long_text')

        snapshot(TARGET_DIR, 666)

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            assert_file_contents_equal('a_new_hardlink', 'folder4/hardlink_to_long_text')
            add_string_to_file('a_new_hardlink', 'HARDLINK_ADDITION')
            assert_file_contents_equal('a_new_hardlink', 'folder4/hardlink_to_long_text')
            rm('folder4/hardlink_to_long_text')


        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, backup_id=666, version=version):
            assert_file_contents_equal('a_new_hardlink', os.path.join(DATA_DIR, 'long_text'))


        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666, version2):
            assert_exists_not('folder4')
            neg_mkdir('folder4')

        self.tear_down_after_successful_completion()

    def test_simple_file_functions_without_hardlinks(self):

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            mkdir('folder1')
            neg_mkdir('folder1')

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            neg_mkdir('folder1')
            rename('folder1', 'folder1_renamed')
            copy(os.path.join(DATA_DIR, 'file1'), 'file1')
            rename('file1', 'folder1_renamed/file1')

        version2 = snapshot(TARGET_DIR, 666)

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            mkdirs('folder2/folder3')
            copy(os.path.join(DATA_DIR, 'file1'), 'file2')
            copy(os.path.join(DATA_DIR, 'file2'), './folder1_renamed/file1')
            copy(os.path.join(DATA_DIR, 'file1'), 'overwriter')
            readdir('.', ['folder1_renamed', 'folder2', 'file2', 'overwriter'])

        snapshot(TARGET_DIR, 666)

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            add_string_to_file('overwriter', 'THIS IS THE MODIFICATION')
            copy(os.path.join(DATA_DIR, 'file1'), 'overwriter')
            mkdir('folder4')
            mkdir('folder5')
            chown('folder5', 1000, 1111)
            rmtree('folder5')
            rm('folder1_renamed/file1')
            copy(os.path.join(DATA_DIR, 'image1.jpg'), 'image.jpg')
            copy(os.path.join(DATA_DIR, 'long_text'), 'long_text')
            copy('long_text', 'folder4/hardlink_to_long_text')
            rm('long_text')
            assert_file_contents_equal(os.path.join(DATA_DIR, 'long_text'), 'folder4/hardlink_to_long_text')
            softlink('folder4/hardlink_to_long_text', 'softlink_to_long_text')
            copy('folder4/hardlink_to_long_text', 'a_new_hardlink')

        version = snapshot(TARGET_DIR, 666)

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            add_string_to_file('overwriter', 'AND THIS IS NUMBER 2')
            assert_file_contents_equal(os.path.join(DATA_DIR, 'long_text'), 'folder4/hardlink_to_long_text')
            assert_file_contents_equal('softlink_to_long_text', 'folder4/hardlink_to_long_text')

        snapshot(TARGET_DIR, 666)

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            assert_file_contents_equal('a_new_hardlink', 'folder4/hardlink_to_long_text')
            add_string_to_file('a_new_hardlink', 'HARDLINK_ADDITION')
#            assert_file_contents_equal('a_new_hardlink', 'folder4/hardlink_to_long_text')
            rm('folder4/hardlink_to_long_text')


        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, backup_id=666, version=version):
            assert_file_contents_equal('a_new_hardlink', os.path.join(DATA_DIR, 'long_text'))


        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666, version2):
            assert_exists_not('folder4')
            neg_mkdir('folder4')

        self.tear_down_after_successful_completion()

    def do_not_test_simple_hardlink(self):
        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            copy(os.path.join(DATA_DIR, 'long_text'), 'long_text')
            hardlink('long_text', 'a_new_hardlink')

        version = snapshot(TARGET_DIR, 666)

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            assert_file_contents_equal(os.path.join(DATA_DIR, 'long_text'), 'long_text')

        self.tear_down_after_successful_completion()

    def do_not_test_hardlink_still_correct_after_deleting_original_file(self):
        version = snapshot(TARGET_DIR, 666)

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            copy(os.path.join(DATA_DIR, 'long_text'), 'long_text')
            hardlink('long_text', 'a_new_hardlink')

        snapshot(TARGET_DIR, 666)

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            assert_file_contents_equal('a_new_hardlink', 'long_text')
            add_string_to_file('a_new_hardlink', 'HARDLINK_ADDITION')
            rm('long_text')

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, backup_id=666, version=version):
            assert_file_contents_equal('a_new_hardlink', os.path.join(DATA_DIR, 'long_text'))

        self.tear_down_after_successful_completion()


    def test_diff_files(self):
        snapshot(TARGET_DIR, 666)

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            copy(os.path.join(DATA_DIR, 'long_text'), 'samefile1')
            copy(os.path.join(DATA_DIR, 'long_text'), 'samefile2')

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            copy(os.path.join(DATA_DIR, 'long_text'), 'myfile')

        snapshot(TARGET_DIR, 666)

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            copy(os.path.join(DATA_DIR, 'long_text'), 'samefile1')
            copy(os.path.join(DATA_DIR, 'long_text'), 'samefile2')

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            copy(os.path.join(DATA_DIR, 'long_text_with_change'), 'myfile')
            assert_file_in_pool_is_diff('myfile',
                                os.path.join(DATA_DIR, 'long_text'), os.path.join(DATA_DIR, 'long_text_with_change'))

        snapshot(TARGET_DIR, 666)

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            copy(os.path.join(DATA_DIR, 'long_text_with_change'), 'mycopy')
            assert_file_in_pool_is_diff('mycopy',
                                os.path.join(DATA_DIR, 'long_text'), os.path.join(DATA_DIR, 'long_text_with_change'))

        snapshot(TARGET_DIR, 666)

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            copy(os.path.join(DATA_DIR, 'changed-more-version'), 'mycopy')
            assert_file_in_pool_is_diff('mycopy',
                                os.path.join(DATA_DIR, 'long_text_with_change'), os.path.join(DATA_DIR, 'changed-more-version'))

        self.tear_down_after_successful_completion()

    def test_simple_diff_files(self):
        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            copy(test_data_dir('long_text'), 'myfile')

        snapshot(TARGET_DIR, 666)

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            copy(test_data_dir('long_text_with_change'), 'myfile')
            assert_file_in_pool_is_diff('myfile', test_data_dir('long_text'), test_data_dir('long_text_with_change'))

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666, version=self.initial_version):
            assert_file_contents_equal(test_data_dir('long_text'), 'myfile')

        self.tear_down_after_successful_completion()


    def test_chained_diff_files(self):
        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            copy(test_data_dir('long_text'), 'myfile')

        version2 = snapshot(TARGET_DIR, 666)

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            copy(test_data_dir('long_text_with_change'), 'myfile')
            assert_file_in_pool_is_diff('myfile', test_data_dir('long_text'), test_data_dir('long_text_with_change'))

        snapshot(TARGET_DIR, 666)

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            copy(test_data_dir('long_text_with_another_change'), 'myfile')
            assert_file_in_pool_is_diff('myfile', test_data_dir('long_text_with_change'), test_data_dir('long_text_with_another_change'))

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666, version=version2):
            assert_file_contents_equal(test_data_dir('long_text_with_change'), 'myfile')

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666, version=self.initial_version):
            assert_file_contents_equal(test_data_dir('long_text'), 'myfile')

        self.tear_down_after_successful_completion()

    def test_copy_same_file_over(self):
        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            copy(test_data_dir('long_text'), 'myfile')

        snapshot(TARGET_DIR, 666)

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            copy(test_data_dir('long_text'), 'myfile')
            assert_file_in_pool_is_diff('myfile', test_data_dir('long_text'), test_data_dir('long_text'))

        self.tear_down_after_successful_completion()

    def test_copy_file_when_identical_file_is_already_in_pool_as_non_diff(self):

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            copy(os.path.join(DATA_DIR, 'file1'), 'file1')
            rename('file1', 'file1_renamed')

        version2 = snapshot(TARGET_DIR, 666)

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            copy(os.path.join(DATA_DIR, 'file1'), 'file2')
            copy(os.path.join(DATA_DIR, 'file2'), 'file1_renamed')
            copy(os.path.join(DATA_DIR, 'file1'), 'overwriter')

        snapshot(TARGET_DIR, 666)

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            add_string_to_file('overwriter', 'THIS IS THE MODIFICATION')

        self.tear_down_after_successful_completion()

    def test_remove_file_after_snapshot(self):
        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            copy(os.path.join(DATA_DIR, 'file1'), 'file1')

        snapshot(TARGET_DIR, 666)

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            rm('file1')

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666, version=self.initial_version):
            assert_file_contents_equal(os.path.join(DATA_DIR, 'file1'), 'file1')

        self.tear_down_after_successful_completion()


    def test_simple_hardlink(self):
        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            copy(os.path.join(DATA_DIR, 'file1'), 'file1')
            hardlink('file1', 'hardlink')

        self.tear_down_after_successful_completion()


    def test_simple_hardlink_after_removing_original(self):
        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            copy(os.path.join(DATA_DIR, 'file1'), 'file1')
            hardlink('file1', 'hardlink')
            rm('file1')
            assert_file_contents_equal(os.path.join(DATA_DIR, 'file1'), 'hardlink')

        self.tear_down_after_successful_completion()


    def test_hardlink_after_removing_original_after_snapshot(self):
        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            copy(os.path.join(DATA_DIR, 'file1'), 'file1')
            hardlink('file1', 'hardlink')

        snapshot(TARGET_DIR, 666)

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            rm('file1')
            assert_file_contents_equal(os.path.join(DATA_DIR, 'file1'), 'hardlink')

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666, version=self.initial_version):
            assert_file_contents_equal(os.path.join(DATA_DIR, 'file1'), 'file1')
            assert_file_contents_equal(os.path.join(DATA_DIR, 'file1'), 'hardlink')

        self.tear_down_after_successful_completion()


    def do_not_test_change_in_one_hardlink_does_not_change_other_hardlink_in_previous_version(self):

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            copy(os.path.join(DATA_DIR, 'long_text'), 'hardlink_to_long_text')
            hardlink('hardlink_to_long_text', 'a_new_hardlink')
#            copy(os.path.join(DATA_DIR, 'long_text'), 'a_new_hardlink')
#            hardlink('a_new_hardlink', 'hardlink_to_long_text')

        snapshot(TARGET_DIR, 666)

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, 666):
            assert_file_contents_equal('a_new_hardlink', 'hardlink_to_long_text')
            copy(os.path.join(DATA_DIR, 'long_text_with_change'), 'a_new_hardlink')
            assert_file_contents_equal('a_new_hardlink', 'hardlink_to_long_text')
#            rm('hardlink_to_long_text')

        with mounted_filesystem(TARGET_DIR, MOUNT_PATH, backup_id=666, version=self.initial_version):
            assert_file_contents_equal('hardlink_to_long_text', os.path.join(DATA_DIR, 'long_text'))
            assert_file_contents_equal('a_new_hardlink', os.path.join(DATA_DIR, 'long_text'))

        self.tear_down_after_successful_completion()


if __name__ == '__main__':
    suite = unittest.TestSuite((CozyFSTest('do_not_test_change_in_one_hardlink_does_not_change_other_hardlink_in_previous_version'),))
#    unittest.TextTestRunner().run(suite)
    unittest.main()
