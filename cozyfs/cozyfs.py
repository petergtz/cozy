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
#        fuse.Stat.__init__(self)


#class Serializeable(object):
#    def set_id_col_name(self, id):
#        pass
#
#    def get_id_col_name(self, id):
#        pass


class FileAttributes(object):
    def __init__(self, inode, **attributes):
        self.inode = inode
        self.attributes = attributes
        self.changed_attributes = {}

    def __getitem__(self, key):
        return self.attributes[key]

    def __setitem__(self, key, value):
        self.changed_attributes[key] = True
        self.attributes[key] = value
#        return self.__setattr__(key, value)

#    def __iter__(self):
#        return self.attributes.__iter__()
#    def set_attributes_unchanged(self):
#        self.changed_attributes.clear()

class AttributesRepository(object):
    def __init__(self, db, versions, backup_id):
        self.db = db
        self.versions = versions
        self.backup_id = backup_id
        self.attributes_names = ['size', 'atime', 'mtime', 'ctime', 'mode', 'uid', 'gid', 'type', 'data_path']
        self.cached_attributes = {}
        self.cached_attributes[0] = FileAttributes(inode=0, size=4096, atime=0, mtime=0, ctime=0, mode=0, uid=0, gid=0, type=DIRECTORY)
        self.log = logging.getLogger('cozyfs')

    def insert(self, file_attributes):
        inode = self.__get_new_inode()
        file_attributes.inode = inode
        print file_attributes.attributes
        for (name, value) in file_attributes.attributes.iteritems():
            self.__insert_attribute(inode, name, value)
        self.cached_attributes[inode] = file_attributes

    def __insert_attribute(self, inode, name, value):
        query = 'INSERT INTO ' + name + ' (' + name + ',inode,backup_id,version) VALUES (?,?,?,?)'

        self.log.debug(query2log(query), value, inode, self.backup_id, self.versions[0])
        self.db.execute(query, (value, inode, self.backup_id, self.versions[0]))

    def __get_new_inode(self):
        ret = self.db.execute('select max(inode) from Hardlinks').fetchone()
        if ret[0] == None:
            return 1
        else:
            return ret[0] + 1

    def attributes_from_inode(self, inode):
        if not self.cached_attributes.has_key(inode):
            attributes = self.__attributes_from_inode_from_database(inode)
            self.cached_attributes[inode] = attributes
        self.log.debug(self.cached_attributes[inode])
        return self.cached_attributes[inode]

    def __attributes_from_inode_from_database(self, inode):
        attributes = FileAttributes(inode=inode)
        for attribute_name in self.attributes_names:
            cursor = self.db.execute("SELECT %(attr_name)s FROM %(attr_name)s WHERE inode=? AND %(where)s ORDER BY version DESC" %
                                     {'attr_name': attribute_name,
                                      'where': self.__backup_id_versions_where_statement(attribute_name)},
                                     (inode,))
            attributes[attribute_name] = cursor.fetchone()[0]
        return attributes

    def __backup_id_versions_where_statement(self, table_name):
        return " (" + table_name + ".backup_id = " + self.backup_id + " AND (" + (table_name + ".version = ") + (" or " + table_name + ".version = ").join(map(str, self.versions)) + ") ) "

