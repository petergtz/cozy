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
import xdelta3

import cProfile


DBFILE = "fsdb"

FILE = 1
SOFT_LINK = 2
HARD_LINK = 3
DIFF = 4
DIRECTORY = 5

DIFF_LIMIT = 0.5


def query2log(query):
    return query.replace('?', '%s')

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


class CozyFS(fuse.Fuse):
    def __init__(self, *args, **kw):
        fuse.Fuse.__init__(self, *args, **kw)
        self.multithreaded = False # CHECKME: is this really necessary
        self.cached_node_ids = dict()
        self.cached_inodes = dict()
        self.cached_attributes = dict()
        self.commit_counter = 0

    def my_commit(self):
        self.commit_counter += 1
        if self.commit_counter > 100:
            self.db.commit()
            self.commit_counter = 0

#    def __init_cached_file_tree(self):
#        query = "select nodename, node_id, parent_node_id from Nodes where " + self.__backup_id_versions_where_statement('Nodes') + " group by node_id order by node_id, version desc"
#        self.db.execute(query)
#        self.cached_file_tree = []

#    def __init_cached_inodes(self):
 #   	for pair in self.db.execute('SELECT node_id, inode FROM Hardlinks'):
  #  		self.cached_inodes[pair[0]] = pair[1]

    def main(self):

        if not hasattr(self, "target_dir"):
            exit('No target dir for backup data specified')
        if not hasattr(self, "backup_id"):
            exit("no backup_id given")


# FIXME: maybe move all this into __init__. See doc for better understanding if must be here or __init__
# for how to use arguments see gmailfs
        try:
            self.db = sqlite3.connect(self.target_dir + "/" + DBFILE)
            self.db.row_factory = sqlite3.Row
            self.db.text_factory = str
        except sqlite3.OperationalError, e:
            sys.stderr.write("Error: Could not open database file: " + self.target_dir + "/" + DBFILE + "\n")
            exit(3)
#            raise "Error: Could not open database file: "+self.target_dir+"/"+DBFILE+"\n"

        self.readonly = True

        if not hasattr(self, "version"):
            ret = self.db.execute('SELECT version FROM Versions WHERE backup_id=? ORDER BY version DESC', (self.backup_id,)).fetchone()
            if ret == None:

                exit('backup_id does not exist in filesystem')
            self.version = ret[0]

        # check if another version is based on this one and set read/write flag accordingly
        cursor = self.db.execute("select * from Versions where based_on_version=? and backup_id=?", (int(self.version), int(self.backup_id)))
        if cursor.fetchone() == None:
            self.readonly = False

        if self.readonly == False:
            self.lockfile = os.path.join(self.target_dir, 'lock')
            if os.path.exists(self.lockfile):
                sys.stderr.write("Error: Filesystem is already mounted. If not, please remove " + self.lockfile + " manually and try again.\n")
                exit(4)

            os.mknod(self.lockfile)

        version = int(self.version)
        self.versions = []
        while version != None:
            self.versions.append(version)
            cursor = self.db.execute("select based_on_version from Versions where version=? and backup_id=?", (version, self.backup_id))
            version = cursor.fetchone()[0]

        log.debug("Backup_id: %s, Versions: %s", self.backup_id, self.versions)

        return fuse.Fuse.main(self)


    def close(self):
        if self.readonly == False:
            self.db.commit()
            os.remove(self.lockfile)
        self.db.close()

    def __backup_id_versions_where_statement(self, table_name):
        return " (backup_id = " + self.backup_id + " AND (" + (table_name + ".version = ") + (" or " + table_name + ".version = ").join(map(str, self.versions)) + ") ) "


    def __get_node_id_from_path(self, path):
        log.debug("PARAMS: path = '%s'", path)
        if path == '/':
            return 0

        if self.cached_node_ids.has_key(path):
            return self.cached_node_ids[path]

        parent_node_id = 0
        built_path = '/'
        for nodename in path.split('/')[1:-1]:
            if self.cached_node_ids.has_key(os.path.join(built_path, nodename)):
                parent_node_id = self.cached_node_ids[os.path.join(built_path, nodename)]
            else:
                parent_node_id = '(' + "select node_id from Nodes where " + self.__backup_id_versions_where_statement('Nodes') + " group by node_id having nodename='" + nodename + "' and parent_node_id=" + str(parent_node_id) + " order by node_id, version desc" + ')'

            built_path = os.path.join(built_path, nodename)

        query = "select node_id from Nodes where " + self.__backup_id_versions_where_statement('Nodes') + " group by node_id having nodename='" + path.split('/')[-1] + "' and parent_node_id=" + str(parent_node_id) + " order by node_id, version desc"
        result = self.db.execute(query).fetchone()
        if result is None:
            self.cached_node_ids[path] = None
            return None
        self.cached_node_ids[path] = result[0]
