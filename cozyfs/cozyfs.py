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
from os.path import join as path_join, split as path_split, basename as path_basename, dirname as path_dirname
import shutil
import sqlite3

from cozyutils.md5sum import md5sum, md5sum_from_string

import logging

import time

# import cProfile

import optparse
import traceback

from uuid import uuid4

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
        self.attributes_names = ['size', 'atime', 'mtime', 'ctime', 'mode', 'uid', 'gid', 'type', 'data']
        self.cached_inodes = dict()
        self.cached_inodes[0] = Inode(inode_number=0, size=4096, atime=0, mtime=0, ctime=0, mode=0, uid=0, gid=0, type=DIRECTORY)
        self.log = logging.getLogger('cozyfs')

    def insert(self, inode):
        inode_number = self.__get_new_inode_number()
        inode.inode_number = inode_number
        for (name, value) in inode.attributes.iteritems():
            self.insert_attribute(inode_number, name, value)
        self.cached_inodes[inode_number] = inode

    def insert_attribute(self, inode_number, name, value):
        self.storage.db_execute('INSERT INTO ' + name + ' (' + name + ',inode,backup_id,version) VALUES (?,?,?,?)',
                                (value, inode_number, self.backup_id, self.versions[0]))

    def __get_new_inode_number(self):
        max_inode_number = self.storage.db_execute('select max(inode_number) from Nodes').fetchone()[0]
        if max_inode_number == None: max_inode_number = 0
        return max_inode_number + 1

    def inode_from_inode_number(self, inode_number):
        if not self.cached_inodes.has_key(inode_number):
            inode = self.__inode_from_inode_number_from_database(inode_number)
            self.cached_inodes[inode_number] = inode
        return self.cached_inodes[inode_number]

    def attribute_has_previous_versions(self, inode_number, attribute):
        cursor = self.storage.db_execute("SELECT count(*) FROM " + attribute + " WHERE inode = ? AND version <> ? and "
                                         + self.__backup_id_versions_where_statement(attribute), (inode_number, self.versions[0]))
        return cursor.fetchone()[0]

    def __inode_from_inode_number_from_database(self, inode_number):
        attributes = {}
        for attribute_name in self.attributes_names:
            cursor = self.storage.db_execute("SELECT %(attr_name)s FROM %(attr_name)s WHERE inode=? AND %(where)s ORDER BY version DESC" %
                                     {'attr_name': attribute_name,
                                      'where': self.__backup_id_versions_where_statement(attribute_name)},
                                     (inode_number,))
            attributes[attribute_name] = cursor.fetchone()[0]
        return Inode(inode_number, **attributes)

    def inode_of_previous_version_from_inode_number(self, inode_number):
        attributes = {}
        for attribute_name in self.attributes_names:
            cursor = self.storage.db_execute("SELECT %(attr_name)s FROM %(attr_name)s WHERE inode=? AND %(where)s AND version <> ? ORDER BY version DESC" %
                                     {'attr_name': attribute_name,
                                      'where': self.__backup_id_versions_where_statement(attribute_name)},
                                     (inode_number, self.versions[0]))
            attributes[attribute_name] = cursor.fetchone()[0]
        return Inode(inode_number, **attributes)


    def __backup_id_versions_where_statement(self, table_name):
        return " (" + table_name + ".backup_id = " + self.backup_id + " AND (" + (table_name + ".version = ") + (" or " + table_name + ".version = ").join(map(str, self.versions)) + ") ) "

    def update_inode_in_place(self, inode_number, attributes):
        for (attribute, val) in attributes.iteritems():
            if self.attribute_exists_in_current_version(inode_number, attribute):
                query = 'UPDATE ' + attribute + ' SET ' + attribute + ' = ? WHERE inode=? AND backup_id=? AND version=?'
            else:
                query = 'INSERT INTO ' + attribute + ' (' + attribute + ',inode,backup_id,version) VALUES (?,?,?,?)'

            if self.cached_inodes.has_key(inode_number):
                self.cached_inodes[inode_number][attribute] = val

            self.storage.db_execute(query, (val, inode_number, self.backup_id, self.versions[0]))

    def attribute_exists_in_current_version(self, inode_number, attribute):
        cursor = self.storage.db_execute('select count(*) from ' + attribute + ' where inode = ? and backup_id = ? and version = ?', (inode_number, self.backup_id, self.versions[0]))
        return cursor.fetchone()[0]

    def delete_inode(self, inode_number):
        for name in self.attributes_names:
            self.__delete_attribute(inode_number, name)
        del self.cached_inodes[inode_number]

    def __delete_attribute(self, inode_number, name):
        self.storage.db_execute('DELETE FROM ' + name + ' WHERE inode = ?', (inode_number,))