#    def update(self, file_attributes):
#        for (name, value) in file_attributes.attributes.iteritems():
#            if file_attributes.changed_attributes[name]:
#                self.__update_attribute(file_attributes.inode, name, value)
#
#    def __update_attribute(self, inode, name, value):
#        if self.__attribute_exists_in_current_version(inode, name):
#            query = 'UPDATE ' + name + ' SET ' + name + ' = ? WHERE inode=? AND backup_id=? AND version=?'
#        else:
#            query = 'INSERT INTO ' + name + ' (' + name + ',inode,backup_id,version) VALUES (?,?,?,?)'
#
#        self.cached_attributes[inode][name] = value
#
#        self.log.debug(query2log(query), value, inode, self.backup_id, self.versions[0])
#        self.db.execute(query, (value, inode, self.backup_id, self.versions[0]))

    def __attribute_exists_in_current_version(self, inode, attribute):
        cursor = self.db.execute('select count(*) from ' + attribute + ' where inode = ? and backup_id = ? and version = ?', (inode, self.backup_id, self.versions[0]))
        return cursor.fetchone()[0]

    def update_attributes_in_place(self, inode, attributes):
        for (attribute, val) in attributes.iteritems():
            if self.__attribute_exists_in_current_version(inode, attribute):
                query = 'update ' + attribute + ' set ' + attribute + ' = ? where inode=? and backup_id=? and version=?'
            else:
                query = 'insert into ' + attribute + ' (' + attribute + ',inode,backup_id,version) values (?,?,?,?)'

            if self.cached_attributes.has_key(inode):
#                self.cached_attributes[inode] = dict()
                self.cached_attributes[inode][attribute] = val

            self.log.debug(query2log(query), val, inode, self.backup_id, self.versions[0])
            self.db.execute(query, (val, inode, self.backup_id, self.versions[0]))


    def delete(self, file_attributes):
        pass

class FileNode(object):
    pass

class NodesRepository(object):
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

        self.__init_cache()
        self.version = self.__init_version(input_params.version)
        self.__set_readonly_if_version_is_base()
        self.__create_lock_file_if_not_readonly()
        self.__init_base_versions(self.version)

        self.attributes_repository = AttributesRepository(self.db, self.versions, self.backup_id)

    def __init_cache(self):
        self.cached_node_ids = {}
        self.cached_node_ids['/'] = 0
        self.cached_inodes = dict()
        self.cached_inodes[0] = 0
#        self.cached_attributes = dict()
        #FIXME: this needs to be initialized properly:
 #       self.cached_attributes[0] = { 'size': 4096, 'atime':0, 'mtime':0, 'ctime':0, 'mode':0, 'uid':0, 'gid':0, 'type':DIRECTORY}

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


    def __get_node_id_from_path(self, path):
        self.log.debug("PARAMS: path = '%s'", path)
        if self.cached_node_ids.has_key(path):
            return self.cached_node_ids[path]
        node_id = self.__get_node_id_from_path_from_database(path)
        self.cached_node_ids[path] = node_id
        return node_id

    def __get_node_id_from_path_from_database(self, path):
        parent_node_id = '0'
        built_path = '/'
        for nodename in path.split('/')[1:]:
            built_path = os.path.join(built_path, nodename)
            if self.cached_node_ids.has_key(built_path):
                parent_node_id = str(self.cached_node_ids[built_path])
            else:
                parent_node_id = "select node_id from Nodes where " + \
                                 self.__backup_id_versions_where_statement('Nodes') + \
                                 " group by node_id having nodename='" + nodename + \
                                 "' and parent_node_id=(" + parent_node_id + ") order by node_id, version desc"
        query = parent_node_id
        row = self.db.execute(query).fetchone()
        if row is None:
            return None
        else:
            return row[0]


    def __get_inode_from_node_id(self, node_id):
        if self.cached_inodes.has_key(node_id):
            return self.cached_inodes[node_id]

        inode = self.db.execute('SELECT inode FROM Hardlinks WHERE node_id=?', (node_id,)).fetchone()[0]
        self.cached_inodes[node_id] = inode
        return inode

    def __get_attributes_from_node_id(self, node_id):
#        if not self.cached_attributes.has_key(node_id):
#            attributes = self.__get_attributes_from_node_id_from_database(node_id)
#            self.cached_attributes[node_id] = attributes
#        self.log.debug(self.cached_attributes[node_id])
#        return self.cached_attributes[node_id]
        inode = self.__get_inode_from_node_id(node_id)
        return self.attributes_repository.attributes_from_inode(inode)