#        print query, "RESULTS:", result[0]
        return result[0]

    def __get_inode(self, node_id):
        if self.cached_inodes.has_key(node_id):
            return self.cached_inodes[node_id]

        inode = self.db.execute('SELECT inode FROM Hardlinks WHERE node_id=?', (node_id,)).fetchone()[0]
        self.cached_inodes[node_id] = inode
        return inode

    def __get_attributes_from_node_id(self, node_id):
    	if self.cached_attributes.has_key(node_id):
    		return self.cached_attributes[node_id]
        row = dict()
        row['inode'] = self.__get_inode(node_id)
        attributes = ['size', 'atime', 'mtime', 'ctime', 'mode', 'uid', 'gid']
        for attribute in attributes:
            log.debug('select ' + attribute + '  from ' + attribute + ' where inode=? and ' +
                        self.__backup_id_versions_where_statement(attribute) + ' order by version desc')
            cursor = self.db.execute('select ' + attribute + '  from ' + attribute + ' where inode=? and ' +
                        self.__backup_id_versions_where_statement(attribute) + ' order by version desc',
                        (row['inode'],))
            row[attribute] = cursor.fetchone()[0]
        cursor = self.db.execute('select type  from DataPaths where inode=? and ' +
                    self.__backup_id_versions_where_statement('DataPaths') + ' order by version desc',
                    (row['inode'],))
        row['type'] = cursor.fetchone()[0]

        self.cached_attributes[node_id] = row
        return row


    def getattr(self, path):
#        log.debug("path = '%s'",path)
        st = Stat()
        if path == '/':
            st.st_nlink = 2 # FIXME: get number of links for DB
            st.st_size = 4096
            st.st_mode = stat.S_IFDIR | 0755
            return st

        log.debug("path = '%s'", path)
        node_id = self.__get_node_id_from_path(path)
        if node_id == None:
            return - errno.ENOENT

        row = self.__get_attributes_from_node_id(node_id)
        if row == None:
            raise Exception, "Node entry without corresponding hardlink- or data-entry"

        st.st_atime = int(row['atime'])
        st.st_mtime = int(row['mtime'])
        st.st_ctime = int(row['ctime'])

        if row['type'] == DIRECTORY:
            st.st_nlink = 2
            # FIXME: this cannot be done like this anymore with a versioned filesystem:
            # FIXME: there is no fast way to do that now, so we comment this out.
            # It should be solved with cached data somehow in the future
#                    cursor = self.db.execute('select count(Nodes.nodename) from Nodes,Hardlinks,DataPaths where parent_node_id=? and Nodes.node_id=Hardlinks.node_id and Hardlinks.inode=DataPaths.inode and DataPaths.type=?', (node_id, DIRECTORY))
#                    st.st_nlink += cursor.fetchone()[0]
            st.st_size = 4096 # FIXME: what size should this be?
            st.st_mode = stat.S_IFDIR | row['mode']
        elif row["type"] == FILE:
            st.st_nlink = 1 # FIXME: get number of links for DB
            st.st_size = int(row['size'])
            st.st_mode = stat.S_IFREG | row['mode']
        elif row["type"] == DIFF:
            st.st_nlink = 1 # FIXME: get number of links for DB
            st.st_size = int(row['size'])
            st.st_mode = stat.S_IFREG | row['mode']
        elif row["type"] == SOFT_LINK:
            st.st_nlink = 1 # FIXME: get number of links for DB
            data_path = self.__get_data_path_from_path(path)
