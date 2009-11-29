#!/usr/bin/python

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



# TODO: check limits of FAT FS, concerning number of files per directory

import sys

import stat
import fuse
fuse.fuse_python_api = (0, 2)
import errno

import os
import shutil
import sqlite3

from cozyutils.md5sum import md5sum, md5sum_from_string

import logging

import time

# import cProfile

import optparse
import traceback

DBFILE = "fsdb"

FILE = 1
SOFT_LINK = 2
DIRECTORY = 5

DIFF_LIMIT = 0.5

MAX_TRANSACTIONS = 1

MD5SUM_FOR_EMPTY_STRING = md5sum_from_string('')

#import xdelta3
import subprocess
class xdelta3:
    @staticmethod
    def xd3_main_cmdline(cmdline):
        subprocess.check_call(cmdline)



def query2log(query):
    return query.replace('?', '%s')

def flags2string(flags):
    flagstr = ''
    if flags & os.O_RDONLY: flagstr += " O_RDONLY"
    if flags & os.O_WRONLY: flagstr += " O_WRONLY"
    if flags & os.O_RDWR: flagstr += " O_RDWR"
    if flags & os.O_CREAT: flagstr += " O_CREAT"
    if flags & os.O_EXCL: flagstr += " O_EXCL"
    if flags & os.O_NOCTTY: flagstr += " O_NOCTTY"
    if flags & os.O_TRUNC: flagstr += " O_TRUNC"
    if flags & os.O_APPEND: flagstr += " O_APPEND"
    if flags & os.O_NONBLOCK: flagstr += " O_NONBLOCK"
    if flags & os.O_NDELAY: flagstr += " O_NDELAY"
    if flags & os.O_SYNC: flagstr += " O_SYNC"
    if flags & os.O_DIRECT: flagstr += " O_DIRECT"
    if flags & os.O_LARGEFILE: flagstr += " O_LARGEFILE"
    return flagstr

class Stat(fuse.Stat):
    def __init__(self):
        self.st_ino = 0
        self.st_dev = 0
        self.st_uid = 1000
        self.st_gid = 1000
        self.st_atime = 0
        self.st_mtime = 0
        self.st_ctime = 0
        self.st_blocks = 1
        self.st_blksize = 4096
        self.st_rdev = 0
        self.st_nlink = 2 # FIXME: get number of links for DB
        self.st_size = 4096
        self.st_mode = stat.S_IFDIR | 0755


class Inode(object):
    def __init__(self, inode_number, **attributes):
        self.inode_number = inode_number
        self.attributes = attributes
        self.changed_attributes = {}

    def __getitem__(self, key):
        return self.attributes[key]

    def __setitem__(self, key, value):
        self.changed_attributes[key] = True
        self.attributes[key] = value

    def __str__(self):
        return "<Inode: inode_number: %s , attributes: %s>" % \
                (str(self.inode_number), str(self.attributes))


class InodesRepository(object):
    def __init__(self, storage, versions, backup_id):
        self.storage = storage
        self.versions = versions
        self.backup_id = backup_id
        self.attributes_names = ['size', 'atime', 'mtime', 'ctime', 'mode', 'uid', 'gid', 'type', 'data_path']
        self.cached_inodes = dict()
        self.cached_inodes[0] = Inode(inode_number=0, size=4096, atime=0, mtime=0, ctime=0, mode=0, uid=0, gid=0, type=DIRECTORY)
        self.log = logging.getLogger('cozyfs')

    def insert(self, inode):
        inode_number = self.__get_new_inode_number()
        inode.inode_number = inode_number
        for (name, value) in inode.attributes.iteritems():
            self.__insert_attribute(inode_number, name, value)
        self.cached_inodes[inode_number] = inode

    def __insert_attribute(self, inode, name, value):
        self.storage.db_execute('INSERT INTO ' + name + ' (' + name + ',inode,backup_id,version) VALUES (?,?,?,?)',
                                (value, inode, self.backup_id, self.versions[0]))

    def __get_new_inode_number(self):
        max_inode_number = self.storage.db_execute('select max(inode_number) from Nodes').fetchone()[0]
        if max_inode_number == None: max_inode_number = 0
        return max_inode_number + 1

    def inode_from_inode_number(self, inode_number):
        if not self.cached_inodes.has_key(inode_number):
            inode = self.__inode_from_inode_number_from_database(inode_number)
            self.cached_inodes[inode_number] = inode
        return self.cached_inodes[inode_number]

    def previous_data_path_version_of_inode(self, inode):
        return self.storage.db_execute("select data_path from data_path where inode = ? and version <> ? and " + self.__backup_id_versions_where_statement('data_path') + " order by version desc",
                               (inode.inode_number, self.versions[0])).fetchone()[0]

    def __inode_from_inode_number_from_database(self, inode_number):
        inode = Inode(inode_number=inode_number)
        for attribute_name in self.attributes_names:
            cursor = self.storage.db_execute("SELECT %(attr_name)s FROM %(attr_name)s WHERE inode=? AND %(where)s ORDER BY version DESC" %
                                     {'attr_name': attribute_name,
                                      'where': self.__backup_id_versions_where_statement(attribute_name)},
                                     (inode_number,))
            inode[attribute_name] = cursor.fetchone()[0]
        return inode

    def __backup_id_versions_where_statement(self, table_name):
        return " (" + table_name + ".backup_id = " + self.backup_id + " AND (" + (table_name + ".version = ") + (" or " + table_name + ".version = ").join(map(str, self.versions)) + ") ) "

    def update_inode_in_place(self, inode_number, attributes):
        for (attribute, val) in attributes.iteritems():
            if self.__attribute_exists_in_current_version(inode_number, attribute):
                query = 'update ' + attribute + ' set ' + attribute + ' = ? where inode=? and backup_id=? and version=?'
            else:
                query = 'insert into ' + attribute + ' (' + attribute + ',inode,backup_id,version) values (?,?,?,?)'

            if self.cached_inodes.has_key(inode_number):
                self.cached_inodes[inode_number][attribute] = val

            self.storage.db_execute(query, (val, inode_number, self.backup_id, self.versions[0]))

    def __attribute_exists_in_current_version(self, inode_number, attribute):
        cursor = self.storage.db_execute('select count(*) from ' + attribute + ' where inode = ? and backup_id = ? and version = ?', (inode_number, self.backup_id, self.versions[0]))
        return cursor.fetchone()[0]

    def delete_inode(self, inode_number):
        for name in self.attributes_names:
            self.__delete_attribute(inode_number, name)
        del self.cached_inodes[inode_number]

    def __delete_attribute(self, inode_number, name):
        self.storage.db_execute('DELETE FROM ' + name + ' WHERE inode = ?', (inode_number,))

    def data_path_not_used_anymore(self, data_path):
        count = self.storage.db_execute("select count(*) from data_path where data_path=?", (data_path,)).fetchone()[0]
        return count == 0


