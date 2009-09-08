# Cozy Backup Solution
# Copyright (C) 2009  Peter Goetz
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

from os.path import join as join_path


def __remove_removed_source_files_in_target_dir(target_dirpath, source_filenames, filesystem_functions):
    for target_dir_file in filesystem_functions.listdir(target_dirpath):
        if filesystem_functions.isfile(join_path(target_dirpath, target_dir_file)) and target_dir_file not in source_filenames:
            filesystem_functions.remove(join_path(target_dirpath, target_dir_file))

def __remove_removed_source_dirs_in_target_dir(target_dirpath, source_dirnames, filesystem_functions):
    for target_dir_file in filesystem_functions.listdir(target_dirpath):
        if filesystem_functions.isdir(join_path(target_dirpath, target_dir_file)) and target_dir_file not in source_dirnames:
            filesystem_functions.remove_dir(join_path(target_dirpath, target_dir_file))

def __update_dirs_in_target_dir(source_dirpath, target_dirpath, dirnames, fsf):
    for dirname in dirnames:
        src = join_path(source_dirpath, dirname)
        dst = join_path(target_dirpath, dirname)
        if fsf.islink(src):
            fsf.update_symlink(src, dst)
        else:
            fsf.update_dir(src, dst)

def __update_files_in_target_dir(source_dirpath, target_dirpath, filenames, fsf):
    for filename in filenames:
        src = join_path(source_dirpath, filename)
        dst = join_path(target_dirpath, filename)
        if fsf.islink(src):
            fsf.update_symlink(src, dst)
        else:
            fsf.update_file(src, dst)


def sync(source, target, filesystem_functions):
    fsf = filesystem_functions

    for source_dirpath, dirnames, filenames in filesystem_functions.walk(source):

        rel_path = source_dirpath.replace(source, '').lstrip('/')
        target_dirpath = join_path(target, rel_path)

        __remove_removed_source_files_in_target_dir(target_dirpath, filenames, fsf)
        __remove_removed_source_dirs_in_target_dir(target_dirpath, dirnames, fsf)

        __update_dirs_in_target_dir(source_dirpath, target_dirpath, dirnames, fsf)
        __update_files_in_target_dir(source_dirpath, target_dirpath, filenames, fsf)