#    def __get_attributes_from_node_id_from_database(self, node_id):
#        attributes = dict()
#        inode = self.__get_inode_from_node_id(node_id)
#        attribute_names = ['size', 'atime', 'mtime', 'ctime', 'mode', 'uid', 'gid', 'type']
#        for attribute in attribute_names:
#            cursor = self.db.execute('select ' + attribute + '  from ' + attribute + ' where inode=? and ' +
#                        self.__backup_id_versions_where_statement(attribute) + ' order by version DESC', # FIXME: this DESC which can be ommited is suspicious!
#                        (inode,))
#            attributes[attribute] = cursor.fetchone()[0]
#        attributes['inode'] = inode
#        return attributes

    def getattr(self, path):
        self.log.debug("path = '%s'", path)
        node_id = self.__get_node_id_from_path(path)
        if node_id == None:
            return - errno.ENOENT
        attributes = self.__get_attributes_from_node_id(node_id)
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
        node_id = self.__get_node_id_from_path(path)
        cursor = self.db.execute("select nodename from Nodes where " + self.__backup_id_versions_where_statement('Nodes') + " group by node_id having parent_node_id=? order by node_id, version desc", (node_id,))
        yield fuse.Direntry('.')
        yield fuse.Direntry('..')
        for c in cursor:
            if c[0] != None:
                self.log.debug(c[0])
                yield fuse.Direntry(c[0])

    def __pending_mknod_or_dir(self, path, mode, type):
        self.__assert_readwrite()

        ctime = time.time()
        attributes = FileAttributes(type=type, mode=mode, atime=ctime)
        self.attributes_repository.insert(attributes)
        node = FileNode(path, attributes)
        self.file_nodes_repository.insert(node)
        return 0

    def __assert_readwrite(self):
        if self.readonly:
            self.log.error("Can't write to FS in a restore session")
            e = IOError()
            e.errno = errno.EROFS
            raise e

    def __mknod_or_dir(self, path, mode, type):
        self.log.debug("PARAMS: path = '%s, mode = %s, dev = %s", path, mode, type)
        self.__assert_readwrite()

