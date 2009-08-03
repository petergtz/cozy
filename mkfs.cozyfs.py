#!/usr/bin/python

import sys
import os
import sqlite3
import errno
import time
import tempfile
import shutil

FSDB = 'fsdb'

if len(sys.argv) not in [3, 4]:
    exit('Wrong number of arguments. Todo: USAGE (targetdir, unique backupid, force)')

target_path = sys.argv[1]
backup_id = int(sys.argv[2])
force = False
if len(sys.argv) == 4:
    if sys.argv[3] == 'force':
        force = True

for dir in ['FilePool', 'Tmp']:
    try:
        os.mkdir(os.path.join(target_path, dir))
    except OSError, e:
        if e.errno != errno.EEXIST:
            print 'Cannot make dirs ' + dir + ' in the specified folder: ' + e.strerror

tempdir = tempfile.mkdtemp()
if os.path.lexists(os.path.join(target_path, FSDB)):
	shutil.copy(os.path.join(target_path, FSDB), os.path.join(tempdir, FSDB))

db = sqlite3.connect(os.path.join(tempdir, FSDB))
db.row_factory = sqlite3.Row
db.text_factory = str

db.executescript("""
CREATE TABLE IF NOT EXISTS Versions (backup_id NUMERIC, version NUMERIC, based_on_version NUMERIC);
CREATE TABLE IF NOT EXISTS DataPaths (backup_id NUMERIC, version NUMERIC, type NUMERIC, data_path TEXT, inode NUMERIC);
CREATE TABLE IF NOT EXISTS Hardlinks (node_id INTEGER PRIMARY KEY, inode NUMERIC);
CREATE TABLE IF NOT EXISTS Nodes (backup_id NUMERIC, version NUMERIC, nodename TEXT, parent_node_id NUMERIC, node_id NUMERIC);
CREATE TABLE IF NOT EXISTS atime (atime NUMERIC, version NUMERIC, backup_id NUMERIC, inode NUMERIC);
CREATE TABLE IF NOT EXISTS ctime (backup_id NUMERIC, version NUMERIC, ctime NUMERIC, inode NUMERIC);
CREATE TABLE IF NOT EXISTS gid (backup_id NUMERIC, version NUMERIC, gid NUMERIC, inode NUMERIC);
CREATE TABLE IF NOT EXISTS mode (backup_id NUMERIC, version NUMERIC, inode NUMERIC, mode NUMERIC);
CREATE TABLE IF NOT EXISTS mtime (backup_id NUMERIC, version NUMERIC, inode NUMERIC, mtime NUMERIC);
CREATE TABLE IF NOT EXISTS size (backup_id NUMERIC, version NUMERIC, inode NUMERIC, size NUMERIC);
CREATE TABLE IF NOT EXISTS uid (backup_id NUMERIC, version NUMERIC, inode NUMERIC, uid NUMERIC);
""")


if db.execute('SELECT count(*) FROM Versions WHERE backup_id=?', (backup_id,)).fetchone()[0] > 0 and not force:
#    exit('Specified backup_id already exists in this filesystem. To overwrite this, use force')
    print 'Specified backup_id already exists in this filesystem. To overwrite this, use force'
elif force:
    db.execute('DELETE FROM Hardlinks WHERE node_id in (SELECT node_id FROM Nodes WHERE backup_id=?)', (backup_id,))
    db.execute('DELETE FROM DataPaths WHERE backup_id = ?', (backup_id,))
    db.execute('DELETE FROM Nodes WHERE backup_id = ?', (backup_id,))
    db.execute('DELETE FROM Versions WHERE backup_id = ?', (backup_id,))
    db.execute('DELETE FROM atime WHERE backup_id = ?', (backup_id,))
    db.execute('DELETE FROM ctime WHERE backup_id = ?', (backup_id,))
    db.execute('DELETE FROM gid WHERE backup_id = ?', (backup_id,))
    db.execute('DELETE FROM uid WHERE backup_id = ?', (backup_id,))
    db.execute('DELETE FROM mode WHERE backup_id = ?', (backup_id,))
    db.execute('DELETE FROM mtime WHERE backup_id = ?', (backup_id,))
    db.execute('DELETE FROM size WHERE backup_id = ?', (backup_id,))

version = int(time.time())

if db.execute('SELECT count(*) FROM Versions WHERE backup_id=?', (backup_id,)).fetchone()[0] == 0:
    db.execute("INSERT INTO Versions (backup_id,version,based_on_version) values (?,?,?)",
            (backup_id, version, None))

db.commit()

db.close()

shutil.copy(os.path.join(tempdir, FSDB), os.path.join(target_path, FSDB))

shutil.rmtree(tempdir)

print version