class Node(object):
    def __init__(self, path, inode_number, node_id=None, parent_node_id=None):
        self.node_id = node_id
        self.path = path
        self.parent_node_id = parent_node_id
        self.inode_number = inode_number

    def __str__(self):
        return "<node_id: %s , path: %s , parent_node_id: %s , inode_number: %s>" % \
                (str(self.node_id), self.path, str(self.parent_node_id), str(self.inode_number))


class NodesRepository(object):
    def __init__(self, storage, versions, backup_id):
        self.storage = storage
        self.versions = versions
        self.backup_id = backup_id
        self.log = logging.getLogger('cozyfs')
        self.cached_nodes = {}
        root_node = Node(path='/', inode_number=0)
        root_node.node_id = 0
        root_node.parent_node_id = None
        self.cached_nodes['/'] = root_node

    def insert(self, node):
        node.node_id = self.__get_new_node_id()
        dirname, basename = os.path.split(node.path)
        parent_node = self.node_from_path(dirname)
        query = 'INSERT INTO Nodes (backup_id,version,nodename,node_id,parent_node_id, inode_number) VALUES (?,?,?,?,?,?)'
        self.storage.db_execute(query, (self.backup_id, self.versions[0], basename, node.node_id, parent_node.node_id, node.inode_number))

        self.cached_nodes[node.path] = node

    def __get_new_node_id(self):
        ret = self.storage.db_execute('select max(node_id) from Nodes').fetchone()
        if ret[0] == None:
            return 1
        else:
            return ret[0] + 1

    def node_from_path(self, path):
        if not self.cached_nodes.has_key(path):
            node = self.__node_from_path_from_database(path)
            self.cached_nodes[path] = node
        return self.cached_nodes[path]

    def __node_from_path_from_database(self, path):
        parent_node_id = '0'
        built_path = '/'
        for nodename in path.split('/')[1:-1]:
            built_path = os.path.join(built_path, nodename)
            if self.cached_nodes.has_key(built_path):
                parent_node_id = str(self.cached_nodes[built_path].node_id)
            else:
                parent_node_id = "select node_id from Nodes where " + \
                                 self.__backup_id_versions_where_statement('Nodes') + \
                                 " group by node_id having nodename='" + nodename + \
                                 "' and parent_node_id=(" + parent_node_id + ") order by version desc"


        query = "select node_id, inode_number from Nodes where " + \
                         self.__backup_id_versions_where_statement('Nodes') + \
                         " group by node_id having nodename='" + os.path.basename(path) + \
                         "' and parent_node_id=(" + parent_node_id + ") order by version desc"
        row = self.storage.db_execute(query).fetchone()
        if row is None:
            return None
        else:
            return Node(path, row['inode_number'], row['node_id'], parent_node_id)

    def __backup_id_versions_where_statement(self, table_name):
        return " (" + table_name + ".backup_id = " + self.backup_id + " AND (" + (table_name + ".version = ") + (" or " + table_name + ".version = ").join(map(str, self.versions)) + ") ) "

    def update_node(self, node, old_path):
        basename = os.path.basename(node.path)
        if self.__has_current_node(node.node_id):
            self.storage.db_execute("update Nodes set nodename = ?, parent_node_id = ? where node_id = ? and backup_id = ? and version = ?", (basename, node.parent_node_id, node.node_id, self.backup_id, self.versions[0]))
        else:
            self.storage.db_execute("insert into Nodes (backup_id, version, node_id, nodename, parent_node_id, inode_number) values (?,?,?,?,?,?) ", (self.backup_id, self.versions[0], node.node_id, basename, node.parent_node_id, node.inode_number))

        del self.cached_nodes[old_path]
        if node.path != '':
            self.cached_nodes[node.path] = node

    def __has_current_node(self, node_id):
        row = self.storage.db_execute("select count(*) from Nodes where node_id = ? and backup_id = ? and version = ?", (node_id, self.backup_id, self.versions[0])).fetchone()
        return row[0]

    def delete_node(self, node):
        self.storage.db_execute("delete from Nodes where backup_id=? and version=? and node_id=?", (self.backup_id, self.versions[0], node.node_id))
        del self.cached_nodes[node.path]

    def inode_not_used_anymore(self, inode):
        count = self.storage.db_execute("select count(*) from Nodes where inode_number=?", (inode.inode_number,)).fetchone()[0]
        return count == 0