#    def data_id_not_used_anymore(self, data_id):
#        count = self.storage.db_execute("select count(*) from hash where data_id=?", (data_id,)).fetchone()[0]
#        return count == 0


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
        dirname, basename = path_split(node.path)
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
            built_path = path_join(built_path, nodename)
            if self.cached_nodes.has_key(built_path):
                parent_node_id = str(self.cached_nodes[built_path].node_id)
            else:
                parent_node_id = "select node_id from Nodes where " + \
                                 self.__backup_id_versions_where_statement('Nodes') + \
                                 " group by node_id having nodename='" + nodename + \
                                 "' and parent_node_id=(" + parent_node_id + ") order by version desc"


        query = "select node_id, inode_number from Nodes where " + \
                         self.__backup_id_versions_where_statement('Nodes') + \
                         " group by node_id having nodename='" + path_basename(path) + \
                         "' and parent_node_id=(" + parent_node_id + ") order by version desc"
        row = self.storage.db_execute(query).fetchone()
        if row is None:
            return None
        else:
            return Node(path, row['inode_number'], row['node_id'], parent_node_id)

    def __backup_id_versions_where_statement(self, table_name):
        return " (" + table_name + ".backup_id = " + self.backup_id + " AND (" + (table_name + ".version = ") + (" or " + table_name + ".version = ").join(map(str, self.versions)) + ") ) "

    def update_node(self, node, old_path):
        basename = path_basename(node.path)
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

    def node_has_base_nodes(self, node_id):
        cursor = self.storage.db_execute("select count(*) from Nodes where node_id = ? and version <> ? and " + self.__backup_id_versions_where_statement('Nodes'), (node_id, self.versions[0]))
        return cursor.fetchone()[0]

    def delete_node(self, node):
        self.storage.db_execute("delete from Nodes where backup_id=? and version=? and node_id=?", (self.backup_id, self.versions[0], node.node_id))
        del self.cached_nodes[node.path]

    def inode_not_used_anymore(self, inode):
        count = self.storage.db_execute("select count(*) from Nodes where inode_number=?", (inode.inode_number,)).fetchone()[0]
        return count == 0

    def some_node_id_from_inode_number_not_equal_node_id(self, inode_number, node_id):
        row = self.storage.db_execute("SELECT node_id FROM Nodes WHERE inode_number=? and node_id <> ?", (inode_number, node_id)).fetchone()
        if row is None:
            return None
        else:
            return row[0]

    def data_path_from_node_id(self, node_id):
        data_path = ''
        while(True):
            row = self.storage.db_execute("SELECT nodename, parent_node_id FROM Nodes WHERE node_id=?", (node_id,)).fetchone()
            if row is None:
                return None
            data_path = path_join(row[0], data_path)
            if row[1] == 0:
                break
            node_id = row[1]
        return data_path.rstrip('/')




class BasicOpenFile(object):
    def __init__(self, storage):
        self.storage = storage
        self.direct_io = True  # since I don't know how direct_io works, I'm enabling it.
        self.keep_cache = True # unfortunately it's nowhere documented in FUSE

class TemporaryPath(object):
    def __init__(self, path, storage):
        assert not path.startswith('/')
        self.path = path
        self.storage = storage

    def __str__(self):
        return 'tmp/' + self.path

    def release(self):
        self.storage.remove_file(self.__str__())

class PermanentPath(object):
    def __init__(self, path):
        assert not path.startswith('/')
        self.path = path

    def __str__(self):
        return 'perm/' + self.path

    def release(self):
        pass

class PlainPath(object):
    def __init__(self, path):
        assert not path.startswith('/')
        self.path = path

    def __str__(self):
        return 'perm/plain/' + self.path

    def release(self):
        pass


class OpenFileInReadMode(BasicOpenFile):
    def __init__(self, storage, working_data_path):
        BasicOpenFile.__init__(self, storage)
        self.working_data_path = working_data_path
        self.file_handle = self.storage.open_file(self.working_data_path, 'r')

    def read(self, length, offset):
        self.file_handle.seek(offset)
        return self.file_handle.read(length)

    def close(self):
        self.file_handle.close()
        self.working_data_path.release()

    def __str__(self):
        return "<OpenFileInReadMode: data_path: %s , file_handle: %s>" % \
                (self.working_data_path, self.file_handle)

