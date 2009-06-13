#!/usr/bin/python


import sys
import os
import tempfile
import shutil

import snapshot
import cozy.configutils
from cozy.mount import mount, umount


def sync(source, target):

# TODO: only copy files that changed to avoid unnecessary copying.    
    for dirpath, dirnames, filenames in os.walk(source):

#TODO: treat symbbolic links correctly

        rel_path = dirpath.replace(source, '').lstrip('/')

        for target_dir_file in os.listdir(os.path.join(target, rel_path)):
            abs_target_path = os.path.join(target, rel_path, target_dir_file)
            if os.path.isfile(abs_target_path) and \
                target_dir_file not in filenames:

                print 'Remove file in target:', abs_target_path
                os.remove(abs_target_path)

            if os.path.isdir(abs_target_path) and \
                target_dir_file not in dirnames:

                print 'Remove dir in target:', abs_target_path
                shutil.rmtree(abs_target_path)

# TODO: check which copy function must be used to also copy attributes. Also check mkdir
        for dirname in dirnames:
            try:
                print 'Copy dir to target:', os.path.join(target, rel_path, dirname)
                os.mkdir(os.path.join(target, rel_path, dirname))
            except OSError:
                pass
        for filename in filenames:
            if os.path.islink(os.path.join(dirpath, filename)):
                print 'Skipping link'
                continue
            print 'Copy file to target:', os.path.join(target, rel_path, filename)
            shutil.copy(os.path.join(dirpath, filename), os.path.join(target, rel_path, filename))


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