#        new_inode = self.__get_new_inode()
        if type == FILE:
            hash = MD5SUM_FOR_EMPTY_STRING
            # although creating an empty file is not necessary it simplifies the open function later, since we have no special case
            if not os.path.exists(self.device_dir + '/FilePool/' + hash):
                try:
                    os.mknod(self.device_dir + '/FilePool/' + hash)
                except:
                    return - errno.EIO # TODO: check if this is really the right error msg
        elif type == DIRECTORY:
            hash = None
        ctime = time.time()

        file_attributes = FileAttributes(inode=None,
                                       type=type,
                                       uid=self.GetContext()['uid'],
                                       gid=self.GetContext()['gid'],
                                       mode=mode,
                                       atime=ctime,
                                       mtime=ctime,
                                       ctime=ctime,
                                       size=0,
                                       data_path=hash)
        self.attributes_repository.insert(file_attributes)

        query = 'insert into Hardlinks (node_id, inode) values (null,?)'
        self.log.debug(query2log(query), file_attributes.inode)
        cursor = self.db.execute(query, (file_attributes.inode,))
        new_node_id = cursor.lastrowid
        self.cached_inodes[new_node_id] = file_attributes.inode

        path_head, path_tail = os.path.split(path)
        query = 'insert into Nodes (backup_id,version,node_id,nodename,parent_node_id) values (?,?,?,?,?)'
        self.log.debug(query2log(query), self.backup_id, self.versions[0], new_node_id, path_tail, self.__get_node_id_from_path(path_head))
        self.db.execute(query, (self.backup_id, self.versions[0], new_node_id, path_tail, self.__get_node_id_from_path(path_head)))

        self.cached_node_ids[path] = new_node_id
        self.db.commit()
        return 0

    def mknod(self, path, mode, dev): #TODO: if file already exists, only change file time. DO NOT empty file!
        self.log.debug("PARAMS: path = '%s, mode = %s, dev = %s", path, mode, dev)
        return self.__mknod_or_dir(path, mode, FILE)

    def mkdir(self, path, mode):
        self.log.debug("PARAMS: path = '%s', mode = %s", path, mode)
        return self.__mknod_or_dir(path, mode, DIRECTORY)

    def rename(self, old_path, new_path):
        self.log.debug("PARAMS: old_path = '%s', new_path = '%s'", old_path, new_path)
        self.__assert_readwrite()

        node_id = self.__get_node_id_from_path(old_path)
        dirname, basename = os.path.split(new_path)
        parent_node_id = self.__get_node_id_from_path(dirname)
        if self.__has_current_node(node_id):
            self.db.execute("update Nodes set nodename = ?, parent_node_id = ? where node_id = ? and backup_id = ? and version = ?", (basename, parent_node_id, node_id, self.backup_id, self.versions[0]))
        else:
            self.db.execute("insert into Nodes (backup_id, version, node_id, nodename, parent_node_id) values (?,?,?,?,?) ", (self.backup_id, self.versions[0], node_id, basename, parent_node_id))

        del self.cached_node_ids[old_path]
        self.cached_node_ids[new_path] = node_id

        ctime = time.time()
        self.attributes_repository.update_attributes_in_place(self.__get_inode_from_path(new_path), {'atime': ctime, 'mtime':ctime})

        self.db.commit()
        return 0

    def link(self, src_path, target_path):
        self.log.debug("PARAMS: src_path = '%s', target_path = '%s'", src_path, target_path)
        self.__assert_readwrite()

        pe = target_path.rsplit('/', 1)
        inode = self.__get_inode_from_path(src_path)
        cursor = self.db.execute("insert into Hardlinks (node_id,inode) values (null,?)", (inode,))
        new_node_id = cursor.lastrowid
        self.cached_inodes[new_node_id] = inode
        self.cached_node_ids[target_path] = new_node_id
        self.db.execute("insert into Nodes (backup_id, version, node_id, parent_node_id, nodename) values (?,?,?,?,?)", \
                        (self.backup_id, self.versions[0], new_node_id, self.__get_node_id_from_path(pe[0]), pe[1]))
        self.db.commit()


    def symlink(self, src_path, target_path):
        self.log.debug("PARAMS: src_path = '%s', target_path = '%s'", src_path, target_path)
        self.__assert_readwrite()

        ctime = time.time()

        file_attributes = FileAttributes(None, type=SOFT_LINK,
                                             uid=self.GetContext()['uid'],
                                             gid=self.GetContext()['gid'],
                                             mode=0,
                                             atime=ctime,
                                             ctime=ctime,
                                             mtime=ctime,
                                             size=len(src_path),
                                             data_path=src_path)
        self.attributes_repository.insert(file_attributes)
        new_inode = file_attributes.inode

        query = 'insert into Hardlinks (node_id, inode) values (null,?)'
        self.log.debug(query2log(query), new_inode)
        cursor = self.db.execute(query, (new_inode,))
        new_node_id = cursor.lastrowid