# FIXME: this seems to be quite a mess with all that symlink stuff! Not sure if the current way is the correct way!
            abs_data_path = os.path.normpath(os.path.join(os.path.dirname(path), data_path))
            st.st_size = len(data_path)
            attr = self.getattr(abs_data_path)
            if isinstance(attr, int):
                st.st_mode = stat.S_IFLNK #row['mode']
            else:
                st.st_mode = stat.S_IFLNK | (attr.st_mode & ~stat.S_IFDIR)#row['mode']
        else:
            raise Exception, "Error: unknown file type \"" + str(row["type"]) + "\" in database."
        st.st_uid = row["uid"]
        st.st_gid = row["gid"]
        log.debug("RETURN %s", str(st))
        return st

    def readdir(self, path, offset):
        log.debug("PARAMS: path = '%s, offset = '%s'", path, offset)
        entries = ['.', '..']
        node_id = self.__get_node_id_from_path(path)
        cursor = self.db.execute("select nodename from Nodes where " + self.__backup_id_versions_where_statement('Nodes') + " group by node_id having parent_node_id=? order by node_id, version desc", (node_id,))
        for c in cursor:
            if c[0] != None:
                log.debug(c[0])
                entries.append(c[0])
        for entry in entries:
            yield fuse.Direntry(entry)

    def __get_new_inode(self):
        ret = self.db.execute('select max(inode) from Hardlinks').fetchone()
        if ret[0] == None:
            return 1
        else:
            return ret[0] + 1

    def __mknod_or_dir(self, path, mode, type):
        log.debug("PARAMS: path = '%s, mode = %s, dev = %s", path, mode, type)
        if self.readonly:
            log.error("Can't write to FS in a restore session")
            return - errno.EROFS

        pe = path.rsplit('/', 1)
        if pe[0] == '': # FIXME: there must be a more elegant solution
            pe[0] = '/'

        new_inode = self.__get_new_inode()
        if type == FILE:
            hash = md5sum_from_string('') # TODO: this could acutally be done only once.
        ctime = time.time()

        if type == DIRECTORY:
            self.db.execute('insert into DataPaths (backup_id,version,inode,type) values(?,?,?,?)', (self.backup_id, self.versions[0], new_inode, DIRECTORY))
        elif type == FILE:
            self.db.execute('insert into DataPaths (backup_id,version,inode, data_path,type) values(?,?,?,?,?)', (self.backup_id, self.versions[0], new_inode, hash, FILE))
        else:
            return - errno.EIO
        self.db.execute('insert into uid (backup_id,version,inode, uid) values(?,?,?,?)', (self.backup_id, self.versions[0], new_inode, self.GetContext()['uid']))
        self.db.execute('insert into gid (backup_id,version,inode, gid) values(?,?,?,?)', (self.backup_id, self.versions[0], new_inode, self.GetContext()['gid']))
        self.db.execute('insert into mode (backup_id,version,inode, mode) values(?,?,?,?)', (self.backup_id, self.versions[0], new_inode, mode))
        self.db.execute('insert into atime (backup_id,version,inode, atime) values(?,?,?,?)', (self.backup_id, self.versions[0], new_inode, ctime))
        self.db.execute('insert into ctime (backup_id,version,inode, ctime) values(?,?,?,?)', (self.backup_id, self.versions[0], new_inode, ctime))
        self.db.execute('insert into mtime (backup_id,version,inode, mtime) values(?,?,?,?)', (self.backup_id, self.versions[0], new_inode, ctime))
        self.db.execute('insert into size (backup_id,version,inode, size) values(?,?,?,?)', (self.backup_id, self.versions[0], new_inode, 0))

        query = 'insert into Hardlinks (node_id, inode) values (null,?)'
        log.debug(query2log(query), new_inode)
        cursor = self.db.execute(query, (new_inode,))
        new_node_id = cursor.lastrowid
        self.cached_inodes[new_node_id] = new_inode
        self.cached_attributes[new_node_id] = {'inode': new_inode,
                                             'type': type,
                                             'uid': self.GetContext()['uid'],
                                             'gid': self.GetContext()['gid'],
                                             'mode': mode,
                                             'atime': ctime,
                                             'ctime': ctime,
                                             'mtime': ctime,
                                             'size': 0 }

        query = 'insert into Nodes (backup_id,version,node_id,nodename,parent_node_id) values (?,?,?,?,?)'
        log.debug(query2log(query), self.backup_id, self.versions[0], new_node_id, pe[1], self.__get_node_id_from_path(pe[0]))
        self.db.execute(query, (self.backup_id, self.versions[0], new_node_id, pe[1], self.__get_node_id_from_path(pe[0])))

        if type == FILE:
            # although creating an empty file is not necessary it simplifies the open function later, since we have no special case
            if not os.path.exists(self.target_dir + '/FilePool/' + hash):
                try:
                    open(self.target_dir + '/FilePool/' + hash, 'w').close()
                except:
                    return - errno.EIO # TODO: check if this is really the right error msg

        self.my_commit()
        self.cached_node_ids[path] = new_node_id
        return 0

    def mknod(self, path, mode, dev): #TODO: if file already exists, only change file time. DO NOT empty file!
        log.debug("PARAMS: path = '%s, mode = %s, dev = %s", path, mode, dev)
        return self.__mknod_or_dir(path, mode, FILE)

    def mkdir(self, path, mode):
        log.debug("PARAMS: path = '%s', mode = %s", path, mode)
        return self.__mknod_or_dir(path, mode, DIRECTORY)

    def rename(self, old, new):
        log.debug("PARAMS: old = '%s', new = '%s'", old, new)
        if self.readonly:
            log.error("Can't write to FS in a restore session")
            return - errno.EROFS

        node_id = self.__get_node_id_from_path(old)
        basename = os.path.basename(new)
        dirname = os.path.dirname(new)
        parent_node_id = self.__get_node_id_from_path(dirname)
        if self.__has_current_node(node_id):
            self.db.execute("update Nodes set nodename = ?, parent_node_id = ? where node_id = ? and backup_id = ? and version = ?", (basename, parent_node_id, node_id, self.backup_id, self.versions[0]))
        else:
            self.db.execute("insert into Nodes (backup_id, version, node_id, nodename, parent_node_id) values (?,?,?,?,?) ", (self.backup_id, self.versions[0], node_id, basename, parent_node_id))

        del self.cached_node_ids[old]
        self.cached_node_ids[new] = node_id

        ctime = time.time()
        self.__update_attributes(self.__get_inode_from_path(new), {'atime': ctime, 'mtime':ctime})

        self.my_commit()
        return 0

    def link(self, src_path, target_path):
        log.debug("PARAMS: src_path = '%s', target_path = '%s'", src_path, target_path)
        if self.readonly:
            log.error("Can't write to FS in a restore session")
            return - errno.EROFS

        pe = target_path.rsplit('/', 1)
        inode = self.__get_inode_from_path(src_path)
        cursor = self.db.execute("insert into Hardlinks (node_id,inode) values (null,?)", (inode,))
        new_node_id = cursor.lastrowid
        self.cached_inodes[new_node_id] = inode
        self.cached_node_ids[target_path] = new_node_id
        self.db.execute("insert into Nodes (backup_id, version, node_id, parent_node_id, nodename) values (?,?,?,?,?)", \
                        (self.backup_id, self.versions[0], new_node_id, self.__get_node_id_from_path(pe[0]), pe[1]))
        self.my_commit()


    def symlink(self, src_path, target_path):
        log.debug("PARAMS: src_path = '%s', target_path = '%s'", src_path, target_path)
        if self.readonly:
            log.error("Can't write to FS in a restore session")
            return - errno.EROFS

        (dirname, basename) = os.path.split(target_path)

        new_inode = self.__get_new_inode()
        ctime = time.time()

        self.db.execute('insert into DataPaths (backup_id,version,inode, data_path,type) values(?,?,?,?,?)', (self.backup_id, self.versions[0], new_inode, src_path, SOFT_LINK))
        self.db.execute('insert into uid (backup_id,version,inode, uid) values(?,?,?,?)', (self.backup_id, self.versions[0], new_inode, self.GetContext()['uid']))
        self.db.execute('insert into gid (backup_id,version,inode, gid) values(?,?,?,?)', (self.backup_id, self.versions[0], new_inode, self.GetContext()['gid']))
        self.db.execute('insert into mode (backup_id,version,inode, mode) values(?,?,?,?)', (self.backup_id, self.versions[0], new_inode, 0))
        self.db.execute('insert into atime (backup_id,version,inode, atime) values(?,?,?,?)', (self.backup_id, self.versions[0], new_inode, ctime))
        self.db.execute('insert into ctime (backup_id,version,inode, ctime) values(?,?,?,?)', (self.backup_id, self.versions[0], new_inode, ctime))
        self.db.execute('insert into mtime (backup_id,version,inode, mtime) values(?,?,?,?)', (self.backup_id, self.versions[0], new_inode, ctime))
        self.db.execute('insert into size (backup_id,version,inode, size) values(?,?,?,?)', (self.backup_id, self.versions[0], new_inode, 0))

        query = 'insert into Hardlinks (node_id, inode) values (null,?)'
        log.debug(query2log(query), new_inode)
        cursor = self.db.execute(query, (new_inode,))
        new_node_id = cursor.lastrowid

        self.cached_attributes[new_node_id] = {'inode': new_inode,
                                             'type': SOFT_LINK,
                                             'uid': self.GetContext()['uid'],
                                             'gid': self.GetContext()['gid'],
                                             'mode':  0,
                                             'atime': ctime,
                                             'ctime': ctime,
                                             'mtime': ctime,
                                             'size': 0 }

        self.cached_inodes[new_node_id] = new_inode
        self.cached_node_ids[target_path] = new_node_id

        query = 'insert into Nodes (backup_id,version,node_id,nodename,parent_node_id) values (?,?,?,?,?)'
        log.debug(query2log(query), self.backup_id, self.versions[0], new_node_id, basename, self.__get_node_id_from_path(dirname))
        self.db.execute(query, (self.backup_id, self.versions[0], new_node_id, basename, self.__get_node_id_from_path(dirname)))

        self.my_commit()
        return 0
        #TODO: insert cached handling

    def readlink(self, path):
        log.debug("PARAMS: path = '%s'", path)
        log.debug("RETURNING: path = '%s'", self.__get_data_path_from_path(path))
        return self.__get_data_path_from_path(path)

    def __has_base_nodes(self, node_id):
        cursor = self.db.execute("select count(*) from Nodes where node_id = ? and version <> ? and " + self.__backup_id_versions_where_statement('Nodes'), (node_id, self.versions[0]))
        return cursor.fetchone()[0]

    def __has_base_inodes(self, inode, attribute):
        cursor = self.db.execute('select count(*) from ' + attribute + ' where inode = ? and version <> ? and ' + self.__backup_id_versions_where_statement(attribute), (inode, self.versions[0]))
        return cursor.fetchone()[0]

    def __get_previous_version_of_data_path_from_inode(self, inode):
        return self.db.execute("select data_path from DataPaths where inode = ? and version <> ? and " + self.__backup_id_versions_where_statement('DataPaths') + " order by version desc",
                                (inode, self.backup_ids[0])).fetchone()[0]

    def __has_current_node(self, node_id):
        cursor = self.db.execute("select count(*) from Nodes where node_id = ? and backup_id = ? and version = ?", (node_id, self.backup_id, self.versions[0]))
        return cursor.fetchone()[0]

    def __has_current_inode(self, inode, attribute):
        cursor = self.db.execute('select count(*) from ' + attribute + ' where inode = ? and backup_id = ? and version = ?', (inode, self.backup_id, self.versions[0]))
        return cursor.fetchone()[0]


    def unlink(self, path):
        log.debug("PARAMS: path = '%s'", path)
        if self.readonly:
            log.error("Can't write to FS in a restore session")
            return - errno.EROFS

        node_id = self.__get_node_id_from_path(path)
        inode = self.__get_inode(node_id)

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
                    self.db.execute("delete from DataPaths where inode=?", (inode,))
                    self.db.execute("delete from size where inode=?", (inode,))
                    self.db.execute("delete from mode where inode=?", (inode,))
                    self.db.execute("delete from atime where inode=?", (inode,))
                    self.db.execute("delete from mtime where inode=?", (inode,))
                    self.db.execute("delete from ctime where inode=?", (inode,))
                    self.db.execute("delete from gid where inode=?", (inode,))
                    self.db.execute("delete from uid where inode=?", (inode,))
                    if self.__get_attributes_from_node_id(node_id)["type"] == FILE:
                        cursor = self.db.execute("select count(inode) from DataPaths where data_path=?", (data_path,))
                        row = cursor.fetchone()
                        if row[0] == 0:
                            os.remove(self.target_dir + '/FilePool/' + data_path)
                            # Todo: check if remove successful. if not, rollback and return "-1"!
        self.my_commit()
        del self.cached_node_ids[path]
        del self.cached_attributes[node_id]
        del self.cached_inodes[node_id]
        return 0

    def rmdir(self, path): # TODO: check if this is funciton is allowd to delete all sub-"nodes"
        log.debug("PARAMS: path = '%s'", path)
        if self.readonly:
            log.error("Can't write to FS in a restore session")
            return - errno.EROFS

        for node in self.readdir(path, 0): # 2nd param is offset. don't know how to use it
            if (node.name != '.') and (node.name != '..'): # TODO: must be a more elegant solutions
                if self.unlink(path + '/' + node.name) != 0:
                    return - 1 # TODO: return proper return value!
        return self.unlink(path)

    def __get_data_path_from_path(self, path):
        cursor = self.db.execute("select data_path from DataPaths where inode=? and " + self.__backup_id_versions_where_statement('DataPaths') + ' order by version desc', (self.__get_inode_from_path(path),))