class DataPathDepChain(object):
    def __init__(self, storage, data_path):
        self.storage = storage
        self.log = logging.getLogger('cozyfs')
        data_path_dep_chain = [data_path]
        while True:
            row = self.storage.db_execute("SELECT based_on_data_path FROM FileDiffDependencies WHERE data_path = ?", (data_path,)).fetchone()
            if row is None or row[0] is None or row[0] == '':
                break
            else:
                data_path = row[0]
                data_path_dep_chain.append(data_path)
        self.data_path_dep_chain = data_path_dep_chain

    def data_path_is_diff(self):
        return len(self.data_path_dep_chain) != 1

    def apply_patches_and_save_as(self, target_path):
        reverse_data_path_dep_chain = self.data_path_dep_chain[:]
        reverse_data_path_dep_chain.reverse()

        real_base_path = self.storage.real_path('perm/' + reverse_data_path_dep_chain[0])

        if self.__dep_chain_includes_more_than_1_diff(reverse_data_path_dep_chain):
            merged_diff_path = self.__merge_diffs(reverse_data_path_dep_chain, target_path)
            real_merged_diff_path = self.storage.real_path(merged_diff_path)
            cmdline = ['xdelta3', '-f', '-d', '-s', real_base_path, real_merged_diff_path, self.storage.real_path(target_path)]
            xdelta3.xd3_main_cmdline(cmdline)
            self.storage.remove_file(merged_diff_path)
        elif len(reverse_data_path_dep_chain) == 2:
            real_merged_diff_path = self.storage.real_path('perm/' + reverse_data_path_dep_chain[1])
            cmdline = ['xdelta3', '-f', '-d', '-s', real_base_path, real_merged_diff_path, self.storage.real_path(target_path)]
            xdelta3.xd3_main_cmdline(cmdline)

    def __dep_chain_includes_more_than_1_diff(self, reverse_data_path_dep_chain):
        return len(reverse_data_path_dep_chain) > 2

    def __merge_diffs(self, reverse_data_path_dep_chain, target_path):
        diff_merge_cmdline = ['xdelta3', 'merge']
        for diff_path in reverse_data_path_dep_chain[1:-1]:
            real_diff_path = self.storage.real_path('perm/' + diff_path)
            diff_merge_cmdline.extend(['-m', real_diff_path])
        real_final_diff_path = self.storage.real_path('perm/' + reverse_data_path_dep_chain[-1])
        merged_diff_path = 'tmp/' + target_path + 'merged_diff' + time_string()
        diff_merge_cmdline.extend([real_final_diff_path, self.storage.real_path(merged_diff_path)])
        xdelta3.xd3_main_cmdline(diff_merge_cmdline)
        return merged_diff_path

def time_string():
    return 'TIME_STAMP_' + str(time.time())


class OpenFileInReadMode(object):
    def __init__(self, storage, data_path):
        self.storage = storage
        self.direct_io = True  # since I don't know how direct_io works, I'm enabling it.
        self.keep_cache = True # unfortunately it's nowhere documented in FUSE
        data_path_dep_chain = DataPathDepChain(storage, data_path)
        if data_path_dep_chain.data_path_is_diff():
            self.filename = 'tmp/' + data_path + '.' + time_string()
            data_path_dep_chain.apply_patches_and_save_as(self.filename)
        else:
            self.filename = 'perm/' + data_path
        self.file_handle = self.storage.open_file(self.filename, 'r')

    def read(self, length, offset):
        self.file_handle.seek(offset)
        return self.file_handle.read(length)

    def close(self):
        self.file_handle.close()
        if self.filename.startswith('tmp/'):
            self.storage.remove_file(self.filename)

    def __str__(self):
        return "<OpenFileInReadMode: filename: %s , file_handle: %s>" % \
                (self.filename, self.file_handle)

