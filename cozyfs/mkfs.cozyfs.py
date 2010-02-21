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

import sys
import os
import sqlite3
import errno
import time
import tempfile
import shutil
import optparse

FSDB = 'fsdb'


def parse_cmdline():
    option_parser = optparse.OptionParser(usage="%prog [-f] <device-dir> <backup-id> ")
    option_parser.add_option('-f', '--force', dest='force', default=False, action='store_true', help='Deletes all existing data with the same backup-id.')
    option_parser.add_option('-n', '--no-version', dest='should_create_first_version', default=True, action='store_false', help='If given, no first version will be created in the database. A version must then be created using cozyfssnapshot.py.')
    (options, args) = option_parser.parse_args()
    if len(args) != 2:
        option_parser.print_help()
        sys.exit()
    return args[0], int(args[1]), options.force, options.should_create_first_version

def create_dirs_if_not_existent(device_dir):
    for dir in ['FilePool', 'Tmp', 'plain']:
        path = os.path.join(device_dir, dir)
        if not os.path.exists(path):
            os.mkdir(path)

def connect_to_db(device_dir):
    db = sqlite3.connect(os.path.join(device_dir, FSDB))
    db.row_factory = sqlite3.Row
    db.text_factory = str
    return db

def create_tables_if_not_existent(db):

    db.executescript("""
    CREATE TABLE IF NOT EXISTS Versions (backup_id NUMERIC, version NUMERIC, based_on_version NUMERIC);
    CREATE TABLE IF NOT EXISTS data_id (backup_id NUMERIC, version NUMERIC, data_id NUMERIC, inode NUMERIC);
    CREATE TABLE IF NOT EXISTS type (backup_id NUMERIC, version NUMERIC, type NUMERIC, inode NUMERIC);
    CREATE TABLE IF NOT EXISTS Nodes (backup_id NUMERIC, version NUMERIC, nodename TEXT, parent_node_id NUMERIC, node_id NUMERIC, inode_number NUMERIC);
    CREATE TABLE IF NOT EXISTS atime (atime NUMERIC, version NUMERIC, backup_id NUMERIC, inode NUMERIC);
    CREATE TABLE IF NOT EXISTS ctime (backup_id NUMERIC, version NUMERIC, ctime NUMERIC, inode NUMERIC);
    CREATE TABLE IF NOT EXISTS gid (backup_id NUMERIC, version NUMERIC, gid NUMERIC, inode NUMERIC);
    CREATE TABLE IF NOT EXISTS mode (backup_id NUMERIC, version NUMERIC, inode NUMERIC, mode NUMERIC);
    CREATE TABLE IF NOT EXISTS mtime (backup_id NUMERIC, version NUMERIC, inode NUMERIC, mtime NUMERIC);
    CREATE TABLE IF NOT EXISTS size (backup_id NUMERIC, version NUMERIC, inode NUMERIC, size NUMERIC);
    CREATE TABLE IF NOT EXISTS uid (backup_id NUMERIC, version NUMERIC, inode NUMERIC, uid NUMERIC);
    CREATE TABLE IF NOT EXISTS FileDiffDependencies (data_id NUMERIC, hash TEXT, based_on_hash TEXT, data_path TEXT, data_size NUMERIC);
    """)

    db.commit()

def backup_id_exists_already(db, backup_id):
    return db.execute('SELECT count(*) FROM Versions WHERE backup_id=?', (backup_id,)).fetchone()[0] > 0

def delete_backup_ids(db, backup_id):
    db.execute('DELETE FROM data_path WHERE backup_id = ?', (backup_id,))
    db.execute('DELETE FROM Nodes WHERE backup_id = ?', (backup_id,))
    db.execute('DELETE FROM Versions WHERE backup_id = ?', (backup_id,))
    db.execute('DELETE FROM type WHERE backup_id = ?', (backup_id,))
    db.execute('DELETE FROM atime WHERE backup_id = ?', (backup_id,))
    db.execute('DELETE FROM ctime WHERE backup_id = ?', (backup_id,))
    db.execute('DELETE FROM gid WHERE backup_id = ?', (backup_id,))
    db.execute('DELETE FROM uid WHERE backup_id = ?', (backup_id,))
    db.execute('DELETE FROM mode WHERE backup_id = ?', (backup_id,))
    db.execute('DELETE FROM mtime WHERE backup_id = ?', (backup_id,))
    db.execute('DELETE FROM size WHERE backup_id = ?', (backup_id,))
    db.execute('DELETE FROM FileDiffDepencies', (backup_id,))

    db.commit()

def create_first_version(db, backup_id):
    version = int(time.time())
    db.execute("INSERT INTO Versions (backup_id,version,based_on_version) values (?,?,?)",
            (backup_id, version, None))
    db.commit()
    return version

def main():
    device_dir, backup_id, should_delete_existing_backup_ids, \
            should_create_first_version = parse_cmdline()

    create_dirs_if_not_existent(device_dir)

    db = connect_to_db(device_dir)
    create_tables_if_not_existent(db)
    a_version_exists_already = False
    if backup_id_exists_already(db, backup_id):
        if should_delete_existing_backup_ids:
            delete_backup_ids(db, backup_id)
        else:
            print '''Specified backup_id already exists in this backup. 
                     Nothing will be changed. If you want to delete all
                     existing data with the specified backup_id, use --force.'''
            a_version_exists_already = True

    if should_create_first_version and not a_version_exists_already:
        version = create_first_version(db, backup_id)
        print version

    db.close()


if __name__ == '__main__':
    main()