#        cursor = self.db.execute("select DataPaths.data_path from Hardlinks, DataPaths where Hardlinks.node_id=? and Hardlinks.inode=DataPaths.inode and " + self.__backup_id_versions_where_statement('DataPaths') + ' order by DataPaths.version desc', (self.__get_node_id_from_path(path),))
        row = cursor.fetchone()
        if row == None:
            raise Exception, "Path does not exist in Database"
        if row[0] == None: # not quite elegant. should be a better solution for handling None and empty string
            return ''
        return row[0]

    def flags(self, flags):
        flagstr = ''
        if flags & os.O_RDONLY:
            flagstr += " O_RDONLY"
        if flags & os.O_WRONLY:
            flagstr += " O_WRONLY"
        if flags & os.O_RDWR:
            flagstr += " O_RDWR"
        if flags & os.O_CREAT:
            flagstr += " O_CREAT"
        if flags & os.O_EXCL:
            flagstr += " O_EXCL"
        if flags & os.O_NOCTTY:
            flagstr += " O_NOCTTY"
        if flags & os.O_TRUNC:
            flagstr += " O_TRUNC"
        if flags & os.O_APPEND:
            flagstr += " O_APPEND"
        if flags & os.O_NONBLOCK:
            flagstr += " O_NONBLOCK"
        if flags & os.O_NDELAY:
            flagstr += " O_NDELAY"
        if flags & os.O_SYNC:
            flagstr += " O_SYNC"
        if flags & os.O_DIRECT:
            flagstr += " O_DIRECT"
        if flags & os.O_LARGEFILE:
            flagstr += " O_LARGEFILE"
        return flagstr

    def __patch_inode_to_target(self, inode, version, target_path):
        log.debug("PARAMS: backup_id = '%s' inode = '%s' target_path = '%s'", version, inode, target_path)
        cursor = self.db.execute('select data_path, type from DataPaths where inode=? and version<=? and ' +
        self.__backup_id_versions_where_statement('DataPaths') + 'order by version desc', (inode, version)).fetchall()
        hashes = []
        for row in cursor:
            hashes.append(row['data_path'])
            if row['type'] == FILE:
                break

        hashes.reverse()
        shutil.copy(self.target_dir + '/FilePool/' + hashes[0], target_path)
        source = target_path
        result = target_path
        for hash in hashes[1:]: # TODO: use the merge option of xdelta instead!
            diff = (self.target_dir + '/FilePool/' + hash)
            xdelta3.xd3_main_cmdline(['xdelta3', '-f', '-d', '-s', source, diff, result])


    def open(self, path, flags):
        log.debug("PARAMS: path = '%s', flags = %s", path, self.flags(flags))
        target_path = self.target_dir + '/Tmp/' + path.replace('/', '_')
        inode = self.__get_inode_from_path(path)
        if flags & os.O_WRONLY:
            if self.readonly:
                return - errno.EROFS
            try:
                log.debug('Open file %s in WRITE mode', target_path)
                fH = open(target_path, 'w')
            except IOError, e:
                log.error("Could not open file %s in WRITE mode due to %s", path, e)
                return - 1 # TODO: find correct error value.
            return fH
        elif flags & os.O_RDWR: # TODO: adjust to handle diffs correctly
            if self.readonly:
                return - errno.EROFS