class OpenFileInWriteMode(BasicOpenFile):
    def __init__(self, storage, chunks, plain_path, tmp_path, previous_version_inode):
        BasicOpenFile.__init__(self, storage)
        self.chunks = chunks
        self.previous_version_inode = previous_version_inode
        self.plain_path = plain_path
        self.tmp_path = tmp_path
        self.file_handle = self.storage.open_file(self.plain_path, 'w')

    def write(self, buf, offset):
        self.file_handle.seek(offset)
        return self.file_handle.write(buf)

    def flush(self):
        self.file_handle.flush()
        new_hash = md5sum(self.storage.real_path(self.plain_path))
        new_size = self.storage.file_size_of(self.plain_path)
        self.chunks.update_hash_and_size_by_plain_path(self.plain_path, new_hash, new_size)
        if self.tmp_path is not None:
            self.__create_diff_and_copy_to_permanent(new_hash)
        return new_size, new_hash

    def __create_diff_and_copy_to_permanent(self, new_based_on_hash):
        diff_data_path = 'tmp/diff.%s' % uuid4()
        self.__create_diff(self.plain_path, self.tmp_path, diff_data_path)
        diff_size = self.storage.file_size_of(diff_data_path)
        if self.__size_of_diff_is_small_enough(diff_size, self.previous_version_inode['size']):
            self.storage.move_file(diff_data_path, PermanentPath(self.previous_version_inode['data']))
            self.chunks.update_based_on_hash(self.previous_version_inode['data'], new_based_on_hash)
        else:
            self.storage.remove_file(diff_data_path)


    def __create_diff(self, original, new, diff):
        original = self.storage.real_path(original)
        new = self.storage.real_path(new)
        diff = self.storage.real_path(diff)
        xdelta3.xd3_main_cmdline(['xdelta3', '-D', '-e', '-s', original, new, diff])

    def __size_of_diff_is_small_enough(self, size_of_diff, size_of_nondiff):
        return size_of_diff < size_of_nondiff * DIFF_LIMIT


    def close(self):
        self.file_handle.close()
        self.plain_path.release()
        if self.tmp_path is not None:
            self.tmp_path.release()

    def __str__(self):
        return "<OpenFileInWriteMode: plain_path: %s, tmp_path: %s,file_handle: %s>" % \
                (self.plain_path, self.tmp_path, self.file_handle)


#class OpenFileInReadWriteMode(OpenFileInReadMode, OpenFileInWriteMode):
#    def __init__(self, storage, data_id, flushing_strategy, chunks):
#        BasicOpenFile.__init__(self, storage)
#        self.chunks = chunks
#        self.data_id = data_id
#        file_diff_entry = chunks.entry_from_data_id(data_id)
#        self.flushing_strategy = flushing_strategy
#        self.working_data_path = PlainPath(file_diff_entry.data_path)
#        self.file_handle = self.storage.open_file(self.working_data_path, 'r+')
#
#    def __str__(self):
#        return "<OpenFileInReadWriteMode: working_data_path: %s , file_handle: %s>" % \
#                (self.working_data_path, self.file_handle)
#
#    def close(self):
#        OpenFileInWriteMode.close(self)

class Patcher(object):
    def __init__(self, storage):
        self.storage = storage
        self.log = logging.getLogger('cozyfs')

    def __data_path(self, chunk):
        if chunk.plain_path:
            return 'perm/plain/' + chunk.plain_path
        else:
            return 'perm/' + chunk.hash

    def apply_patches_and_save_as(self, chunk_chain, target_path):
        self.log.debug('chunk_chain: ' + ' '.join(map(str, chunk_chain)) + ' target_path: ' + str(target_path))
        real_base_path = self.storage.real_path(self.__data_path(chunk_chain[0]))

        if len(chunk_chain) > 2:
            merged_diff_path = self.__merge_diffs(chunk_chain, target_path)
            real_merged_diff_path = self.storage.real_path(merged_diff_path)
            cmdline = ['xdelta3', '-f', '-d', '-s', real_base_path, real_merged_diff_path, self.storage.real_path(target_path)]
            xdelta3.xd3_main_cmdline(cmdline)
            self.log.debug(' '.join(cmdline))
            self.storage.remove_file(merged_diff_path)
        elif len(chunk_chain) == 2:
            real_merged_diff_path = self.storage.real_path(self.__data_path(chunk_chain[1]))
            cmdline = ['xdelta3', '-f', '-d', '-s', real_base_path, real_merged_diff_path, self.storage.real_path(target_path)]
            self.log.debug(' '.join(cmdline))
            xdelta3.xd3_main_cmdline(cmdline)
        else:
            self.storage.copy_file(self.__data_path(chunk_chain[0]), target_path)

    def __merge_diffs(self, reverse_data_path_dep_chain, target_path):
        diff_merge_cmdline = ['xdelta3', 'merge']
        for diff_path in reverse_data_path_dep_chain[1:-1]:
            real_diff_path = self.storage.real_path(self.__data_path(diff_path))
            diff_merge_cmdline.extend(['-m', real_diff_path])
        real_final_diff_path = self.storage.real_path(self.__data_path(reverse_data_path_dep_chain[-1]))
        merged_diff_path = str(target_path) + 'merged_diff' + str(uuid4())
        diff_merge_cmdline.extend([real_final_diff_path, self.storage.real_path(merged_diff_path)])
        xdelta3.xd3_main_cmdline(diff_merge_cmdline)
        return merged_diff_path

