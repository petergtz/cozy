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
#FIXME: replacing dashes by underscores as temp file name is NOT safe!!!

#from sqlite3 import lastrowid
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

import cProfile

import optparse

DBFILE = "fsdb"

FILE = 1
SOFT_LINK = 2
HARD_LINK = 3
DIFF = 4
DIRECTORY = 5

DIFF_LIMIT = 0.5

MAX_TRANSACTIONS = 100

MD5SUM_FOR_EMPTY_STRING = md5sum_from_string('')

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
#        self.direct_io = 1
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


class InodesRepository(object):
    def __init__(self, db, versions, backup_id):
        self.db = db
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
        query = 'INSERT INTO ' + name + ' (' + name + ',inode,backup_id,version) VALUES (?,?,?,?)'
        self.log.debug(query2log(query), value, inode, self.backup_id, self.versions[0])
        self.db.execute(query, (value, inode, self.backup_id, self.versions[0]))

    def __get_new_inode_number(self):
        max_inode_number = self.db.execute('select max(inode_number) from Nodes').fetchone()[0]
        if max_inode_number == None: max_inode_number = 0
        return max_inode_number + 1

    def inode_from_inode_number(self, inode_number):
        if not self.cached_inodes.has_key(inode_number):
            inode = self.__inode_from_inode_number_from_database(inode_number)
            self.cached_inodes[inode_number] = inode
        self.log.debug(self.cached_inodes[inode_number])
        return self.cached_inodes[inode_number]

    def __inode_from_inode_number_from_database(self, inode_number):
        inode = Inode(inode_number=inode_number)
        for attribute_name in self.attributes_names:
            cursor = self.db.execute("SELECT %(attr_name)s FROM %(attr_name)s WHERE inode=? AND %(where)s ORDER BY version DESC" %
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

            self.log.debug(query2log(query), val, inode_number, self.backup_id, self.versions[0])
            self.db.execute(query, (val, inode_number, self.backup_id, self.versions[0]))

    def __attribute_exists_in_current_version(self, inode_number, attribute):
        cursor = self.db.execute('select count(*) from ' + attribute + ' where inode = ? and backup_id = ? and version = ?', (inode_number, self.backup_id, self.versions[0]))
        return cursor.fetchone()[0]

    def delete_inode(self, inode_number):
        for name in self.attributes_names:
            self.__delete_attribute(inode_number, name)
        del self.cached_inodes[inode_number]

    def __delete_attribute(self, inode_number, name):
        query = 'DELETE FROM ' + name + ' WHERE inode = ?'
        self.log.debug(query2log(query), inode_number)
        self.db.execute(query, (inode_number,))

    def data_path_not_used_anymore(self, data_path):
        count = self.db.execute("select count(*) from data_path where data_path=?", (data_path,)).fetchone()[0]
        return count == 0


class Node(object):
    def __init__(self, path, inode_number, node_id=None, parent_node_id=None):
        self.node_id = node_id
        self.path = path
        self.parent_node_id = parent_node_id
        self.inode_number = inode_number

    def __str__(self):
        return "node_id: %s , path: %s , parent_node_id: %s , inode_number: %s" % (str(self.node_id),
     self.path, str(self.parent_node_id), str(self.inode_number))


class NodesRepository(object):
    def __init__(self, db, versions, backup_id):
        self.db = db
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
        self.log.debug(query2log(query), self.backup_id, self.versions[0], basename, node.node_id, parent_node.node_id, node.inode_number)
        self.db.execute(query, (self.backup_id, self.versions[0], basename, node.node_id, parent_node.node_id, node.inode_number))

        self.cached_nodes[node.path] = node

    def __get_new_node_id(self):
        ret = self.db.execute('select max(node_id) from Nodes').fetchone()
        if ret[0] == None:
            return 1
        else:
            return ret[0] + 1

    def node_from_path(self, path):
        self.log.debug("PARAMS: path = '%s'", path)
        if not self.cached_nodes.has_key(path):
            node = self.__node_from_path_from_database(path)
            self.cached_nodes[path] = node
        self.log.debug("Returning: " + str(self.cached_nodes[path]))
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
                                 "' and parent_node_id=(" + parent_node_id + ") order by node_id, version desc"


        query = "select node_id, inode_number from Nodes where " + \
                         self.__backup_id_versions_where_statement('Nodes') + \
                         " group by node_id having nodename='" + os.path.basename(path) + \
                         "' and parent_node_id=(" + parent_node_id + ") order by node_id, version desc"
        self.log.debug(query)
        row = self.db.execute(query).fetchone()
        if row is None:
            return None
        else:
            return Node(path, row['inode_number'], row['node_id'], parent_node_id)

    def __backup_id_versions_where_statement(self, table_name):
        return " (" + table_name + ".backup_id = " + self.backup_id + " AND (" + (table_name + ".version = ") + (" or " + table_name + ".version = ").join(map(str, self.versions)) + ") ) "

    def update_node(self, node, old_path):
        basename = os.path.basename(node.path)
        if self.__has_current_node(node.node_id):
            self.db.execute("update Nodes set nodename = ?, parent_node_id = ? where node_id = ? and backup_id = ? and version = ?", (basename, node.parent_node_id, node.node_id, self.backup_id, self.versions[0]))
        else:
            self.db.execute("insert into Nodes (backup_id, version, node_id, nodename, parent_node_id, inode_number) values (?,?,?,?,?,?) ", (self.backup_id, self.versions[0], node.node_id, basename, node.parent_node_id, node.inode_number))


        del self.cached_nodes[old_path]
        if node.path != '':
            self.cached_nodes[node.path] = node

    def __has_current_node(self, node_id):
        row = self.db.execute("select count(*) from Nodes where node_id = ? and backup_id = ? and version = ?", (node_id, self.backup_id, self.versions[0])).fetchone()
        return row[0]

    def delete_node(self, node):
        self.db.execute("delete from Nodes where backup_id=? and version=? and node_id=?", (self.backup_id, self.versions[0], node.node_id))
        del self.cached_nodes[node.path]

    def inode_not_used_anymore(self, inode):
        count = self.db.execute("select count(*) from Nodes where inode_number=?", (inode.inode_number,)).fetchone()[0]
        return count == 0


class OpenFile(object):
    def __init__(self, storage, file_path, mode):
        self.storage = storage
        self.file_handle = None
        if mode == 'read':
            self.__open_in_read_mode(file_path)
        elif mode == 'write':
            self.__open_in_write_mode(file_path)
        elif mode == 'readwrite':
            self.__open_in_readwrite_mode(file_path)

    def __open_in_read_mode(self, data_path):
        filediff_deps_chain = self.__get_filediff_dependency_chain(data_path)
        if len(filediff_deps_chain) == 1:
            self.file_handle = self.storage.open(filediff_deps_chain[0])
        else:
            filename = self.__apply_patches_into_tmp_dir(filediff_deps_chain)
            self.file_handle = self.storage.open_from_tmp_dir(filename, 'r')

    def __open_in_write_mode(self, data_path):
        filediff_deps_chain = self.__get_filediff_dependency_chain(data_path)
        filename = self.__apply_patches_into_tmp_dir(filediff_deps_chain)
        self.__create_a_copy_in_tmp_dir_for_later_diff(filename)
        self.file_handle = self.storage.open_from_tmp_dir(target_path, 'w')

    def __open_in_readwrite_mode(self, data_path):
        filediff_deps_chain = self.__get_filediff_dependency_chain(data_path)
        filename = self.__apply_patches_into_tmp_dir(filediff_deps_chain)
        self.file_handle = self.storage.open_from_tmp_dir(target_path, 'r+')

    def __get_filediff_dependency_chain(self, data_path):
        data_paths = [data_path]
        while True:
            row = self.storage.db_execute("SELECT based_on_data_path FROM FileDiffDependencies WHERE data_path = ?", (data_path,)).fetchone()
            if row is None:
                break
            else:
                data_path = row[0]
                data_paths.append(data_path)

        return data_paths

    def __apply_patches_into_tmp_dir(self, filediff_deps_chain):
        pass

    def __create_a_copy_of_original_in_tmp_dir_for_later_diff(self, filename):
        self.original_data_path

    def flush(self):
        self.file_handle.flush()
        self.__create_diff_in_permanent_dir()
        self.storage.copy_file_to_permanent(self.file_handle.name)

    def __create_diff_in_permanent_dir(self):
        self.hash = md5sum(self.file_handle.name)
        __create_actual_diff_in_permanent_dir()
        pass

    def close(self):
        file_path = self.file_handle.name
        self.file_handle.close()
        if self.storage.path_is_in_tmp_dir(file_path):
            os.remove(file_path)

class ConsistenceStorage(object):
    '''
    A low level layer for database access and file access.
    The commit method allows to commit consistent changes
    between database and files.
    '''

    def __init__(self, db):
        self.db = db
        self.commit_delay_counter = 0

    def db_execute(self, query, params):
        return self.db.execute(query, params)

    def open_from_permanent(self, data_path):
        pass

    def copy_from_tmp_to_permanent(self):
        pass

    def commit(self):
        self.commit_delay_counter += 1
        if self.commit_delay_counter > MAX_TRANSACTIONS:
            self.__real_commit()
            self.commit_delay_counter = 0

    def __real_commit(self):
        pass





class CozyFS(fuse.Fuse):
    def __init__(self, db, input_params, *args, **kw):
        fuse.Fuse.__init__(self, *args, **kw)
        self.multithreaded = False # CHECKME: is this really necessary
        self.log = logging.getLogger('cozyfs')
        self.db = db
        self.readonly = input_params.readonly
        self.backup_id = input_params.backup_id
        self.fuse_args.mountpoint = input_params.mountpoint
        self.device_dir = input_params.device_dir

        self.version = self.__init_version(input_params.version)
        self.__set_readonly_if_version_is_base()
        self.__create_lock_file_if_not_readonly()
        self.__init_base_versions(self.version)

        self.inodes = InodesRepository(self.db, self.versions, self.backup_id)
        self.nodes = NodesRepository(self.db, self.versions, self.backup_id)

    def __init_version(self, version):
        if version is None:
            ret = self.db.execute('SELECT version FROM Versions WHERE backup_id=? ORDER BY version DESC', (self.backup_id,)).fetchone()
            if ret == None:
                exit('backup_id does not exist in filesystem')
            return ret[0]
        else:
            return version

    def __set_readonly_if_version_is_base(self):
        cursor = self.db.execute("select * from Versions where based_on_version=? and backup_id=?", (int(self.version), int(self.backup_id)))
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
            cursor = self.db.execute("select based_on_version from Versions where version=? and backup_id=?", (version, self.backup_id))
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
        elif attributes["type"] == FILE or attributes["type"] == DIFF:
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
        node = self.nodes.node_from_path(path)
        cursor = self.db.execute("select nodename from Nodes where " + self.__backup_id_versions_where_statement('Nodes') + " group by node_id having parent_node_id=? order by node_id, version desc", (node.node_id,))
        yield fuse.Direntry('.')
        yield fuse.Direntry('..')
        for c in cursor:
            if c[0] != None:
                self.log.debug(c[0])
                yield fuse.Direntry(c[0])

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

        self.db.commit()
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

        self.db.commit()


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

        self.db.commit()
        return 0

    def readlink(self, path):
        self.log.debug("PARAMS: path = '%s'", path)
        node = self.nodes.node_from_path(path)
        inode = self.inodes.inode_from_inode_number(node.inode_number)
        self.log.debug("RETURNING: path = '%s'", inode['data_path'])
        return inode['data_path']

    def __has_base_nodes(self, node_id):
        cursor = self.db.execute("select count(*) from Nodes where node_id = ? and version <> ? and " + self.__backup_id_versions_where_statement('Nodes'), (node_id, self.versions[0]))
        return cursor.fetchone()[0]

    def __has_base_inodes(self, inode, attribute):
        cursor = self.db.execute('select count(*) from ' + attribute + ' where inode = ? and version <> ? and ' + self.__backup_id_versions_where_statement(attribute), (inode, self.versions[0]))
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

        self.db.commit()
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
                        os.remove(self.target_dir + '/FilePool/' + data_path)
        self.db.commit()
        return 0


    def rmdir(self, path): # TODO: check if this is funciton is allowd to delete all sub-"nodes"
        self.log.debug("PARAMS: path = '%s'", path)
        self.__assert_readwrite()

        for node in self.readdir(path, 0): # 2nd param is offset. don't know how to use it
            if (node.name != '.') and (node.name != '..'): # TODO: must be a more elegant solutions
                if self.unlink(path + '/' + node.name) != 0:
                    return - 1 # TODO: return proper return value!
        return self.unlink(path)

    def __patch_inode_to_target(self, inode, version, target_path):
        self.log.debug("PARAMS: backup_id = '%s' inode = '%s' target_path = '%s'", version, inode, target_path)
        cursor = self.db.execute('select data_path from data_path where inode=? and version<=? and ' +
                                    self.__backup_id_versions_where_statement('data_path') + 'order by version desc', (inode, version))
        type_cursor = self.db.execute('select type from type where inode=? and version<=? and ' +
                                    self.__backup_id_versions_where_statement('type') + 'order by version desc', (inode, version))
        hashes = []
        for row in cursor:
            hashes.append(row['data_path'])
            if type_cursor.fetchone()['type'] == FILE:
                break

        hashes.reverse()
        shutil.copy(self.device_dir + '/FilePool/' + hashes[0], target_path)
        source = target_path
        result = target_path
        for hash in hashes[1:]: # TODO: use the merge option of xdelta instead!
            diff = (self.device_dir + '/FilePool/' + hash)
            cmdline = ['xdelta3', '-f', '-d', '-s', source, diff, result]
            self.log.debug(' '.join(cmdline))
            xdelta3.xd3_main_cmdline(cmdline)
        self.log.debug('Target_path is ' + result)


    def open(self, path, flags):
        self.log.debug("PARAMS: path = '%s', flags = %s", path, flags2string(flags))
        target_path = self.device_dir + '/Tmp/' + path.replace('/', '_')
        node = self.nodes.node_from_path(path)
        if flags & os.O_WRONLY:
            self.__assert_readwrite()
            self.log.debug('Open file %s in WRITE mode', target_path)
            fH = open(target_path, 'w')
        elif flags & os.O_RDWR: # TODO: adjust to handle diffs correctly
            self.__assert_readwrite()
            self.__patch_inode_to_target(node.inode_number, self.versions[0], target_path)
            self.log.debug('Open file %s in r+ mode', target_path)
            fH = open(target_path, 'r+')
        else: # apparently there is nothing like a "read" flag
            # TODO: check if it makes more sense to patch in the Pool directory.
            self.__patch_inode_to_target(node.inode_number, self.versions[0], target_path)
            self.log.debug("Open file '%s' in READ mode", target_path)
            fH = open(target_path, 'r')
        return fH


    def release(self, path, flags, fH=None):
        self.log.debug("PARAMS: path = '%s, flags = %s, fH = %s'", path, flags, fH)
        tmp_path = fH.name
        fH.close()
        ctime = time.time()
        node = self.nodes.node_from_path(path)
        inode = self.inodes.inode_from_inode_number(node.inode_number)
        if (flags & os.O_WRONLY) or (flags & os.O_RDWR) : # TODO: treat RDWR different in the future to allow for diffs
            filesize = os.stat(tmp_path)[stat.ST_SIZE]
            type = FILE
            # if this inode has more than the current version, then...
            if self.__has_base_inodes(node.inode_number, 'data_path'):
                # ... build this previous version by patching it and calc the diff between this prev and the current version:
                prev_data_path = self.device_dir + '/Tmp/' + path.replace('/', '_') + '.previous'
                self.__patch_inode_to_target(node.inode_number, self.versions[1], prev_data_path)
                xdelta3.xd3_main_cmdline(['xdelta3', '-e', '-s', prev_data_path, tmp_path, tmp_path + '.diff'])
                os.remove(prev_data_path)
                # Only if patch is significantly smaller, use it:
                if os.stat(tmp_path + '.diff')[stat.ST_SIZE] < DIFF_LIMIT * os.stat(tmp_path)[stat.ST_SIZE]:
                    type = DIFF
                    os.remove(tmp_path)
                    tmp_path = tmp_path + '.diff'
# TODO: elif diff is 0, then do NOTHING!
                else:
                    os.remove(tmp_path + '.diff')

            new_data_path = md5sum(tmp_path)

            absolute_new_data_path = os.path.join(self.device_dir, 'FilePool', new_data_path)
            if not os.path.exists(absolute_new_data_path):
                self.log.debug("Move %s to %s", tmp_path, absolute_new_data_path)
                shutil.move(tmp_path, absolute_new_data_path)
            else:
                os.remove(tmp_path)

            old_data_path = inode['data_path']

            self.inodes.update_inode_in_place(inode.inode_number, {'data_path': new_data_path, 'type': type, 'size': filesize, 'atime': ctime, 'ctime':ctime, 'mtime':ctime})

            if self.inodes.data_path_not_used_anymore(old_data_path):
                os.remove(os.path.join(self.device_dir, 'FilePool', old_data_path))

        else:
            os.remove(tmp_path)
            if not self.readonly:
                self.inodes.update_inode_in_place(inode.inode_number, {'atime': ctime})

        self.db.commit()
        return 0


    def read(self, path, length, offset, fH=None):
        self.log.debug("PARAMS: path = '%s', len = %s, offset = %s, fH = %s", path, length, offset, fH)
        fH.seek(offset)
        return fH.read(length)

    def write(self, path, buf, offset, fH=None):
        self.log.debug("PARAMS: path = '%s', buf = %s, offset = %s, fH = %s", path, "buffer placeholder", offset, fH)
        fH.seek(offset)
        fH.write(buf)
        return len(buf)


# TODO: this function should also use diffs!!!
    def truncate(self, path, length, fh=None):
        self.log.debug("PARAMS: path = '%s', length = %s, fH = %s", path, length, fh)
        self.__assert_readwrite()

        node = self.nodes.node_from_path(path)
        inode = self.inodes.inode_from_inode_number(node.inode_number)
        old_data_path = inode['data_path']
        ctime = time.time()

        # Copy file to the tmp dir and truncate it:
        tmp_path = self.device_dir + '/Tmp/' + path.replace('/', '_')
        self.log.debug('Copy file %s to %s.', self.device_dir + '/FilePool/' + old_data_path, tmp_path)
        shutil.copy(self.device_dir + '/FilePool/' + old_data_path, tmp_path)
        try:
            self.log.debug('Open, truncate and close file %s in r+ mode.', tmp_path)
            fh = open(tmp_path, 'r+')
            fh.truncate(length)
            fh.close()
        except:
            self.logerror('Cannot truncate temporary file %s', tmp_path)

        # Calculate new data path=hash and move it back to the file pool:
        new_data_path = md5sum(tmp_path)
        self.log.debug('Move file %s to %s.', tmp_path, self.device_dir + '/FilePool/' + new_data_path)
        shutil.move(tmp_path, self.device_dir + '/FilePool/' + new_data_path)

        self.inodes.update_inode_in_place(node.inode_number, {'data_path': new_data_path, 'type': FILE, 'size': length, 'atime': ctime, 'ctime':ctime, 'mtime':ctime})

        if self.inodes.data_path_not_used_anymore(old_data_path):
            os.remove(self.device_dir + '/FilePool/' + old_data_path)

        self.db.commit()
        return 0


    def flush(self, path, fh=None):
        self.log.debug("PARAMS: path = '%s', fH = %s", path, fh)
        fh.flush()
        return 0

    def fsync(self, path, fdatasync, fh=None):
        self.log.debug("PARAMS: path = '%s', fdatasync = %s, fH = %s", path, fdatasync, fh)
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
        self.db.commit()
        return 0

    def statfs(self):
        host_fs = os.statvfs(self.target_dir)
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
        sys.stderr.write("Error: Could not open database file\n")
        exit(3)


def initLogger():
    log = logging.getLogger('cozyfs')
    log.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('  Line %(lineno)-3d %(levelname)-7s Fnc: %(funcName)-10s: %(message)s'))
    log.addHandler(handler)

class InputParameters:
    pass

def parse_commandline():
    option_parser = optparse.OptionParser()
    option_parser.add_option('-v', '--version', dest='version')
    option_parser.add_option('-r', '--readonly', dest='readonly', default=False, action='store_true')
    option_parser.add_option('-b', '--backup-id', dest='backup_id')
    (options, args) = option_parser.parse_args()
    if len(args) < 2:
        sys.exit("PRINT USAGE")
    input_params = InputParameters()
    input_params.device_dir = args[0]
    input_params.mountpoint = args[1]
    input_params.backup_id = options.backup_id
    input_params.version = options.version
    input_params.readonly = options.readonly
    return input_params


def main():

    input_params = parse_commandline()
    initLogger()
    db = connect_to_database(os.path.join(input_params.device_dir, DBFILE))

    FS = CozyFS(db, input_params, fetch_mp=False, version="CozyFS version 0.1", usage='Usage not quite sure yet')
#    FS.parser.add_option("--test", metavar="READONLY", default="", help="version of backup this backup is based up on")
    FS.parse(['-f'])
    FS.main()
    FS.close()
    db.close()


if __name__ == '__main__':
#    cProfile.run('mount()', 'cozyfs-profile-output')
    main()
