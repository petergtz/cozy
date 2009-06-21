#!/usr/bin/python

import sys
import os
import shutil
from time import sleep
import subprocess
import sqlite3
import stat

ROOT_DIR = '/home/peter/Projects/Cozy/'


COZYFS_PATH = ROOT_DIR + 'cozyfs.py'
MKFS_PATH = ROOT_DIR + 'cozy-mkfs.py'
SNAPSHOT_PATH = ROOT_DIR + 'snapshot.py'
DBFILE = "fsdb"
TARGET_DIR = '/home/peter/MyBackup'



def make_cozyfs(target_dir, backup_id):
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


def mount(mountpath, target_dir, backup_id, version=None):
    os.mkdir(mountpath)
    cmdline = [COZYFS_PATH, mountpath, '-f', '-o']
    cmdline.append('target_dir=' + target_dir + ',backup_id=' + str(backup_id))
    if version is not None:
        cmdline[-1] = cmdline[-1] + ',version=' + version
    print '### MOUNTING: ' + ' '.join(cmdline)
    process = subprocess.Popen(cmdline)
    sleep(2)
    if process.poll() != None:
        sys.exit('### FAILED mount')
    os.chdir(mountpath)

def snapshot(target_dir, backup_id, based_on_version=None):
    cmdline = [SNAPSHOT_PATH, target_dir, str(backup_id)]
    if based_on_version is not None:
        cmdline.append(str(based_on_version))
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
        if open(target).read() != open(source).read():
            raise Exception('compare failed: ' + source + ' ' + target)

    except Exception, e:
        sys.exit('### FAILED copy ' + source + ' ' + target + ': ' + str(e))
    else:
        print '### PASSED copy', source, target

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
        sys.exit('### WARNING tmp dir is not empty')


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


def clean_file_pool():
    os.system('rm -rf ' + TARGET_DIR + '/FilePool/*')


def clean_tmp_dir():
    os.system('rm -rf ' + TARGET_DIR + '/Tmp/*')


def umount(mountpath):
    print '### UNMOUNTING'
    os.system('fusermount -z -u ' + mountpath)
    os.chdir('/')
    shutil.rmtree(mountpath)

def remove_cozyfs(target_dir, backup_id):
    os.rmdir(os.path.join(TARGET_DIR, 'FilePool'))
    os.rmdir(os.path.join(TARGET_DIR, 'Tmp'))
    os.remove(os.path.join(TARGET_DIR, DBFILE))


mountpath = '/tmp/cozy-TestCase'

try:
    version1 = make_cozyfs(target_dir=TARGET_DIR, backup_id=666)

    mount(mountpath, target_dir=TARGET_DIR, backup_id=666)
    mkdir('folder1')
    neg_mkdir('folder1')
    umount(mountpath)

    mount(mountpath, target_dir=TARGET_DIR, backup_id=666, version=version1)
    neg_mkdir('folder1')
    move('folder1', 'folder1_renamed')
    copy(ROOT_DIR + 'Testcases/file1', 'file1')
    move('file1', 'folder1_renamed/file1')
    umount(mountpath)

    version2 = snapshot(TARGET_DIR, 666, based_on_version=version1)

    mount(mountpath, target_dir=TARGET_DIR, backup_id=666, version=version2)
    mkdirs('folder2/folder3')
    copy(ROOT_DIR + 'Testcases/file1', 'file2')
    copy(ROOT_DIR + 'Testcases/file2', './folder1_renamed/file1')
    copy(ROOT_DIR + 'Testcases/file1', 'overwriter')
    umount(mountpath)

    version3 = snapshot(TARGET_DIR, '666', version2)

    mount(mountpath, target_dir=TARGET_DIR, backup_id=666, version=version3)
    copy(ROOT_DIR + 'Testcases/file1', 'overwriter')
#    raw_input()
    mkdir('folder4')
    mkdir('folder5')
    rmtree('folder5')
    rm('folder1_renamed/file1')
    copy(ROOT_DIR + 'Testcases/image1.jpg', 'image.jpg')
    hardlink('image.jpg', 'folder4/hardlink_to_image.jpg')
    rm('image.jpg')
    compare_file_content(ROOT_DIR + 'Testcases/image1.jpg', 'folder4/hardlink_to_image.jpg')
    softlink('folder4/hardlink_to_image.jpg', 'softlink_to_image.jpg')
    umount(mountpath)

    mount(mountpath, target_dir=TARGET_DIR, backup_id=666, version=version2)

    neg_exists('folder4')
    neg_mkdir('folder4')
    # negativ mount tests to be done

    check_tmp_dir()
except Exception, e:
    raise
finally: # clean up in any case!
    umount(mountpath)
    sleep(1)
    clean_db()
    clean_file_pool()
#    clean_tmp_dir()

    remove_cozyfs(target_dir=TARGET_DIR, backup_id=666)

print '### EXITING SUCCESSFULLY'