def dependency_chain(chunks, hash):
    chunk = chunks.chunk_from_hash(hash)
    result = [chunk]
    while True:
        based_on_hash = chunk.based_on_hash
        if based_on_hash:
            chunk = chunks.chunk_from_hash(based_on_hash)
        else:
            break
        result.append(chunk)

    result.reverse()
    return result

#FIXME: __depency_chain is very expensive and should not be called twice.
def is_based_on_other_hash(chunks, hash): # FIXME: rename contains_at_least_one_diff
    return len(dependency_chain(chunks, hash)) > 1

class Chunk(object):
    def __init__(self, hash, based_on_hash, plain_path, size):
        self.hash = hash
        self.based_on_hash = based_on_hash
        self.plain_path = plain_path
        self.size = size

    def __str__(self):
        return 'Chunk(hash: %s, based_on_hash: %s, plain_path: %s, size: %s)' % (
                self.hash, self.based_on_hash, self.plain_path, self.size)

class ChunkRepository(object):
    def __init__(self, storage):
        self.storage = storage

    def chunk_from_hash(self, hash):
# Note: sometimes we have the case that a chunk has a hash and is beased on the
#       very same hash. Essentially that means that the chunk denotes a null
#       diff. null diffs are removed with the next snapshot.
#       However, before they're removed we simply want to ignore them completely
#       Therefore the addtional condition:
        row = self.storage.db_execute('SELECT * FROM Chunks WHERE hash = ? AND (based_on_hash ISNULL OR  based_on_hash <> ?)', (hash, hash)).fetchone()
        chunk = Chunk(row['hash'], row['based_on_hash'], row['plain_path'], row['size'])
        assert row['plain_path'] != ''
        return chunk

    def update_hash(self, old_hash, new_hash):
        self.storage.db_execute('UPDATE Chunks SET hash = ? WHERE hash = ?', (new_hash, old_hash))

    def update_size(self, hash, size):
        self.storage.db_execute('UPDATE Chunks SET size = ? WHERE hash = ?', (size, hash))

    def update_plain_path(self, hash, data_path):
        self.storage.db_execute('UPDATE Chunks SET plain_path = ? WHERE hash = ?', (data_path, hash))

    def update_based_on_hash(self, hash, based_on_hash):
# Note: the following additional condition falls into the same category as the
#       noted above. When we flush and the file is exactly the same as the
#       previous version, we get a null diff and identical hashes. However,
#       we only want to update diff hash and not the one with the plain_path.
        self.storage.db_execute('UPDATE Chunks SET based_on_hash = ? WHERE hash = ? AND plain_path ISNULL', (based_on_hash, hash))

    def update_hash_and_size_by_plain_path(self, plain_path, hash, size):
        self.storage.db_execute('UPDATE Chunks SET hash = ?, size = ? WHERE plain_path = ?', (hash, size, str(plain_path).replace('perm/plain/', '')))

    def clear_plain_path(self, plain_path):
        self.storage.db_execute('UPDATE Chunks SET plain_path = null WHERE plain_path = ?', (plain_path,))

    def remove_chunk_by_plain_path(self, plain_path):
        self.storage.db_execute('DELETE FROM Chunks WHERE plain_path = ?', (plain_path,))

