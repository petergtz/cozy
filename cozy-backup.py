#!/usr/bin/python


import sys
import os
import tempfile
import shutil

import snapshot
import cozy.configutils
from cozy.mount import mount, umount

import errno

def copyfile(src, dst):
    src_stat = os.stat(src)
    if os.path.exists(dst):
        src_stat = os.stat(src)
        dst_stat = os.stat(dst)
        if src_stat.st_size == dst_stat.st_size and \
            src_stat.st_mode == dst_stat.st_mode and \
            src_stat.st_gid == dst_stat.st_gid and \
            src_stat.st_uid == dst_stat.st_uid and \
            src_stat.st_ctime == dst_stat.st_ctime and \
            src_stat.st_mtime == dst_stat.st_mtime:
            # we're not interested in comparing atime, because that's the access time. Only accessing it, does not mean we need to back it up
    # TODO: maybe add more stats
            return
    print 'Copy file to target:', dst
    shutil.copy2(src, dst)
    os.chown(dst, src_stat.st_uid, src_stat.st_gid)
    os.utime(dst, (src_stat.st_atime, src_stat.st_mtime))

def copysymlink(src, dst):
    linkto = os.readlink(src)
    src_stat = os.lstat(src)
    if os.path.lexists(dst):
        dst_stat = os.lstat(dst)
        if os.path.islink(dst) and os.readlink(dst) == linkto and \
            dst_stat.st_gid == src_stat.st_gid and \
            dst_stat.st_uid == src_stat.st_uid:
            return
        else:
            os.remove(dst)
    print 'Copy symlink:', dst, '->', linkto
    os.symlink(linkto, dst)
    os.lchown(dst, src_stat.st_uid, src_stat.st_gid)
# new in python 2.6:    
#    os.lchmod(dst, src_stat.st_mode)
    os.utime(dst, (src_stat.st_atime, src_stat.st_mtime))

def copydir(src, dst):
    src_stat = os.stat(src)
    if os.path.exists(dst):
        dst_stat = os.stat(dst)
        if src_stat.st_mode == dst_stat.st_mode and \
            src_stat.st_gid == dst_stat.st_gid and \
            src_stat.st_uid == dst_stat.st_uid and \
            src_stat.st_ctime == dst_stat.st_ctime and \
            src_stat.st_mtime == dst_stat.st_mtime:
#            src_stat.st_ctime == dst_stat.st_ctime and \
            pass
        else:
            os.chmod(dst, src_stat.st_mode)
            os.chown(dst, src_stat.st_uid, src_stat.st_gid)
            os.utime(dst, (src_stat.st_atime, src_stat.st_mtime))
        return

    print 'Copy dir to target:', dst
    os.mkdir(dst)
    os.chmod(dst, src_stat.st_mode)
    os.chown(dst, src_stat.st_uid, src_stat.st_gid)
    os.utime(dst, (src_stat.st_atime, src_stat.st_mtime))

def sync(source, target):

    for dirpath, dirnames, filenames in os.walk(source):

        rel_path = dirpath.replace(source, '').lstrip('/')

        for target_dir_file in os.listdir(os.path.join(target, rel_path)):
            abs_target_path = os.path.join(target, rel_path, target_dir_file)
            if (os.path.isfile(abs_target_path) or (os.path.islink(abs_target_path))) and \
                target_dir_file not in filenames:

                print 'Remove file in target:', abs_target_path
                os.remove(abs_target_path)

            if os.path.isdir(abs_target_path) and \
                target_dir_file not in dirnames:

                print 'Remove dir in target:', abs_target_path
                shutil.rmtree(abs_target_path)

        for dirname in dirnames:
            src = os.path.join(dirpath, dirname)
            dst = os.path.join(target, rel_path, dirname)
            if os.path.islink(src):
                copysymlink(src, dst)
            else:
                copydir(src, dst)

        for filename in filenames:
            src = os.path.join(dirpath, filename)
            dst = os.path.join(target, rel_path, filename)
            if os.path.islink(src):
                copysymlink(src, dst)
            else:
                copyfile(src, dst)


if __name__ == '__main__':

    if len(sys.argv) > 2:
        exit("USAGE: " + __name__ + "[-f]; -f = start immediatly backing up data")


    if len(sys.argv) == 2 and sys.argv[1] == '-f':
        answer = 'y'
    else:
        answer = raw_input("Do you really want to back up your data?")

    if answer in ['y', 'Y', 'yes']:

        try:
            config = cozy.configutils.Configuration()
            target_path = config.get_full_target_path()
            backup_id = config.get_backup_id()
            source_paths = [config.get_source_path()] # in the future get_source_path will be get_source_paths
        except Exception, e:

            sys.stderr.write(str(e) + "\n")
            exit('Error: Aborting backup because getting the configuration failed')

        try:
            mountpoint = tempfile.mkdtemp(prefix='cozy')
            mount(target_path, mountpoint, backup_id)
        except Exception, e:
            sys.stderr.write(str(e) + "\n")
            exit('Error: Aborting backup because mounting failed')

        for source_path in source_paths:
            sync(source_path, mountpoint)

        umount(mountpoint)

        snapshot.snapshot(target_path, backup_id)