class OpenFileInReadWriteMode(object):
    def __init__(self, storage, data_path, mode, file_content_strategy):
        self.direct_io = True  # since I don't know how direct_io works, I'm enabling it.
        self.keep_cache = True # unfortunately it's nowhere documented in FUSE
        self.storage = storage
        self.data_path = data_path
        self.file_content_strategy = file_content_strategy

        self.filename = 'tmp/' + data_path + time_string()
        if mode == 'write':
            self.file_handle = self.storage.open_file(self.filename, 'w')
        elif mode == 'readwrite':
            data_path_deps_chain = DataPathDepChain(storage, data_path)
            if data_path_deps_chain.data_path_is_diff():
                data_path_deps_chain.apply_patches_and_save_as(self.filename)
            else:
                self.storage.copy_file('perm/' + data_path, self.filename)
            self.file_handle = self.storage.open_file(self.filename, 'r+')
        else:
            assert False, 'Wrong mode as Parameter'

    def read(self, length, offset):
        self.file_handle.seek(offset)
        return self.file_handle.read(length)

    def write(self, buf, offset):
        self.file_handle.seek(offset)
        return self.file_handle.write(buf)

    def flush(self):
        self.file_handle.flush()
        new_data_path = md5sum(self.storage.real_path(self.filename))
        new_size = self.storage.file_size_of(self.filename)
        if new_data_path != self.data_path:
            self.file_content_strategy.flush(new_data_path, self.filename)
        return new_data_path, new_size

    def close(self):
        self.file_handle.close()
        self.file_content_strategy.close()
        self.storage.remove_file(self.filename)

    def __str__(self):
        return "<OpenFileInReadWriteMode: original_filename: REFACTORED, filename: %s , file_handle: %s>" % \
                (self.filename, self.file_handle)

class FileDiffDependecies(object):
    def __init__(self, storage):
        self.storage = storage

    def data_path_exists_already(self, data_path):
        return self.storage.db_execute('SELECT count(*) FROM FileDiffDependencies WHERE data_path = ?', (data_path,)).fetchone()[0]

    def update(self, data_path, based_on_data_path):
        self.storage.db_execute('UPDATE FileDiffDependencies SET based_on_data_path = ? WHERE data_path = ?',
                                (based_on_data_path, data_path))

    def insert(self, data_path, based_on_data_path):
        self.storage.db_execute('INSERT INTO FileDiffDependencies (based_on_data_path, data_path) VALUES (?, ?)',
                                (based_on_data_path, data_path))


class PlainFileContentStrategy(object):
    def __init__(self, storage, filediff_deps):
        self.storage = storage
        self.filediff_deps = filediff_deps

    def flush(self, new_data_path, filename):
        if not self.filediff_deps.data_path_exists_already(new_data_path):
            self.storage.copy_file(filename, 'perm/' + new_data_path)
            self.filediff_deps.insert(new_data_path, None)

    def close(self):
        pass


class PatchedFileContentStrategy(object):
    def __init__(self, storage, filediff_deps, data_path, data_path_of_previous_version):
        self.storage = storage
        self.filediff_deps = filediff_deps
        self.data_path = data_path

        self.previous_version_dep_chain = DataPathDepChain(storage, data_path_of_previous_version)
        if self.previous_version_dep_chain.data_path_is_diff():
            self.original_filename = 'tmp/%s.orig.%s' % (data_path_of_previous_version, time_string())
            self.previous_version_dep_chain.apply_patches_and_save_as(self.original_filename)
        else:
            self.original_filename = 'perm/' + data_path_of_previous_version


    def flush(self, new_data_path, filename):
        if self.previous_version_dep_chain.data_path_dep_chain[0] != new_data_path:
            diff_filename = 'tmp/%s.diff.%s' % (new_data_path, time_string())
            self.__create_diff(self.original_filename, filename, diff_filename)
            size_of_diff = self.storage.file_size_of(diff_filename)
            if self.filediff_deps.data_path_exists_already(new_data_path):
                size_of_existing_diff = self.storage.file_size_of('perm/' + new_data_path)
                if size_of_diff < size_of_existing_diff:
                    self.storage.move_file(diff_filename, 'perm/' + new_data_path)
                    self.filediff_deps.update(new_data_path, self.data_path)
                    # FIXME:
                    # if old based_on_data_path in FileDiffDeps not needed anymore,
                    #     delete it.
                else:
                    self.storage.remove_file(diff_filename)
            else:
                size_of_nondiff = self.storage.file_size_of(filename)
                if self.__size_of_diff_is_too_big(size_of_diff, size_of_nondiff):
                    self.storage.copy_file(filename, 'perm/' + new_data_path)
                    self.storage.remove_file(diff_filename)
                    self.filediff_deps.insert(new_data_path, None)
                else:
                    self.storage.move_file(diff_filename, 'perm/' + new_data_path)
                    self.filediff_deps.insert(new_data_path, self.previous_version_dep_chain.data_path_dep_chain[0])

    def __create_diff(self, original, new, diff):
        original = self.storage.real_path(original)
        new = self.storage.real_path(new)
        diff = self.storage.real_path(diff)
        xdelta3.xd3_main_cmdline(['xdelta3', '-e', '-s', original, new, diff])

    def __size_of_diff_is_too_big(self, size_of_diff, size_of_nondiff):
        return size_of_diff > size_of_nondiff * DIFF_LIMIT

    def close(self):
        if self.original_filename.startswith('tmp/'):
            self.storage.remove_file(self.original_filename)