#    def remove_and_handle_plain_path(self, hash):
#        chunk = self.chunk_from_hash(hash)
##        hash = self.storage.db_execute("SELECT hash FROM Chunks WHERE data_id = ?", (data_id,)).fetchone()[0]
#        count = self.storage.db_execute("SELECT count(*) FROM Chunks WHERE chunks_path = ?", (chunk.plain_path,)).fetchone()[0]
#        if count > 0:
#            # NOTE: we could *move* the file so we don't have to copy it (*remove*
#            # it in the else block. That would be faster.
#            # But we'd like to keep the operations on the plain filesystem in
#            # a delegating way in CozyFS. This is less error prone. And avoiding corruption
#            # in the plain filesystem is the highest goal.
#            self.storage.copy_file(PlainPath(chunk.plain_path), PermanentPath(chunk.hash))
#            self.storage.db_execute("UPDATE Chunks SET plain_path = NULL WHERE plain_path = ?", (chunk.plain_path,))
#        else:
#            self.storage.db_execute("DELETE FROM Chunks WHERE hash = ?", (hash,))

    def insert(self, chunk):
        self.storage.db_execute('INSERT INTO Chunks (hash, based_on_hash, plain_path, size) VALUES (?, ?, ?, ?)',
                                (chunk.hash, chunk.based_on_hash, chunk.plain_path, chunk.size))

    def no_hash_dependent_anymore_on(self, hash):
        return self.storage.db_execute('SELECT count(*) FROM Chunks WHERE based_on_hash = ?', (hash,)).fetchone()[0]

    def remove_chunk(self, hash):
        self.storage.db_execute('DELETE FROM Chunks WHERE hash = ? AND plain_path ISNULL', (hash,))

    def base_of(self, hash):
        row = self.storage.db_execute("SELECT based_on_hash FROM Chunks WHERE hash = ?", (hash,)).fetchone()
        if row is None or row[0] is None or row[0] == '':
            return None
        else:
            return row[0]

    def update_chunks_refering_to(self, plain_path):
        pass


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
        self.log.debug(query + ' % ' + str(params))
        if params is None:
            return self.db.execute(query)
        else:
            return self.db.execute(query, params)

    def open_file(self, filename, mode):
        return open(self.real_path(filename), mode)

    def copy_file(self, source, dest):
        self.log.debug(self.real_path(source) + ' -> ' + self.real_path(dest))
        shutil.copy(self.real_path(source), self.real_path(dest))

    def move_file(self, source, dest):
        self.log.debug(self.real_path(source) + ' -> ' + self.real_path(dest))
        shutil.move(self.real_path(source), self.real_path(dest))

    def remove_file(self, filename):
        self.log.debug(self.real_path(filename))
        os.remove(self.real_path(filename))

    def chmod_file(self, path, mode):
        os.chmod(self.real_path(path), mode)

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
        path_str = str(path)
        assert path_str.startswith('tmp/') or path_str.startswith('perm/'), \
               "Programming error: filename must start with either tmp or perm"
        if path_str.startswith('tmp/'):
            return path_join(self.devdir, 'Tmp', path_str.replace('tmp/', ''))
        else:
            if path_str.startswith('perm/plain'):
                return path_join(self.devdir, 'plain/' + path_str.replace('perm/plain/', ''))
            else:
                return path_join(self.devdir, 'FilePool', path_str.replace('perm/', ''))

    def file_size_of(self, path):
        return os.path.getsize(self.real_path(path))


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
        self.chunks = ChunkRepository(self.storage)

    def __init_version(self, version):
        if version is None:
            ret = self.storage.db_execute('SELECT version FROM Versions WHERE backup_id=? ORDER BY version DESC', (self.backup_id,)).fetchone()
            if ret == None:
                exit('backup_id does not exist in filesystem')
            return ret[0]
        else:
            return version

    def __set_readonly_if_version_is_base(self):
        cursor = self.storage.db_execute("select * from Versions where based_on_version = ? and backup_id = ?", (int(self.version), int(self.backup_id)))
        if cursor.fetchone() is not None:
            self.readonly = True

    def __create_lock_file_if_not_readonly(self):
        if self.readonly == False:
            self.lockfile = path_join(self.device_dir, 'lock')
            if os.path.exists(self.lockfile):
                sys.stderr.write("Error: Filesystem is already mounted. If not, please remove " + self.lockfile + " manually and try again.\n")
                exit(4)

            os.mknod(self.lockfile)

    def __init_base_versions(self, version):
        version = int(version)
        self.versions = []
        while version != None:
            self.versions.append(version)
            cursor = self.storage.db_execute("select based_on_version from Versions where version = ? and backup_id = ?", (version, self.backup_id))
            version = cursor.fetchone()[0]

        self.log.debug("Backup_id: % s, Versions: % s", self.backup_id, self.versions)


    def close(self):
        if not self.readonly:
            os.remove(self.lockfile)

    def __backup_id_versions_where_statement(self, table_name):
        return " (" + table_name + ".backup_id=" + self.backup_id + " AND (" + (table_name + ".version=") + (" or " + table_name + ".version=").join(map(str, self.versions)) + ")) "


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
        st.st_nlink = 10 # FIXME: get number of links from DB
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
#        abs_data_path = os.path.normpath(path_join(path_dirname(path), data_path))
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

    def __mknod_or_dir(self, path, mode, type, hash=None):
        self.log.debug("PARAMS: path = '%s, mode = %s, dev = %s", path, mode, type)

        ctime = time.time()

        inode = Inode(inode_number=None, type=type, mode=mode, size=0,
                      uid=self.GetContext()['uid'], gid=self.GetContext()['gid'],
                      atime=ctime, mtime=ctime, ctime=ctime,
                      data=hash)
        self.inodes.insert(inode)

        node = Node(path, inode.inode_number)
        self.nodes.insert(node)

        self.storage.commit()
        return 0

    def __plain_path(self, path):
        return path_join(self.device_dir, 'plain' + path)

    def mknod(self, path, mode, dev): #TODO: if file already exists, only change file time. DO NOT empty file!
        self.log.debug("PARAMS: path = '%s, mode = %s, dev = %s", path, mode, dev)
        self.__assert_readwrite()

        os.mknod(self.__plain_path(path), mode, dev)

