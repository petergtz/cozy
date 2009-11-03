# Cozy Backup Solution
# Copyright (C) 2009  peter
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

from __future__ import with_statement

from cozy.configuration import Configuration
from cozy.backupprovider import BackupProvider
from cozy.locationmanager import LocationManager
from cozy.backup import Backup

import logging
import logging.config

import dbus
import time

import os

from os.path import join as join_path


def __remove_removed_source_file_or_dirs_in_target_dir(target_dirpath, isfileordir_func, source_file_or_dir_names, remove_func):
    for target_dir_file in os.listdir(target_dirpath):
        if isfileordir_func(join_path(target_dirpath, target_dir_file)) and target_dir_file not in source_file_or_dir_names:
            remove_func(join_path(target_dirpath, target_dir_file))

def __remove_removed_source_files_and_dirs_in_target_dir(target_dirpath, source_filenames, source_dirnames,
                                                         file_update_strategy):
    __remove_removed_source_file_or_dirs_in_target_dir(target_dirpath, os.path.isfile,
                                                       source_filenames, file_update_strategy.remove)
    __remove_removed_source_file_or_dirs_in_target_dir(target_dirpath, os.path.isdir,
                                                       source_dirnames, file_update_strategy.remove_dir)


def __update_files_or_dirs_in_target_dir(source_dirpath, target_dirpath,
                                         file_or_dir_names, update_func, file_update_strategy):
    for file_or_dir_name in file_or_dir_names:
        src = join_path(source_dirpath, file_or_dir_name)
        dst = join_path(target_dirpath, file_or_dir_name)
        if os.path.islink(src):
            file_update_strategy.update_symlink(src, dst)
        else:
            update_func(src, dst)

def __update_files_and_dirs_in_target_dir(source_dirpath, target_dirpath,
                                          filenames, dirnames, file_update_strategy):
    __update_files_or_dirs_in_target_dir(source_dirpath, target_dirpath, filenames,
                                         file_update_strategy.update_file, file_update_strategy)
    __update_files_or_dirs_in_target_dir(source_dirpath, target_dirpath, dirnames,
                                         file_update_strategy.update_dir, file_update_strategy)

def sync(source_path, target_path, file_update_strategy):

    for source_dirpath, dirnames, filenames in os.walk(source_path):

        rel_path = source_dirpath.replace(source_path, '').lstrip('/')
        target_dirpath = join_path(target_path, rel_path)

        __remove_removed_source_files_and_dirs_in_target_dir(target_dirpath, filenames, dirnames,
                                                             file_update_strategy)
        __update_files_and_dirs_in_target_dir(source_dirpath, target_dirpath, filenames, dirnames,
                                              file_update_strategy)


def back_up():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logging', 'config')
    logging.config.fileConfig(config_path)

    logger = logging.getLogger('cozy.backup')

    try:
        logger.info('STARTING BACKUP SESSION')
        config = Configuration()

        backup_provider = BackupProvider()

        system_bus = dbus.SystemBus()

        location_manager = LocationManager(system_bus)

        backup_location = location_manager.get_backup_location(config)

        backup = backup_provider.get_backup(backup_location.get_path(), config)
        logger.info('Version Number: %d', backup.get_latest_version())

        backup.clone_latest_version()

        with backup.mount_latest_version() as mounted_filesystem:
            time.sleep(1)
            logger.info('Backing up data from ' + config.data_path + ' to ' + mounted_filesystem.mount_point + ': ')

            file_update_strategy = backup.get_file_update_strategy(mounted_filesystem, logger)

            sync(config.data_path, mounted_filesystem.mount_point, file_update_strategy)

#        time.sleep(1)

        logger.info('ENDING BACKUP SESSION properly with new version number: %d', backup.get_latest_version())

    except Backup.MountException, e:
        logger.error(str(e))
    except Exception, e:
        logger.exception(str(e))