class ConsistenceStorage(object):
    '''
    A low level layer for database access and file access.
    The commit method allows to commit consistent changes
    between database and files.
    '''

    def __init__(self, db, devdir):
        self.db = db
        self.commit_delay_counter = 0
        self.devdir = devdir
        self.log = logging.getLogger('cozyfs')

    def db_execute(self, query, params=None):
        if params is None:
            return self.db.execute(query)
        else:
            return self.db.execute(query, params)

    def open_file(self, filename, mode):
        return open(self.real_path(filename), mode)

    def copy_file(self, source, dest):
        shutil.copy(self.real_path(source), self.real_path(dest))

    def move_file(self, source, dest):
        shutil.move(self.real_path(source), self.real_path(dest))

    def remove_file(self, filename):
        os.remove(self.real_path(filename))

    def commit(self):
        self.commit_delay_counter += 1
        if self.commit_delay_counter >= MAX_TRANSACTIONS:
            self.__real_commit()
            self.commit_delay_counter = 0

    def __real_commit(self):
        self.db.commit()

    def close(self):
        self.__real_commit()

    def real_path(self, path):
        assert path.startswith('tmp/') or path.startswith('perm/'), \
               "Programming error: filename must start with either tmp or perm"
        if path.startswith('tmp/'):
            return os.path.join(self.devdir, 'Tmp', path.replace('tmp/', ''))
        else:
            return os.path.join(self.devdir, 'FilePool', path.replace('perm/', ''))

    def file_size_of(self, path):
        return os.stat(self.real_path(path))[stat.ST_SIZE]


class CozyFS(fuse.Fuse):
    def __init__(self, storage, input_params, *args, **kw):
        fuse.Fuse.__init__(self, *args, **kw)
        self.multithreaded = False # we don't want file functions to be called in paralell
        self.log = logging.getLogger('cozyfs')
        self.storage = storage
        self.readonly = input_params.readonly
        self.backup_id = input_params.backup_id
        self.fuse_args.mountpoint = input_params.mountpoint
        self.device_dir = input_params.device_dir

        self.version = self.__init_version(input_params.version)
        self.__set_readonly_if_version_is_base()
        self.__create_lock_file_if_not_readonly()
        self.__init_base_versions(self.version)

        self.inodes = InodesRepository(self.storage, self.versions, self.backup_id)
        self.nodes = NodesRepository(self.storage, self.versions, self.backup_id)

    def __init_version(self, version):
        if version is None:
            ret = self.storage.db_execute('SELECT version FROM Versions WHERE backup_id=? ORDER BY version DESC', (self.backup_id,)).fetchone()
            if ret == None:
                exit('backup_id does not exist in filesystem')
            return ret[0]
        else:
            return version

    def __set_readonly_if_version_is_base(self):
        cursor = self.storage.db_execute("select * from Versions where based_on_version=? and backup_id=?", (int(self.version), int(self.backup_id)))
        if cursor.fetchone() is not None:
            self.readonly = True

    def __create_lock_file_if_not_readonly(self):
        if self.readonly == False:
            self.lockfile = os.path.join(self.device_dir, 'lock')
            if os.path.exists(self.lockfile):
                sys.stderr.write("Error: Filesystem is already mounted. If not, please remove " + self.lockfile + " manually and try again.\n")
                exit(4)

            os.mknod(self.lockfile)

    def __init_base_versions(self, version):
        version = int(version)
        self.versions = []
        while version != None:
            self.versions.append(version)
            cursor = self.storage.db_execute("select based_on_version from Versions where version=? and backup_id=?", (version, self.backup_id))
            version = cursor.fetchone()[0]

        self.log.debug("Backup_id: %s, Versions: %s", self.backup_id, self.versions)


    def close(self):
        if not self.readonly:
            os.remove(self.lockfile)

    def __backup_id_versions_where_statement(self, table_name):
        return " (" + table_name + ".backup_id = " + self.backup_id + " AND (" + (table_name + ".version = ") + (" or " + table_name + ".version = ").join(map(str, self.versions)) + ") ) "


    def getattr(self, path):
        self.log.debug("path = '%s'", path)
        node = self.nodes.node_from_path(path)
        if node == None:
            return - errno.ENOENT
        inode = self.inodes.inode_from_inode_number(node.inode_number)
        attributes = inode.attributes
        return self.__stat_from_attribute(attributes)

    def __stat_from_attribute(self, attributes):
        st = Stat()
        self.__store_common_attributes_into_stat(attributes, st)
        self.__store_file_type_specific_attributes_into_stat(attributes, st)
        return st

    def __store_common_attributes_into_stat(self, attributes, st):
        st.st_atime = int(attributes['atime'])
        st.st_mtime = int(attributes['mtime'])
        st.st_ctime = int(attributes['ctime'])
        st.st_uid = attributes["uid"]
        st.st_gid = attributes["gid"]

    def __store_file_type_specific_attributes_into_stat(self, attributes, st):
        if attributes['type'] == DIRECTORY:
            self.__store_dir_specific_attributes_into_stat(attributes, st)
        elif attributes["type"] == FILE:
            self.__store_file_specific_attributes_into_stat(attributes, st)
        elif attributes["type"] == SOFT_LINK:
            self.__store_symlink_specific_attributes_into_stat(attributes, st)
        else:
            raise Exception, "Error: unknown file type \"" + str(attributes["type"]) + "\" in database."

    def __store_dir_specific_attributes_into_stat(self, attributes, st):
        st.st_nlink = 2 # FIXME: get number of links from DB
        st.st_size = 4096 # FIXME: what size should this be?
        st.st_mode = stat.S_IFDIR | attributes['mode']

    def __store_file_specific_attributes_into_stat(self, attributes, st):
        st.st_nlink = 1 # FIXME: get number of links from DB
        st.st_size = int(attributes['size'])
        st.st_mode = stat.S_IFREG | attributes['mode']

    def __store_symlink_specific_attributes_into_stat(self, attributes, st):
        st.st_nlink = 1 # FIXME: get number of links from DB