#        empty_file_path = path_join(self.device_dir, 'FilePool', MD5SUM_FOR_EMPTY_STRING)
#        if not os.path.exists(empty_file_path):
#            os.mknod(empty_file_path)
        self.chunks.insert(Chunk(MD5SUM_FOR_EMPTY_STRING, None, path.lstrip('/'), 0))
        return self.__mknod_or_dir(path, mode, FILE, MD5SUM_FOR_EMPTY_STRING)

    def mkdir(self, path, mode):
        self.log.debug("PARAMS: path = '%s', mode = %s", path, mode)
        self.__assert_readwrite()
        os.mkdir(self.__plain_path(path), mode)
        return self.__mknod_or_dir(path, mode, DIRECTORY)

    def link(self, src_path, target_path):
        self.log.debug("PARAMS: src_path = '%s', target_path = '%s'", src_path, target_path)
        self.__assert_readwrite()

        os.link(self.__plain_path(src_path), self.__plain_path(target_path))

        node = self.nodes.node_from_path(src_path)
        new_node = Node(target_path, node.inode_number)
        self.nodes.insert(new_node)

        self.storage.commit()


    def symlink(self, src_path, target_path):
        self.log.debug("PARAMS: src_path = '%s', target_path = '%s'", src_path, target_path)
        self.__assert_readwrite()

        os.symlink(src_path, self.__plain_path(target_path))

        ctime = time.time()

        inode = Inode(None, type=SOFT_LINK, mode=0, size=len(src_path),
                      uid=self.GetContext()['uid'], gid=self.GetContext()['gid'],
                      atime=ctime, ctime=ctime, mtime=ctime,
                      data=src_path)
        self.inodes.insert(inode)
        new_node = Node(target_path, inode.inode_number)
        self.nodes.insert(new_node)

        self.storage.commit()
        return 0

    def readlink(self, path):
        self.log.debug("PARAMS: path = '%s'", path)
        node = self.nodes.node_from_path(path)
        inode = self.inodes.inode_from_inode_number(node.inode_number)
        self.log.debug("RETURNING: path = '%s'", inode['data'])
        return inode['data']


    def rename(self, old_path, new_path):
        self.log.debug("PARAMS: old_path = '%s', new_path = '%s'", old_path, new_path)
        self.__assert_readwrite()


        node = self.nodes.node_from_path(old_path)
        new_parent_node = self.nodes.node_from_path(path_dirname(new_path))

        os.rename(self.__plain_path(old_path), self.__plain_path(new_path))
        inode = self.inodes.inode_from_inode_number(node.inode_number)
        self.chunks.update_plain_path(inode['data'], new_path.lstrip('/'))

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
#        os.unlink(self.__plain_path(path))
        node = self.nodes.node_from_path(path)
        inode = self.inodes.inode_from_inode_number(node.inode_number)
        hash = inode['data']
        self.__unlink_or_rmdir(path)

        node_id = self.nodes.some_node_id_from_inode_number_not_equal_node_id(inode.inode_number, node.node_id)
        if node_id is not None: # this is the hardlink handling.
            data_path = self.nodes.data_path_from_node_id(node_id)
            if data_path is not None:
                self.log.debug('path "' + path + '" will be replaced by "' + data_path + '"')
                self.chunks.update_plain_path(hash, data_path)
            os.unlink(self.__plain_path(path))