#        del self.cached_inodes[new_node_id]

        self.cached_inodes[new_node_id] = new_inode
        self.cached_node_ids[target_path] = new_node_id

        (dirname, basename) = os.path.split(target_path)
        query = 'insert into Nodes (backup_id,version,node_id,nodename,parent_node_id) values (?,?,?,?,?)'
        self.log.debug(query2log(query), self.backup_id, self.versions[0], new_node_id, basename, self.__get_node_id_from_path(dirname))
        self.db.execute(query, (self.backup_id, self.versions[0], new_node_id, basename, self.__get_node_id_from_path(dirname)))

        self.db.commit()
        return 0
        #TODO: insert cached handling

    def readlink(self, path):
        self.log.debug("PARAMS: path = '%s'", path)
        self.log.debug("RETURNING: path = '%s'", self.__get_data_path_from_path(path))
        return self.__get_data_path_from_path(path)

    def __has_base_nodes(self, node_id):
        cursor = self.db.execute("select count(*) from Nodes where node_id = ? and version <> ? and " + self.__backup_id_versions_where_statement('Nodes'), (node_id, self.versions[0]))
        return cursor.fetchone()[0]

    def __has_base_inodes(self, inode, attribute):
        cursor = self.db.execute('select count(*) from ' + attribute + ' where inode = ? and version <> ? and ' + self.__backup_id_versions_where_statement(attribute), (inode, self.versions[0]))
        return cursor.fetchone()[0]

    def __get_previous_version_of_data_path_from_inode(self, inode):
        return self.db.select("select data_path from data_path where inode = ? and version <> ? and " + self.__backup_id_versions_where_statement('data_path') + " order by version desc",
                                (inode, self.backup_ids[0])).next()[0]

    def __has_current_node(self, node_id):
        row = self.db.execute("select count(*) from Nodes where node_id = ? and backup_id = ? and version = ?", (node_id, self.backup_id, self.versions[0])).fetchone()
        return row[0]

    def __has_current_inode(self, inode, attribute):
        cursor = self.db.execute('select count(*) from ' + attribute + ' where inode = ? and backup_id = ? and version = ?', (inode, self.backup_id, self.versions[0]))
        return cursor.fetchone()[0]


    def unlink(self, path):
        self.log.debug("PARAMS: path = '%s'", path)
        self.__assert_readwrite()

        node_id = self.__get_node_id_from_path(path)
        inode = self.__get_inode_from_node_id(node_id)

        if self.__has_base_nodes(node_id):
            if self.__has_current_node(node_id):
                self.db.execute("update Nodes set nodename = null where node_id = ? and backup_id = ? and version = ?", (node_id, self.backup_id, self.versions[0]))
            else: # TODO: might be VERY IMPORTANT TO ALSO INSERT PARENT_NODE_ID! (dont know...)
                self.db.execute("insert into Nodes (backup_id, version, node_id) values (?,?,?) ", (self.backup_id, self.versions[0], node_id))
        else:
#            node_id = self.__get_node_id_from_path(path)
            data_path = self.__get_data_path_from_path(path)
            self.db.execute("delete from Nodes where backup_id=? and version=? and node_id=?", (self.backup_id, self.versions[0], node_id))
            cursor = self.db.execute("select count(node_id) from Nodes where node_id=?", (node_id,))
            row = cursor.fetchone()
            if row[0] == 0:
                self.db.execute("delete from Hardlinks where node_id=?", (node_id,))

                cursor = self.db.execute("select count(inode) from Hardlinks where inode=?", (inode,))
                row = cursor.fetchone()
                if row[0] == 0:
                    self.db.execute("delete from data_path where inode=?", (inode,))
                    self.db.execute("delete from type where inode=?", (inode,))
                    self.db.execute("delete from size where inode=?", (inode,))
                    self.db.execute("delete from mode where inode=?", (inode,))
                    self.db.execute("delete from atime where inode=?", (inode,))
                    self.db.execute("delete from mtime where inode=?", (inode,))
                    self.db.execute("delete from ctime where inode=?", (inode,))
                    self.db.execute("delete from gid where inode=?", (inode,))
                    self.db.execute("delete from uid where inode=?", (inode,))
                    if self.__get_attributes_from_node_id(node_id)["type"] == FILE:
                        cursor = self.db.select("select count(inode) from data_path where data_path=?", (data_path,))
                        row = cursor.next()
                        if row[0] == 0:
                            os.remove(self.target_dir + '/FilePool/' + data_path)
                            # Todo: check if remove successful. if not, rollback and return "-1"!
        del self.cached_node_ids[path]
        del self.cached_inodes[node_id]
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

    def __get_data_path_from_path(self, path):
        cursor = self.db.execute("select data_path from data_path where inode=? and " + self.__backup_id_versions_where_statement('data_path') + ' order by version desc', (self.__get_inode_from_path(path),))