# FIXME: this seems to be quite a mess with all that symlink stuff! Not sure if the current way is the correct way!
#        data_path = self.__get_data_path_from_path(path)
#        abs_data_path = os.path.normpath(os.path.join(os.path.dirname(path), data_path))
#        st.st_size = len(data_path)
        st.st_size = int(attributes['size'])
#        attr = self.getattr(abs_data_path)
        attr = 1
        if isinstance(attr, int):
            st.st_mode = stat.S_IFLNK #attributes['mode']
        else:
            st.st_mode = stat.S_IFLNK | (attr.st_mode & ~stat.S_IFDIR)#attributes['mode']



    def readdir(self, path, offset):
        self.log.debug("PARAMS: path = '%s, offset = '%s'", path, offset)
        entries = ['.', '..']
        node = self.nodes.node_from_path(path)
        cursor = self.storage.db_execute("select nodename from Nodes where " + self.__backup_id_versions_where_statement('Nodes') + " group by node_id having parent_node_id=? order by version desc", (node.node_id,))
        for c in cursor:
            if c[0] != None and c[0] != '': # FIXME: this should be either or None or '' Fix somewhere else!
                self.log.debug(c[0])
                entries.append(c[0])
        for entry in entries:
            yield fuse.Direntry(entry)

    def __assert_readwrite(self):
        if self.readonly:
            self.log.error("Can't write to FS in a restore session")
            e = IOError()
            e.errno = errno.EROFS
            raise e

    def __mknod_or_dir(self, path, mode, type, data_path=None):
        self.log.debug("PARAMS: path = '%s, mode = %s, dev = %s", path, mode, type)

        ctime = time.time()

        inode = Inode(inode_number=None, type=type, mode=mode, size=0,
                      uid=self.GetContext()['uid'], gid=self.GetContext()['gid'],
                      atime=ctime, mtime=ctime, ctime=ctime,
                      data_path=data_path)
        self.inodes.insert(inode)

        node = Node(path, inode.inode_number)
        self.nodes.insert(node)

        self.storage.commit()
        return 0


    def mknod(self, path, mode, dev): #TODO: if file already exists, only change file time. DO NOT empty file!
        self.log.debug("PARAMS: path = '%s, mode = %s, dev = %s", path, mode, dev)
        self.__assert_readwrite()
        empty_file_path = os.path.join(self.device_dir, 'FilePool', MD5SUM_FOR_EMPTY_STRING)
        if not os.path.exists(empty_file_path):
            os.mknod(empty_file_path)
        return self.__mknod_or_dir(path, mode, FILE, MD5SUM_FOR_EMPTY_STRING)

    def mkdir(self, path, mode):
        self.log.debug("PARAMS: path = '%s', mode = %s", path, mode)
        self.__assert_readwrite()
        return self.__mknod_or_dir(path, mode, DIRECTORY)

    def link(self, src_path, target_path):
        self.log.debug("PARAMS: src_path = '%s', target_path = '%s'", src_path, target_path)
        self.__assert_readwrite()

        node = self.nodes.node_from_path(src_path)
        new_node = Node(target_path, node.inode_number)
        self.nodes.insert(new_node)

        self.storage.commit()


    def symlink(self, src_path, target_path):
        self.log.debug("PARAMS: src_path = '%s', target_path = '%s'", src_path, target_path)
        self.__assert_readwrite()

        ctime = time.time()

        inode = Inode(None, type=SOFT_LINK, mode=0, size=len(src_path),
                      uid=self.GetContext()['uid'], gid=self.GetContext()['gid'],
                      atime=ctime, ctime=ctime, mtime=ctime,
                      data_path=src_path)
        self.inodes.insert(inode)
        new_node = Node(target_path, inode.inode_number)
        self.nodes.insert(new_node)

        self.storage.commit()
        return 0

    def readlink(self, path):
        self.log.debug("PARAMS: path = '%s'", path)
        node = self.nodes.node_from_path(path)
        inode = self.inodes.inode_from_inode_number(node.inode_number)
        self.log.debug("RETURNING: path = '%s'", inode['data_path'])
        return inode['data_path']

    def __has_base_nodes(self, node_id):
        cursor = self.storage.db_execute("select count(*) from Nodes where node_id = ? and version <> ? and " + self.__backup_id_versions_where_statement('Nodes'), (node_id, self.versions[0]))
        return cursor.fetchone()[0]

    def __has_base_inodes(self, inode, attribute):
        cursor = self.storage.db_execute('select count(*) from ' + attribute + ' where inode = ? and version <> ? and ' + self.__backup_id_versions_where_statement(attribute), (inode, self.versions[0]))
        return cursor.fetchone()[0]


    def rename(self, old_path, new_path):
        self.log.debug("PARAMS: old_path = '%s', new_path = '%s'", old_path, new_path)
        self.__assert_readwrite()

        node = self.nodes.node_from_path(old_path)
        new_parent_node = self.nodes.node_from_path(os.path.dirname(new_path))

        node.parent_node_id = new_parent_node.node_id
        node.path = new_path

        self.nodes.update_node(node, old_path)

        ctime = time.time()
        self.inodes.update_inode_in_place(node.inode_number, {'atime': ctime, 'mtime':ctime})

        self.storage.commit()
        return 0

    def unlink(self, path):
        self.log.debug("PARAMS: path = '%s'", path)
        self.__assert_readwrite()

        node = self.nodes.node_from_path(path)
        inode = self.inodes.inode_from_inode_number(node.inode_number)

        if self.__has_base_nodes(node.node_id):
            old_path = node.path
            node.path = ''
            node.parent_node_id = 0
            self.nodes.update_node(node, old_path)
        else:
            self.nodes.delete_node(node)
            if self.nodes.inode_not_used_anymore(inode):
                data_path = inode['data_path']
                file_system_object_type = inode["type"]
                self.inodes.delete_inode(inode.inode_number)
                if file_system_object_type == FILE:
                    if self.inodes.data_path_not_used_anymore(data_path):
                        os.remove(self.device_dir + '/FilePool/' + data_path)
                        self.storage.db_execute('DELETE FROM FileDiffDependencies WHERE data_path=?', (data_path,))
        self.storage.commit()
        return 0


    def rmdir(self, path): # TODO: check if this is funciton is allowd to delete all sub-"nodes"
        self.log.debug("PARAMS: path = '%s'", path)
        self.__assert_readwrite()

        for node in self.readdir(path, 0):
            if (node.name != '.') and (node.name != '..'): # TODO: must be a more elegant solutions
                if self.unlink(path + '/' + node.name) != 0:
                    return - 1 # TODO: return proper return value!
        return self.unlink(path)


    def open(self, path, flags):
        self.log.debug("PARAMS: path = '%s', flags = %s", path, flags2string(flags))
        node = self.nodes.node_from_path(path)
        inode = self.inodes.inode_from_inode_number(node.inode_number)
        if flags & os.O_WRONLY or flags & os.O_RDWR:
            self.__assert_readwrite()
            if flags & os.O_WRONLY:
                mode = 'write'
            elif flags & os.O_RDWR:
                mode = 'readwrite'
            else:
                assert False, 'Unknown mode'
            filediff_deps = FileDiffDependecies(self.storage)
            if self.__has_base_nodes(node.node_id):
                previous_data_path = self.inodes.previous_data_path_version_of_inode(inode)
                file_content_strategy = PatchedFileContentStrategy(self.storage, filediff_deps, inode['data_path'], previous_data_path)
            else:
                file_content_strategy = PlainFileContentStrategy(self.storage, filediff_deps)

            return OpenFileInReadWriteMode(self.storage, inode['data_path'], mode, file_content_strategy)
        else: # apparently there is nothing like a "read" flag
            return OpenFileInReadMode(self.storage, inode['data_path'])


    def read(self, path, length, offset, fH):
        buf = fH.read(length, offset)
        return buf

    def write(self, path, buf, offset, fH):
        fH.write(buf, offset)
        return len(buf)

    def flush(self, path, fh):
        self.log.debug("PARAMS: path = '%s', fH = %s", path, fh)
        try:
            if isinstance(fh, OpenFileInReadWriteMode):
                node = self.nodes.node_from_path(path)
                inode = self.inodes.inode_from_inode_number(node.inode_number)
                old_data_path = inode['data_path']
                new_data_path, new_size = fh.flush()
                if old_data_path != new_data_path:
                    self.inodes.update_inode_in_place(node.inode_number, {'data_path': new_data_path, 'size': new_size})

                    if self.inodes.data_path_not_used_anymore(old_data_path) and \
                        self.__data_path_not_used_in_filediff_deps_anymore(old_data_path):

                        self.storage.remove_file('perm/' + old_data_path)
                        self.storage.db_execute('DELETE FROM FileDiffDependencies WHERE data_path=?', (old_data_path,))
            self.storage.commit()
        except Exception, e:
            traceback.print_exc(file=sys.stderr)
            raise Exception(str(e))
        return 0

    def __data_path_not_used_in_filediff_deps_anymore(self, data_path):
        self.storage.db_execute('SELECT count(*) FROM FileDiffDependencies WHERE based_on_data_path = ?', (data_path,))

    def release(self, path, flags, fH):
        self.log.debug("PARAMS: path = '%s, flags = %s, fH = %s'", path, flags, fH)
        fH.close()

        self.storage.commit()
        return 0


    def truncate(self, path, length, fh=None):
        self.log.debug("PARAMS: path = '%s', length = %s, fH = %s", path, length, fh)
        assert fh is None, "Assumption that fh is always None is wrong"
        self.__assert_readwrite()

        # FIXME: not sure if implementing truncate through open, write, flush release sequence is good. 
        file_handle = self.open(path, os.O_RDWR)
        file_handle.file_handle.truncate(length)
        self.flush(path, file_handle)
        self.release(path, 0, file_handle)
        return 0


    def chown(self, path, uid, gid):
        self.log.debug("PARAMS: path = '%s'", path)
        ctime = time.time()
        return self.__update_attributes(path, {'gid': gid, 'uid': uid, 'atime': ctime, 'ctime':ctime})

    def chmod(self, path, mode):
        self.log.debug("PARAMS: path = '%s'", path)
        ctime = time.time()
        return self.__update_attributes(path, {'mode': mode, 'atime': ctime, 'mtime': ctime})

    def utimens(self, path, acc_nsec, mod_nsec):
        self.log.debug("PARAMS: path = '%s' acc_nsec = %s, mod_nsec = %s", path, acc_nsec.tv_sec, mod_nsec.tv_sec)
        return self.__update_attributes(path, {'atime': acc_nsec.tv_sec, 'mtime':mod_nsec.tv_sec})

    def __update_attributes(self, path, attributes):
        self.__assert_readwrite()
        node = self.nodes.node_from_path(path)
        self.inodes.update_inode_in_place(node.inode_number, attributes)
        self.storage.commit()
        return 0

    def statfs(self):
        host_fs = os.statvfs(self.device_dir)
        st = fuse.StatVfs()
        # for better explanations of the variables see: http://linux.die.net/man/2/statfs
        st.f_bsize = host_fs.f_bsize   # optimal transfer block size.
        st.f_blocks = host_fs.f_blocks # total data blocks in file system
        st.f_bfree = host_fs.f_bfree   # free blocks in fs
        st.f_bavail = host_fs.f_bavail # free blocks avail to non-superuser
        st.f_files = host_fs.f_files   # total file nodes in file system.  Of course this is not completely correct! FIXME
        st.f_ffree = host_fs.f_ffree   # free file nodes in fs. Of course this is not completely correct! FIXME
        st.f_namemax = 0               # maximum length of filenames. 0 since there basically no limit in the db
        return st