#        else: # no hardlink to same file exists. Still we must handle chunks
#            data_path = self.chunks.chunk_from_hash(hash).plain_path
#            self.chunks.remove_and_handle_data_path(inode['data'])
#            self.storage.remove_file(PlainPath(data_path))

        self.storage.commit()
        return 0

    def __unlink_or_rmdir(self, path):
        node = self.nodes.node_from_path(path)
        inode = self.inodes.inode_from_inode_number(node.inode_number)
        data_id = inode['data']
        if self.nodes.node_has_base_nodes(node.node_id):
            old_path = node.path
            node.path = ''
            node.parent_node_id = 0
            self.nodes.update_node(node, old_path)
        else:
            self.nodes.delete_node(node)
            if self.nodes.inode_not_used_anymore(inode):
                file_system_object_type = inode["type"]
                self.inodes.delete_inode(inode.inode_number)
                if file_system_object_type == FILE:
                    self.__remove_data_path_recursively(data_id)

        return 0

    def __remove_data_path_recursively(self, data_id):
#        file_diff_entry = self.chunks.entry_from_data_id(data_id)
#        while self.inodes.data_id_not_used_anymore(data_id) and self.chunks.no_hash_dependent_anymore_on(file_diff_entry.hash):
#            previous_data_path = self.chunks.base_of(data_path)
#            self.storage.remove('perm/' + data_path)
#            self.chunks.delete_element(data_path)
#            data_path = previous_data_path
#            if data_path is None:
#                break
        pass

    def rmdir(self, path): # TODO: check if this is funciton is allowd to delete all sub-"nodes"
        self.log.debug("PARAMS: path = '%s'", path)
        self.__assert_readwrite()
        os.rmdir(self.__plain_path(path))
        self.__unlink_or_rmdir(path)
        self.storage.commit()
        return 0

    def open(self, path, flags):
        self.log.debug("PARAMS: path = '%s', flags = %s", path, flags2string(flags))
        node = self.nodes.node_from_path(path)
        inode = self.inodes.inode_from_inode_number(node.inode_number)
        if flags & os.O_WRONLY or flags & os.O_RDWR:
            self.__assert_readwrite()

            hash = inode['data']
            if not self.inodes.attribute_exists_in_current_version(node.inode_number, 'data'):
                if flags & os.O_WRONLY:
                    self.__copy_from_plain_to_perm(path, hash)
                    self.inodes.update_inode_in_place(node.inode_number, {'data': MD5SUM_FOR_EMPTY_STRING})
                    self.chunks.insert(Chunk(MD5SUM_FOR_EMPTY_STRING, None, path.lstrip('/'), 0))
                elif flags & os.O_RDWR:
                    self.inodes.update_inode_in_place(node.inode_number, {'data': hash})
                    self.chunks.insert(Chunk(hash, None, PlainPath(path.lstrip('/')), inode['size']))
                    self.storage.copy_file(PlainPath(path.lstrip('/')), PermanentPath(hash))

            if self.inodes.attribute_has_previous_versions(node.inode_number, 'data'):
                tmp_path = TemporaryPath(hash, self.storage)
                previous_inode = self.inodes.inode_of_previous_version_from_inode_number(node.inode_number)
                Patcher(self.storage).apply_patches_and_save_as(dependency_chain(self.chunks, previous_inode['data']), tmp_path)
            else:
                tmp_path = None
                previous_inode = None

            plain_path = PlainPath(path.lstrip('/'))
            if flags & os.O_WRONLY:
                return OpenFileInWriteMode(self.storage, self.chunks, plain_path, tmp_path, previous_inode)
            elif flags & os.O_RDWR:
                assert False
