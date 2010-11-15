#!/usr/bin/python

# Cozy Backup Solution
# Copyright (C) 2010  Peter Goetz
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


import os
from contextlib import contextmanager
import subprocess
from time import sleep
import time
import stat
import shutil
from cozyutils.md5sum import md5sum
import tempfile



SUCCESSFUL_MOUNT_TIMEOUT = 2

log = None


def set_logger(logger):
    global log
    log = logger



def make_cozyfs(target_dir, backup_id):
    os.mkdir(target_dir)
    cmdline = [MKFS_PATH, target_dir, str(backup_id)]
    log.info(' '.join(cmdline))
    subprocess.check_call(cmdline, stdout=subprocess.PIPE)


@contextmanager
def mounted_filesystem(device_dir, mount_point, backup_id, version=None, as_readonly=False):
    mount(device_dir, mount_point, backup_id, version, as_readonly)
    try:
        yield
    finally:
        umount(mount_point)

def mount(device_dir, mount_point, backup_id, version=None, as_readonly=False):
    cmdline = build_mount_cmdline(device_dir, mount_point, backup_id, version, as_readonly)
    log.info(' '.join(cmdline))
    process = subprocess.Popen(cmdline, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process.args = cmdline
    try:
        wait_until(is_mounted, mount_point)
    except:
        handle_return_code_of(process)
    os.chdir(mount_point)

def build_mount_cmdline(device_dir, mount_point, backup_id, version, as_readonly):
    cmdline = [COZYFS_PATH, device_dir, mount_point, '-b', str(backup_id)]
    if version is not None:
        cmdline.append('-v')
        cmdline.append(str(version))
    if as_readonly:
        cmdline.append('-r')
    return cmdline

def handle_return_code_of(process):
    if  process.returncode == 3:
        raise Exception('Error: Mount failed because database couldn''t be found.')
    elif  process.returncode == 4:
        raise Exception('Error: Mount failed because filesystem is locked.')
    else:
        (stdoutdata, stderrdata) = process.communicate()
        raise Exception('Error: Mount cmd :  ' + ' '.join(process.args) + ' failed due to errors: ' + str(stderrdata) + str(stdoutdata))


def umount(mountpath):
    os.chdir('/')
    cmdline = ['fusermount', '-z', '-u', mountpath]
    log.info(' '.join(cmdline))
    subprocess.check_call(cmdline)
    wait_until(is_unmounted, mountpath)
    sleep(1)

def wait_until(mount_condition, mount_point):
    start_time = time.time()
    time_passed = 0

    while time_passed < SUCCESSFUL_MOUNT_TIMEOUT:
        if mount_condition(mount_point):
            return
        time_passed = time.time() - start_time
    raise Exception("Timeout")

def is_mounted(mount_point):
    with open('/etc/mtab', 'r') as mtab_file:
        return mtab_file.read().find(mount_point) != -1

def is_unmounted(mount_point):
    return not is_mounted(mount_point)


def snapshot(target_dir, backup_id):
    cmdline = [SNAPSHOT_PATH, target_dir, str(backup_id)]
    log.info(' '.join(cmdline))
    process = subprocess.Popen(cmdline, stdout=subprocess.PIPE)
    version = process.communicate()[0]
    log.debug('Returned version: ' + version)
    return version

def assert_exists(path):
    if not os.access(path, os.F_OK) or not os.path.exists(path):
        raise Exception('Could not access ' + path)

def assert_exists_not(path):
    if os.path.exists(path) and os.access(path, os.F_OK):
        raise Exception('Could accidently access ' + path)

def assert_file_contents_equal(filename1, filename2):
    with open(filename1) as file1: content1 = file1.read()
    with open(filename2) as file2: content2 = file2.read()
    if content1 != content2:
        log.debug('compare failed: ' + filename1 + ' != ' + filename2 + ': \n' +
                          content1 + '\n\n!=\n\n' + content2)
        raise Exception('compare failed: ' + filename1 + ' != ' + filename2 + '.')

def binary_diffs_equal(expected, actual):
    return expected[-50:] == actual[-50:]

def binary_dump(binary_data):
    for c in binary_data:
        if ord(c) < 32 or ord(c) > 127:
            sys.stderr.write("*")
        else:
            sys.stderr.write(c)

def assert_file_in_pool_is_diff(file, original, new):
    filename_in_pool = md5sum(original)
    with open(os.path.join(TARGET_DIR, 'FilePool', filename_in_pool), 'rb') as file_in_pool:
        content_of_file_in_pool = file_in_pool.read()
    size_of_file_in_pool = len(content_of_file_in_pool)

    (fd, filename_expected) = tempfile.mkstemp()
    subprocess.check_call(['xdelta3', '-f', '-e', '-s', new, original, filename_expected])
    with open(filename_expected, 'rb') as filehandle_expected:
        expected_content = filehandle_expected.read()
        expected_size = len(expected_content)
    os.remove(filename_expected)
    if not binary_diffs_equal(expected_content, content_of_file_in_pool):
        log.debug('File in pool is not a diff: ' + file + '\n' +
                          expected_content + '\n\n!=\n\n' + content_of_file_in_pool)
        raise Exception('File in pool is not a diff: ' + file)
#    if abs(expected_size - size_of_file_in_pool) > 120:


def mkdir(path):
    log.info(path)
    os.mkdir(path)
    assert_exists(path)

    mode = os.stat(path)[stat.ST_MODE]
    if not stat.S_ISDIR(mode):
        raise Exception(path + ' is not a directory')


def chown(path, uid, gid):
    log.info(path + ' ' + str(uid) + ' ' + str(gid))
    os.chown(path, uid, gid)

    actual_gid = os.stat(path)[stat.ST_GID]
    actual_uid = os.stat(path)[stat.ST_UID]
    if actual_gid != gid or actual_uid != uid:
        raise Exception(str(actual_gid) + '!=' + str(gid) + ' and ' + str(actual_uid) + '!=' + str(uid))

def readdir(path, files):
    log.info(path)
    actual_files = os.listdir(path)
    for actual_file in actual_files:
        if actual_file not in files:
            raise Exception('file: ' + actual_file + 'should not exist')
    for file in files:
        if file not in actual_files:
            raise Exception('file: ' + file + 'should exist')

def mkdirs(path):
    log.info(path)
    os.makedirs(path)
    assert_exists(path)

    mode = os.stat(path)[stat.ST_MODE]
    if not stat.S_ISDIR(mode):
        raise Exception(path + ' is not a directory')


def neg_mkdir(path):
    try:
        log.info(path)
        os.mkdir(path)
    except Exception:
        pass # that is what we expect here
    else:
        raise Exception('neg_mkdir: ' + path + ': folder is not allowed to be created')



def rename(source, target):
    log.info(source + ' -> ' + target)
    os.rename(source, target)
    assert_exists(target)
    assert_exists_not(source)

def rm(path):
    log.info(path)
    os.remove(path)
    assert_exists_not(path)

def rmtree(path):
    log.info(path)
    shutil.rmtree(path)
    assert_exists_not(path)

def copy(source, target):
    log.info(source + ' -> ' + target)
    shutil.copy(source, target)
    assert_exists(source)
    assert_exists(target)
    assert_file_contents_equal(source, target)


def add_string_to_file(filename, string):
    log.info(filename + ' add: ' + string)
    with open(filename, 'r') as fh:
        orig_content = fh.read()

    with open(filename, 'w') as fh:
        fh.write(orig_content + string)

    with open(filename, 'r') as fh:
        new_content = fh.read()

    if new_content != orig_content + string:
        raise Exception('Adding string to file failed:\n expected: %s\nactual: %s' %
                        (orig_content + string, new_content))

def hardlink(source, target):
    log.info(source + ' -> ' + target)
    os.link(source, target)

    assert_exists(source)
    assert_exists(target)
    assert_file_contents_equal(source, target)


def softlink(source, target):
    log.info(source + ' -> ' + target)
    os.symlink(source, target)

    assert_exists(source)
    assert_exists(target)

    assert_file_contents_equal(source, target)

    if len(os.readlink(target)) != os.lstat(target).st_size:
        raise Exception('size comparison failed: ' + str(len(os.readlink(target))) + '!=' + str(os.stat(target).st_size))


def check_tmp_dir(dev_dir):
    files = os.listdir(dev_dir + '/Tmp')
    if len(files) > 0:
        log.warning('tmp dir is not empty\n' + '\n'.join(files))