#            log.debug("Copy %s to %s",self.target_dir+'/FilePool/'+self.__get_data_path_from_path(path),self.target_dir+'/Tmp/'+path.replace('/','_'))
            self.__patch_inode_to_target(inode, self.versions[0], target_path)
            if os.path.exists(target_path): # TODO: is this check (and its consequences) really necessary? File SHOULD exist.
                mode = 'r+'
            else:
                mode = 'w+'
            try:
                log.debug('Open file %s in %s mode', target_path, mode)
                fH = open(target_path, mode)
            except IOError, e:
                log.error("Could not open file %s in READWRITE mode due to %s", path, e)
                return - 1 # TODO: find correct error value.
            return fH
        else: # there is apparently nothing like a read flag
            try:
                # TODO: check if it makes more sense to patch in the Pool directory.
                self.__patch_inode_to_target(inode, self.versions[0], target_path)
                log.debug("Open file '%s' in READ mode", target_path)
                fH = open(target_path, 'r')
            except IOError, e:
                log.error("Could not open file %s in READ mode due to %s", path, e)
                return - 1 # TODO: find correct error value.
            return fH


    def __get_inode_from_path(self, path):
    	return self.__get_inode(self.__get_node_id_from_path(path))

    def __update_attributes(self, inode, attributes):