#                return OpenFileInReadWriteMode(self.storage, plain_path, tmp_path)
        else: # apparently there is nothing like a "read" flag
            hash = inode['data']
            if is_based_on_other_hash(self.chunks, hash):
                working_data_path = TemporaryPath(hash + '.' + str(uuid4()), self.storage)
                Patcher(self.storage).apply_patches_and_save_as(dependency_chain(self.chunks, hash), working_data_path)
            else:
                chunk = self.chunks.chunk_from_hash(hash)
                if chunk.plain_path is None:
                    working_data_path = PermanentPath(chunk.hash)
                else:
                    working_data_path = PlainPath(chunk.plain_path)

            return OpenFileInReadMode(self.storage, working_data_path)

    def __copy_from_plain_to_perm(self, plain_path, hash):
        if not os.path.exists(self.storage.real_path(PermanentPath(hash))):
            self.chunks.clear_plain_path(plain_path.lstrip('/'))
            self.storage.copy_file(PlainPath(plain_path.lstrip('/')), PermanentPath(hash))
        else:
            self.chunks.remove_chunk_by_plain_path(plain_path.lstrip('/'))


    def read(self, path, length, offset, fH):
        buf = fH.read(length, offset)
        return buf

    def write(self, path, buf, offset, fH):
        fH.write(buf, offset)
        return len(buf)

    def flush(self, path, fh):
        self.log.debug("PARAMS: path = '%s', fH = %s", path, fh)
        try:
            if (#isinstance(fh, OpenFileInReadWriteMode) or 
                isinstance(fh, OpenFileInWriteMode)):
                node = self.nodes.node_from_path(path)
                inode = self.inodes.inode_from_inode_number(node.inode_number)
                new_size, new_hash = fh.flush()
                if new_hash != inode['data']:
                    self.inodes.update_inode_in_place(node.inode_number, {'size': new_size, 'data': new_hash})
#                    self.__remove_data_path_recursively(old_data_path)
            self.storage.commit()
        except Exception, e:
            traceback.print_exc(file=sys.stderr)
            raise Exception(str(e))
        return 0

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
#        file_handle = self.open(path, os.O_WRONLY)
#        file_handle.file_handle.truncate(length)
#        self.flush(path, file_handle)
#        self.release(path, 0, file_handle)
        return 0


    def chown(self, path, uid, gid): # FIXME: make these changes also in plain
        self.log.debug("PARAMS: path = '%s'", path)
        ctime = time.time()
        return self.__update_attributes(path, {'gid': gid, 'uid': uid, 'atime': ctime, 'ctime':ctime})

    def chmod(self, path, mode):
        self.log.debug("PARAMS: path = '%s'", path)
        self.storage.chmod_file(PlainPath(path.lstrip('/')), mode)
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


def init_logger():
    log = logging.getLogger('cozyfs')
    log.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('  %(asctime)s Line %(lineno)-3d %(levelname)-7s Fnc: %(funcName)-10s: %(message)s')
    handler.setFormatter(formatter)
    log.addHandler(handler)

    debug_handler = logging.FileHandler('/tmp/cozyfs_log')
    debug_handler.setFormatter(formatter)
    debug_handler.setLevel(logging.DEBUG)
    log.addHandler(debug_handler)


class InputParameters:
    pass

def parse_commandline(argv):
    option_parser = optparse.OptionParser(usage="%prog <device-dir> <mount-point> [<options>]")
    option_parser.add_option('-v', '--version', dest='version', help='Specifies the backup-version to mount.')
    option_parser.add_option('-r', '--readonly', dest='readonly', default=False, action='store_true', help='Specifies to mount the backup-version as read-only.')
    option_parser.add_option('-b', '--backup-id', dest='backup_id', help='Specifies the backup-ID of the backup.')
    (options, args) = option_parser.parse_args(argv)
    if len(args) < 2:
        option_parser.print_help()
        sys.exit("cozyfs.py <device-dir> <mount-point> [<options>]")
    input_params = InputParameters()
    input_params.device_dir = args[0]
    input_params.mountpoint = args[1]
    input_params.backup_id = options.backup_id
    input_params.version = options.version
    input_params.readonly = options.readonly
#    input_params.coverage = options.coverage
    return input_params

def pydevBrk():
    print "BREAK"
    pydevdPath = "/opt/eclipse/dropins/plugins/org.python.pydev.debug_1.5.1.1258496115/pysrc"
    if not pydevdPath in sys.path:
        sys.path.append(pydevdPath)
        try:
            import pydevd
            pydevd.settrace()
        except ImportError:
            print "cannot connect"

def main(argv=sys.argv[1:]):
#    pydevBrk()
    input_params = parse_commandline(argv)

    init_logger()
    db = connect_to_database(path_join(input_params.device_dir, DBFILE))
    storage = ConsistenceStorage(db, input_params.device_dir)

    FS = CozyFS(storage, input_params, fetch_mp=False, usage='cozyfs.py <device-dir> <mount-point> [<options>]')
    FS.parse(['-f'])
    FS.main()
    storage.close()
    db.close()

    FS.close()
    logging.getLogger('cozyfs').debug("exiting properly.")

if __name__ == '__main__':
#    cProfile.run('mount()', 'cozyfs-profile-output')
    main()