#        cursor = self.db.execute("select data_path.data_path from Hardlinks, data_path where Hardlinks.node_id=? and Hardlinks.inode=data_path.inode and " + self.__backup_id_versions_where_statement('data_path') + ' order by data_path.version desc', (self.__get_node_id_from_path(path),))
        for row in cursor:
            if row[0] == None: # not quite elegant. should be a better solution for handling None and empty string
                return ''
            else:
                return row[0]
        raise Exception, "Path does not exist in Database"

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
        inode = self.__get_inode_from_path(path)
        if flags & os.O_WRONLY:
            if self.readonly:
                return - errno.EROFS
            try:
                self.log.debug('Open file %s in WRITE mode', target_path)
                fH = open(target_path, 'w')
            except IOError, e:
                self.logerror("Could not open file %s in WRITE mode due to %s", path, e)
                return - 1 # TODO: find correct error value.
            return fH
        elif flags & os.O_RDWR: # TODO: adjust to handle diffs correctly
            if self.readonly:
                return - errno.EROFS
#            self.log.debug("Copy %s to %s",self.target_dir+'/FilePool/'+self.__get_data_path_from_path(path),self.target_dir+'/Tmp/'+path.replace('/','_'))
            self.__patch_inode_to_target(inode, self.versions[0], target_path)
            if os.path.exists(target_path): # TODO: is this check (and its consequences) really necessary? File SHOULD exist.
                mode = 'r+'
            else:
                mode = 'w+'
            try:
                self.log.debug('Open file %s in %s mode', target_path, mode)
                fH = open(target_path, mode)
            except IOError, e:
                self.logerror("Could not open file %s in READWRITE mode due to %s", path, e)
                return - 1 # TODO: find correct error value.
            return fH
        else: # there is apparently nothing like a read flag
            try:
                # TODO: check if it makes more sense to patch in the Pool directory.
                self.__patch_inode_to_target(inode, self.versions[0], target_path)
                self.log.debug("Open file '%s' in READ mode", target_path)
                fH = open(target_path, 'r')
            except IOError, e:
                self.logerror("Could not open file %s in READ mode due to %s", path, e)
                return - 1 # TODO: find correct error value.
            return fH


    def __get_inode_from_path(self, path):
    	return self.__get_inode_from_node_id(self.__get_node_id_from_path(path))


    def __update_data_path(self, inode, data_path):
        if self.__has_current_inode(inode, 'data_path'):
            query = 'update data_path set data_path = ? where inode=? and backup_id=? and version=?'
        else:
            query = 'insert into data_path (data_path,inode,backup_id,version) values (?,?,?,?)'

        self.log.debug(query2log(query), data_path, inode, self.backup_id, self.versions[0])
        self.db.execute(query, (data_path, inode, self.backup_id, self.versions[0]))


    def release(self, path, flags, fH=None):
        self.log.debug("PARAMS: path = '%s, flags = %s, fH = %s'", path, flags, fH)
        tmp_path = fH.name
        fH.close()
        ctime = time.time()
        inode = self.__get_inode_from_path(path)
        if (flags & os.O_WRONLY) or (flags & os.O_RDWR) : # TODO: treat RDWR different in the future to allow for diffs
            filesize = os.stat(tmp_path)[stat.ST_SIZE]
            type = FILE
            # if this inode has more than the current version, then...
            if self.__has_base_inodes(inode, 'data_path'):
                # ... build this previous version by patching it and calc the diff between this prev and the current version:
                prev_data_path = self.device_dir + '/Tmp/' + path.replace('/', '_') + '.previous'
                self.__patch_inode_to_target(inode, self.versions[1], prev_data_path)
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

            hash = md5sum(tmp_path)

            if not os.path.exists(self.device_dir + '/FilePool/' + hash):
                self.log.debug("Move %s to %s", tmp_path, self.device_dir + '/FilePool/' + hash)
                shutil.move(tmp_path, self.device_dir + '/FilePool/' + hash)
            else:
                os.remove(tmp_path)

            # save old hash to check later if files with its name can be deleted, because not needed anymore
            old_hash = self.__get_data_path_from_path(path)

            # update database with new data_path=hash (either of the actual file or of the diff)
            self.__update_data_path(inode, hash)
            self.__update_attributes(inode, {'type': type, 'size': filesize, 'atime': ctime, 'ctime':ctime, 'mtime':ctime})

            # clean the file pool, so that no orphaned files remain:
            cursor = self.db.execute("select count(*) from data_path where data_path=?", (old_hash,))
            if cursor.fetchone()[0] == 0:
                os.remove(self.device_dir + '/FilePool/' + old_hash)

            self.db.commit()
        else:
            os.remove(tmp_path)
            if not self.readonly:
                self.__update_attributes(inode, {'atime': ctime})

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


    def ftruncate(self, path, length, fh=None):
        self.log.debug("PARAMS: path = '%s', length = %s, fH = %s", path, length, fh)
        fh.truncate(length)
        return 0