#        if not self.cached_attributes.has_key(inode):
#            self.cached_attributes[inode] = dict()
#        self.__get_attributes_from_node_id(node_id)
        for (attribute, val) in attributes.iteritems():
            if self.__has_current_inode(inode, attribute):
                query = 'update ' + attribute + ' set ' + attribute + ' = ? where inode=? and backup_id=? and version=?'
            else:
                query = 'insert into ' + attribute + ' (' + attribute + ',inode,backup_id,version) values (?,?,?,?)'

            if self.cached_attributes.has_key(inode):
#                self.cached_attributes[inode] = dict()
                self.cached_attributes[inode][attribute] = val

            log.debug(query2log(query), val, inode, self.backup_id, self.versions[0])
            self.db.execute(query, (val, inode, self.backup_id, self.versions[0]))

        self.my_commit()

    def __update_data_path(self, inode, data_path, type):
        if self.__has_current_inode(inode, 'DataPaths'):
            query = 'update DataPaths set data_path = ?, type = ? where inode=? and backup_id=? and version=?'
        else:
            query = 'insert into Datapaths (data_path,type,inode,backup_id,version) values (?,?,?,?,?)'

        self.cached_attributes[inode]['type'] = type
        log.debug(query2log(query), data_path, type, inode, self.backup_id, self.versions[0])
        self.db.execute(query, (data_path, type, inode, self.backup_id, self.versions[0]))
        # CHECKME: why was this not here before? Is it sometimes not needed???
        self.my_commit()


    def release(self, path, flags, fH=None):
        log.debug("PARAMS: path = '%s, flags = %s, fH = %s'", path, flags, fH)
        tmp_path = fH.name
        fH.close()
        ctime = time.time()
        inode = self.__get_inode_from_path(path)
        if (flags & os.O_WRONLY) or (flags & os.O_RDWR) : # TODO: treat RDWR different in the future to allow for diffs
            filesize = os.stat(tmp_path)[stat.ST_SIZE]
            type = FILE
            # if this inode has more than the current version, then...
            if self.__has_base_inodes(inode, 'DataPaths'):
                # ... build this previous version by patching it and calc the diff between this prev and the current version:
                prev_data_path = self.target_dir + '/Tmp/' + path.replace('/', '_') + '.previous'
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

            if not os.path.exists(self.target_dir + '/FilePool/' + hash):
                log.debug("Move %s to %s", tmp_path, self.target_dir + '/FilePool/' + hash)
                shutil.move(tmp_path, self.target_dir + '/FilePool/' + hash)
            else:
                os.remove(tmp_path)

            # save old hash to check later if files with its name can be deleted, because not needed anymore
            old_hash = self.__get_data_path_from_path(path)

            # update database with new data_path=hash (either of the actual file or of the diff)
            self.__update_data_path(inode, hash, type)
            self.__update_attributes(inode, {'size': filesize, 'atime': ctime, 'ctime':ctime, 'mtime':ctime})

            # clean the file pool, so that no orphaned files remain:
            cursor = self.db.execute("select count(*) from DataPaths where data_path=?", (old_hash,))
            if cursor.fetchone()[0] == 0:
                os.remove(self.target_dir + '/FilePool/' + old_hash)

            self.my_commit()

        else:
            os.remove(tmp_path)
            if not self.readonly:
                self.__update_attributes(inode, {'atime': ctime})

        return 0


    def read(self, path, length, offset, fH=None):
        log.debug("PARAMS: path = '%s', len = %s, offset = %s, fH = %s", path, length, offset, fH)
        fH.seek(offset)
        return fH.read(length)

    def write(self, path, buf, offset, fH=None):
        log.debug("PARAMS: path = '%s', buf = %s, offset = %s, fH = %s", path, "buffer placeholder", offset, fH)
        fH.seek(offset)
        fH.write(buf)
        return len(buf)


    def ftruncate(self, path, length, fh=None):
        log.debug("PARAMS: path = '%s', length = %s, fH = %s", path, length, fh)
        fh.truncate(length)
        return 0