def connect_to_database(db_filename):
    try:
        db = sqlite3.connect(db_filename)
        db.row_factory = sqlite3.Row
        db.text_factory = str
        return db
    except sqlite3.OperationalError, e:
        sys.stderr.write("Error: Could not open database file due to: " + str(e))
        exit(3)


def initLogger():
    log = logging.getLogger('cozyfs')
    log.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('  Line %(lineno)-3d %(levelname)-7s Fnc: %(funcName)-10s: %(message)s'))
    log.addHandler(handler)

class InputParameters:
    pass

def parse_commandline(argv):
    option_parser = optparse.OptionParser()
    option_parser.add_option('-v', '--version', dest='version')
    option_parser.add_option('-r', '--readonly', dest='readonly', default=False, action='store_true')
    option_parser.add_option('-b', '--backup-id', dest='backup_id')
    (options, args) = option_parser.parse_args(argv)
    if len(args) < 2:
        sys.exit("PRINT USAGE")
    input_params = InputParameters()
    input_params.device_dir = args[0]
    input_params.mountpoint = args[1]
    input_params.backup_id = options.backup_id
    input_params.version = options.version
    input_params.readonly = options.readonly
#    input_params.coverage = options.coverage
    return input_params


def main(argv=sys.argv[1:]):
    input_params = parse_commandline(argv)

    initLogger()
    db = connect_to_database(os.path.join(input_params.device_dir, DBFILE))
    storage = ConsistenceStorage(db, input_params.device_dir)

    FS = CozyFS(storage, input_params, fetch_mp=False, version="CozyFS version 0.1", usage='Usage not quite sure yet')
    FS.parse(['-f'])
    FS.main()
    FS.close()
    storage.close()
    db.close()

if __name__ == '__main__':
#    cProfile.run('mount()', 'cozyfs-profile-output')
    main()