# TODO: this function should also use diffs!!!
    def truncate(self, path, length, fh=None):
        self.log.debug("PARAMS: path = '%s', length = %s, fH = %s", path, length, fh)
        self.__assert_readwrite()

        inode = self.__get_inode_from_path(path)
        data_path = self.__get_data_path_from_path(path) # old data path
        ctime = time.time()

        # Copy file to the tmp dir and truncate it:
        tmp_path = self.device_dir + '/Tmp/' + path.replace('/', '_')
        self.log.debug('Copy file %s to %s.', self.device_dir + '/FilePool/' + data_path, tmp_path)
        shutil.copy(self.device_dir + '/FilePool/' + data_path, tmp_path)
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

        # update database with new data path:
        self.__update_data_path(inode, new_data_path)
        self.__update_attributes(inode, {'type': FILE, 'size': length, 'atime': ctime, 'ctime':ctime, 'mtime':ctime})

        if self.__no_entry_in_database_with(data_path):
            os.remove(self.device_dir + '/FilePool/' + data_path)

        self.db.commit()
        return 0

    def __no_entry_in_database_with(self, data_path):
        cursor = self.db.execute("select count(*) from data_path where data_path=?", (data_path,))
        return cursor.fetchone()[0] == 0


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
        return self.__update_attributes(self.__get_inode_from_path(path), {'gid': gid, 'uid': uid, 'atime': ctime, 'ctime':ctime})

    def chmod(self, path, mode):
        self.log.debug("PARAMS: path = '%s'", path)
        ctime = time.time()
        return self.__update_attributes(self.__get_inode_from_path(path), {'mode': mode, 'atime': ctime, 'mtime': ctime})

    def utimens(self, path, acc_nsec, mod_nsec):
        self.log.debug("PARAMS: path = '%s' acc_nsec = %s, mod_nsec = %s", path, acc_nsec.tv_sec, mod_nsec.tv_sec)
        return self.__update_attributes(self.__get_inode_from_path(path), {'atime': acc_nsec.tv_sec, 'mtime':mod_nsec.tv_sec})

    def __update_attributes(self, inode, attributes):
        self.__assert_readwrite()

        self.attributes_repository.update_attributes_in_place(inode, attributes)
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
#    FS.parser.add_option(mountopt="target_dir", metavar="TARGET_DIR", default="", help="location of backup data")
#    FS.parser.add_option(mountopt="backup_id", metavar="BACKUP_ID", default="", help="mount backup from daspecified backup_id")
#    FS.parser.add_option(mountopt="version", metavar="BASE", default="", help="version of backup this backup is based up on")
#    FS.parser.add_option(mountopt="ro", TEST="READONLY", default="", help="version of backup this backup is based up on")
    FS.parser.add_option("--test", metavar="READONLY", default="", help="version of backup this backup is based up on")
#    FS.parse(values=FS)
    FS.parse(['-f'])
#    FS.parse(errex=1)
    FS.main()
    FS.close()
    db.close()
#    log.debug("REACHED THE END")


if __name__ == '__main__':
#    cProfile.run('mount()', 'cozyfs-profile-output')
    main()