# TODO: this function should also use diffs!!!
    def truncate(self, path, length, fh=None):
        log.debug("PARAMS: path = '%s', length = %s, fH = %s", path, length, fh)
        if self.readonly:
            log.error("Can't write to FS in a restore session")
            return - errno.EROFS

        inode = self.__get_inode_from_path(path)
        data_path = self.__get_data_path_from_path(path) # old data path
        ctime = time.time()

        # Copy file to the tmp dir and truncate it:
        tmp_path = self.target_dir + '/Tmp/' + path.replace('/', '_')
        log.debug('Copy file %s to %s.', self.target_dir + '/FilePool/' + data_path, tmp_path)
        shutil.copy(self.target_dir + '/FilePool/' + data_path, tmp_path)
        try:
            log.debug('Open, truncate and close file %s in r+ mode.', tmp_path)
            fh = open(tmp_path, 'r+')
            fh.truncate(length)
            fh.close()
        except:
            log.error('Cannot truncate temporary file %s', tmp_path)

        # Calculate new data path=hash and move it back to the file pool:
        new_data_path = md5sum(tmp_path)
        log.debug('Move file %s to %s.', tmp_path, self.target_dir + '/FilePool/' + new_data_path)
        shutil.move(tmp_path, self.target_dir + '/FilePool/' + new_data_path)

        # update database with new data path:
        self.__update_data_path(inode, new_data_path, FILE)
        self.__update_attributes(inode, {'size': length, 'atime': ctime, 'ctime':ctime, 'mtime':ctime})

        # if there is no entry in the database anymore with the old data path=old hash, delete it:
        cursor = self.db.execute("select count(*) from DataPaths where data_path=?", (data_path,))
        if cursor.fetchone()[0] == 0:
            os.remove(self.target_dir + '/FilePool/' + data_path)

        self.my_commit()

        return 0


    def flush(self, path, fh=None):
        log.debug("PARAMS: path = '%s', fH = %s", path, fh)
        fh.flush()
        return 0

    def fsync(self, path, fdatasync, fh=None):
        log.debug("PARAMS: path = '%s', fdatasync = %s, fH = %s", path, fdatasync, fh)
        return 0

    def chown(self, path, uid, gid):
        log.debug("PARAMS: path = '%s'", path)

        if self.readonly:
            log.error("Can't write to FS in a restore session")
            return - errno.EROFS

        ctime = time.time()
        self.__update_attributes(self.__get_inode_from_path(path), {'gid': gid, 'uid': uid, 'atime': ctime, 'ctime':ctime})
        return 0

    def chmod(self, path, mode):
        log.debug("PARAMS: path = '%s'", path)

        if self.readonly:
            log.error("Can't write to FS in a restore session")
            return - errno.EROFS

        ctime = time.time()
        self.__update_attributes(self.__get_inode_from_path(path), {'mode': mode, 'atime': ctime, 'ctime':ctime})
        return 0

    def utimens(self, path, acc_nsec, mod_nsec):
        log.debug("PARAMS: path = '%s' acc_nsec = %s, mod_nsec = %s", path, acc_nsec.tv_sec, mod_nsec.tv_sec)

        if self.readonly:
            log.error("Can't write to FS in a restore session")
            return - errno.EROFS

        self.__update_attributes(self.__get_inode_from_path(path), {'atime': acc_nsec.tv_sec, 'mtime':mod_nsec.tv_sec})

        return 0

    def statfs(self):
#        log.debug("")
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

def mount():
    FS = CozyFS(version="CozyFS version 0.1", usage='Usage not quite sure yet')
    FS.parser.add_option(mountopt="target_dir", metavar="TARGET_DIR", default="", help="location of backup data")
    FS.parser.add_option(mountopt="backup_id", metavar="BACKUP_ID", default="", help="mount backup from daspecified backup_id")
    FS.parser.add_option(mountopt="version", metavar="BASE", default="", help="version of backup this backup is based up on")
    FS.parse(values=FS)
    FS.main()
    FS.close()


#    FS.db.commit()

sqlite3.enable_callback_tracebacks(True)
log = logging.getLogger('cozyfs')
#try:
#    sys.argv.index('DEBUG')
#except ValueError:
log.setLevel(logging.ERROR)
#else:
#log.setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('  Line %(lineno)-3d %(levelname)-7s Fnc: %(funcName)-10s: %(message)s'))
log.addHandler(handler)


if __name__ == '__main__':
#    cProfile.run('mount()', 'cozyfs-profile-output')
    mount()
