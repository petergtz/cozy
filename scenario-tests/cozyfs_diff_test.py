#!/usr/bin/python

from __future__ import with_statement
import sys
import os
import shutil
from time import sleep
import time
import subprocess
import sqlite3
import stat

import pwd
import tempfile
import traceback
from cozyutils.md5sum import md5sum

TC_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(TC_DIR, 'SimpleCozyFSTestData')
ROOT_DIR = os.path.dirname(TC_DIR)


COZYFS_PATH = os.path.join(ROOT_DIR, 'cozyfs', 'cozyfs.py')
MKFS_PATH = os.path.join(ROOT_DIR, 'cozyfs', 'mkfs.cozyfs.py')
SNAPSHOT_PATH = os.path.join(ROOT_DIR, 'cozyfs', 'cozyfssnapshot.py')
DBFILE = "fsdb"

loginname = pwd.getpwuid(os.getuid())[0]
TARGET_DIR = tempfile.mkdtemp(prefix='cozy-' + loginname)

SUCCESSFUL_MOUNT_TIMEOUT = 2

os.environ['COVERAGE_FILE'] = os.path.join(TC_DIR, 'coveragedata')


def make_cozyfs(target_dir, backup_id):
    if not os.path.exists(TARGET_DIR):
        print >> sys.stderr, 'Please provide the file:', TARGET_DIR

    cmdline = [MKFS_PATH, target_dir, str(backup_id)]
    print '### MAKING FS: ' + ' '.join(cmdline)
    try:
        process = subprocess.Popen(cmdline, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception, e:
        print e
        raise

    (stdout, stderr) = process.communicate()

    print stdout
    return stdout


def mount(device_dir, mount_point, backup_id, version=None, as_readonly=False):
    os.mkdir(mount_point)
    try:
#        subprocess.call(['python-coverage', '-e'])
        cmdline = __build_cmdline(device_dir, mount_point, backup_id, version, as_readonly)
        print '### MOUNTING: ' + ' '.join(cmdline)
        process = subprocess.Popen(cmdline)
        process.args = cmdline
        __wait_until_filesystem_is_mounted(process, mount_point)
        os.chdir(mount_point)

    except Exception, e:
        sys.exit('### FAILED mount. Error: ' + str(e))


def __build_cmdline(device_dir, mount_point, backup_id, version, as_readonly):
#    cmdline = ['coverage', '-x', COZYFS_PATH, device_dir, mount_point, '-b', str(backup_id)]
#    cmdline = ['python', '-m', 'trace', '--count', '-C', '/home/peter/Projects/Cozy/scenario-tests/coverage-report', COZYFS_PATH, device_dir, mount_point, '-b', str(backup_id)]
    cmdline = [COZYFS_PATH, device_dir, mount_point, '-b', str(backup_id)]
    if version is not None:
        cmdline.append('-v')
        cmdline.append(str(version))
    if as_readonly:
        cmdline.append('-r')
    return cmdline

def __wait_until_filesystem_is_mounted(process, mount_point):
    start_time = time.time()
    time_passed = 0

    while (time_passed < SUCCESSFUL_MOUNT_TIMEOUT):
        mtab_file = open('/etc/mtab', 'r')
        mtab_string = mtab_file.read()
        mtab_file.close()
        if mtab_string.find(mount_point) != -1:
            return
        time_passed = time.time() - start_time
    __handle_return_code_of(process)

def __handle_return_code_of(process):
    if  process.returncode == 3:
        raise Exception('Error: Mount failed because database couldn''t be found.')
    elif  process.returncode == 4:
        raise Exception('Error: Mount failed because filesystem is locked.')
    else:
        (stdoutdata, stderrdata) = process.communicate()
        raise Exception('Error: Mount cmd :  ' + ' '.join(process.args) + 'failed due to errors: ' + str(stderrdata) + str(stdoutdata))




def snapshot(target_dir, backup_id, based_on_version=None):
    cmdline = [SNAPSHOT_PATH, target_dir, str(backup_id)]
    if based_on_version is not None:
        cmdline.extend(['-b', str(based_on_version)])
    print '### SNAPSHOTTING: ' + ' '.join(cmdline)
    try:
        process = subprocess.Popen(cmdline, stdout=subprocess.PIPE)
    except Exception, e:
        print e
        raise

    version = process.communicate()[0]
    print version
    return version


def mkdir(path):
    try:
        os.mkdir(path)
        if not os.access(path, os.F_OK):
            os.removedirs(path)
            raise Exception('Could not access ' + path)

        mode = os.stat(path)[stat.ST_MODE]
        if not stat.S_ISDIR(mode):
            os.removedirs(path)
            raise Exception(path + ' is not a directory')

    except Exception, e:
        sys.exit('### FAILED mkdir ' + path + ': ' + str(e))
    else:
        print '### PASSED mkdir', path

def chown(path, uid, gid):
    try:
        os.chown(path, uid, gid)

        actual_gid = os.stat(path)[stat.ST_GID]
        actual_uid = os.stat(path)[stat.ST_UID]
        if actual_gid != gid or actual_uid != uid:
            raise Exception(str(actual_gid) + '!=' + str(gid) + ' and ' + str(actual_uid) + '!=' + str(uid))

    except Exception, e:
        sys.exit('### FAILED chown ' + path + ': ' + str(e))
    else:
        print '### PASSED chown', path

def readdir(path, files):
    try:
        actual_files = os.listdir(path)
        for actual_file in actual_files:
            if actual_file not in files:
                raise Exception('file: ' + actual_file + 'should not exist')
        for file in files:
            if file not in actual_files:
                raise Exception('file: ' + file + 'should exist')

    except Exception, e:
        sys.exit('### FAILED readdir ' + path + ': ' + str(e))
    else:
        print '### PASSED readdir', path

def mkdirs(path):
    try:
        os.makedirs(path)
        if not os.access(path, os.F_OK):
            os.removedirs(path)
            raise Exception('Could not access ' + path)

        mode = os.stat(path)[stat.ST_MODE]
        if not stat.S_ISDIR(mode):
            os.removedirs(path)
            raise Exception(path + ' is not a directory')

    except Exception, e:
        sys.exit('### FAILED mkdirs ' + path + ': ' + str(e))
    else:
        print '### PASSED mkdirs', path

def neg_mkdir(path):
    try:
        os.mkdir(path)
    except Exception:
        print '### PASSED neg_mkdir', path
    else:
        sys.exit('### FAILED neg_mkdir ' + path + ': folder is not allowed to be created')



def move(source, target):
    try:
        shutil.move(source, target)

        if not os.access(target, os.F_OK):
            raise Exception('Could not access ' + target)

        if os.access(source, os.F_OK):
            raise Exception('Could access ' + source)

    except Exception, e:
        sys.exit('### FAILED move ' + source + ' ' + target + ': ' + str(e))
    else:
        print '### PASSED move', source, target

def rm(path):
    try:
        os.remove(path)

        if os.access(path, os.F_OK):
            raise Exception('Could accidently access ' + path)

    except Exception, e:
        sys.exit('### FAILED remove ' + path + ': ' + str(e))
    else:
        print '### PASSED remove', path

def rmtree(path):
    try:
        shutil.rmtree(path)

        if os.access(path, os.F_OK):
            raise Exception('Could accidently access ' + path)

    except Exception, e:
        sys.exit('### FAILED remove ' + path + ': ' + str(e))
    else:
        print '### PASSED remove', path




#def write_file(path,content_file):
#    try:
#        file=open(path,'w')
#        file
#        shutil.move(source, target)
#
#        if not os.access(target,os.F_OK):
#            raise Exception('Could not access '+target)
#
#        if os.access(source,os.F_OK):
#            raise Exception('Could access '+source)
#
#    except Exception, e:
#        sys.exit('### FAILED move '+source+' '+target+': '+str(e))
#    else:
#        print '### PASSED move', source, target

def copy(source, target):
    try:
        shutil.copy(source, target)
        if not os.access(target, os.F_OK):
            raise Exception('Could not access ' + target)
        target_content = open(target).read()
        source_content = open(source).read()
        if target_content != source_content:
            print 'source: ', source_content
            print
            print 'target: ', target_content
            raise Exception('compare failed: ' + source + ' ' + target)

# FIXME: add size comparison here!!!

    except Exception, e:
        sys.exit('### FAILED copy ' + source + ' ' + target + ': ' + str(e))
    else:
        print '### PASSED copy', source, target

def add_string_to_file(filename, string):
    try:
        with open(filename, 'r') as fh:
            orig_content = fh.read()

#        with open(filename, 'r+') as fh:
#            fh.write(string)

        with open(filename, 'w') as fh:
            fh.write(orig_content + string)

        with open(filename, 'r') as fh:
            new_content = fh.read()

        if new_content != orig_content + string:
            raise Exception('Adding string to file failed:\n expected: %s\nactual: %s' %
                            (orig_content + string, new_content))

    except Exception, e:
        sys.exit('### FAILED add string to file ' + filename + ': ' + str(e))
    else:
        print '### PASSED add string to file', filename

def hardlink(source, target):
    try:
        os.link(source, target)

        if not os.access(target, os.F_OK):
            raise Exception('Could not access ' + target)
        if open(target).read() != open(source).read():
            raise Exception('compare failed: ' + source + ' ' + target)

    except Exception, e:
        sys.exit('### FAILED hardlink ' + source + ' ' + target + ': ' + str(e))
    else:
        print '### PASSED hardlink', source, target

def softlink(source, target):
    try:
        os.symlink(source, target)

        if not os.access(target, os.F_OK):
            raise Exception('Could not access ' + target)
        if open(target).read() != open(source).read():
            raise Exception('compare failed: ' + source + ' ' + target)
        if len(os.readlink(target)) != os.lstat(target).st_size:
            raise Exception('size comparison failed: ' + str(len(os.readlink(target))) + '!=' + str(os.stat(target).st_size))
    except Exception, e:
        sys.exit('### FAILED softlink ' + source + ' ' + target + ': ' + str(e))
    else:
        print '### PASSED softlink', source, target

def exists(path):
    if not os.access(path, os.F_OK):
        sys.exit('### FAILED exists ' + path)
    else:
        print '### PASSED exists', path

def neg_exists(path):
    if os.access(path, os.F_OK):
        sys.exit('### FAILED neg_exists ' + path)
    else:
        print '### PASSED neg_exists', path




def compare_file_content(file1, file2):
    if open(file2).read() != open(file1).read():
        sys.exit('### FAILED compare ' + file1 + ' ' + file2)
    else:
        print '### PASSED compare', file1, file2




def check_tmp_dir():
    files = os.listdir(TARGET_DIR + '/Tmp')
#    files.remove('.svn')
    if len(files) > 0:
        sys.exit('### WARNING tmp dir is not empty\n' + '\n'.join(files))


def clean_db():
    db = sqlite3.connect(TARGET_DIR + "/" + DBFILE)
    db.execute('DELETE FROM DataPaths')
    db.execute('DELETE FROM size')
    db.execute('DELETE FROM mode')
    db.execute('DELETE FROM atime')
    db.execute('DELETE FROM mtime')
    db.execute('DELETE FROM ctime')
    db.execute('DELETE FROM gid')
    db.execute('DELETE FROM uid')
    db.execute('DELETE FROM Hardlinks')
    db.execute('DELETE FROM Nodes')
    db.commit()

def clean_mount_dir():
    os.system('rm -rf ' + TARGET_DIR)



def clean_file_pool():
    os.system('rm -rf ' + os.path.join(TARGET_DIR, 'FilePool/*'))


def clean_tmp_dir():
    os.system('rm -rf ' + os.path.join(TARGET_DIR, 'Tmp/*'))


def umount(mountpath):
    print '### UNMOUNTING'
    os.chdir('/')
    os.system('fusermount -z -u ' + mountpath)
    __wait_until_filesystem_is_unmounted(mountpath)
    shutil.rmtree(mountpath)

def __wait_until_filesystem_is_unmounted(mount_point):
    start_time = time.time()
    time_passed = 0

    while (time_passed < SUCCESSFUL_MOUNT_TIMEOUT):
        mtab_file = open('/etc/mtab', 'r')
        mtab_string = mtab_file.read()
        mtab_file.close()
        if mtab_string.find(mount_point) > -1:
            return
        time_passed = time.time() - start_time

def remove_cozyfs(target_dir, backup_id):
    os.rmdir(os.path.join(TARGET_DIR, 'FilePool'))
    os.rmdir(os.path.join(TARGET_DIR, 'Tmp'))
    os.remove(os.path.join(TARGET_DIR, DBFILE))


mountpath = '/tmp/cozy-TestCase'

def binary_diffs_equal(expected, actual):
    return expected[-50:] == actual[-50:]

def assert_file_in_pool_is_diff(file, original, new):
    filename_in_pool = md5sum(file)
    with open(os.path.join(TARGET_DIR, 'FilePool', filename_in_pool), 'rb') as file_in_pool:
        content_of_file_in_pool = file_in_pool.read()
        size_of_file_in_pool = len(content_of_file_in_pool)

    (fd, filename_expected) = tempfile.mkstemp()
    subprocess.check_call(['xdelta3', '-f', '-e', '-s', original, new, filename_expected])
    with open(filename_expected, 'rb') as filehandle_expected:
        expected_content = filehandle_expected.read()
        expected_size = len(expected_content)
    os.remove(filename_expected)
    if not binary_diffs_equal(expected_content, content_of_file_in_pool):
#    if abs(expected_size - size_of_file_in_pool) > 120:
        print >> sys.stderr, "Expected content:"
        for c in expected_content:
            if ord(c) < 32 or ord(c) > 127:
                sys.stderr.write("*")
            else:
                sys.stderr.write(c)
        print >> sys.stderr
        print >> sys.stderr, "Actual content:"
        for c in content_of_file_in_pool:
            if ord(c) < 32 or ord(c) > 127:
                sys.stderr.write("*")
            else:
                sys.stderr.write(c)
        print >> sys.stderr
        sys.exit('### FAILED file in pool is not a diff ' + file)
    else:
        print '### PASSED file in pool is diff', file


try:
    make_cozyfs(target_dir=TARGET_DIR, backup_id=666)
    time.sleep(1)
    snapshot(TARGET_DIR, 666)

    mount(TARGET_DIR, mountpath, 666)
    copy(os.path.join(DATA_DIR, 'non-favorites-version'), 'samefile1')
    copy(os.path.join(DATA_DIR, 'non-favorites-version'), 'samefile2')
    umount(mountpath)

    mount(TARGET_DIR, mountpath, 666)
    copy(os.path.join(DATA_DIR, 'non-favorites-version'), 'myfile')
    umount(mountpath)

    version2 = snapshot(TARGET_DIR, 666)

    mount(TARGET_DIR, mountpath, 666)
    copy(os.path.join(DATA_DIR, 'non-favorites-version'), 'samefile1')
    copy(os.path.join(DATA_DIR, 'non-favorites-version'), 'samefile2')
    umount(mountpath)

    mount(TARGET_DIR, mountpath, 666, version2)
    copy(os.path.join(DATA_DIR, 'favorites-version'), 'myfile')

    assert_file_in_pool_is_diff('myfile',
                        os.path.join(DATA_DIR, 'non-favorites-version'), os.path.join(DATA_DIR, 'favorites-version'))

    umount(mountpath)

    version3 = snapshot(TARGET_DIR, 666)

    mount(TARGET_DIR, mountpath, 666, version3)
    copy(os.path.join(DATA_DIR, 'favorites-version'), 'mycopy')

    assert_file_in_pool_is_diff('mycopy',
                        os.path.join(DATA_DIR, 'non-favorites-version'), os.path.join(DATA_DIR, 'favorites-version'))

    umount(mountpath)

    version3 = snapshot(TARGET_DIR, 666)

    mount(TARGET_DIR, mountpath, 666, version3)
    copy(os.path.join(DATA_DIR, 'changed-more-version'), 'mycopy')

    assert_file_in_pool_is_diff('mycopy',
                        os.path.join(DATA_DIR, 'favorites-version'), os.path.join(DATA_DIR, 'changed-more-version'))


    check_tmp_dir()
finally: # clean up in any case!
    umount(mountpath)
    sleep(1)
    clean_mount_dir()
#    clean_db()
#    clean_file_pool()
#    clean_tmp_dir()

#    remove_cozyfs(target_dir=TARGET_DIR, backup_id=666)

print '### EXITING SUCCESSFULLY'
