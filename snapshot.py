#!/usr/bin/python


import sys
import os
import sqlite3
import time

FSDB='fsdb'

# TODO: check if FS is mounted and refuse to do the snapshot. We don't want a
#       inconsistent FS.
#		How can we check this? -> create a lock file in the backupdir

def snapshot(target_path,backup_id,based_on_version=None):

	db=sqlite3.connect(os.path.join(target_path,FSDB))
	db.row_factory=sqlite3.Row
	db.text_factory=str

	if based_on_version is None:
		ret=db.execute('SELECT version FROM Versions WHERE backup_id=? ORDER BY version DESC',(backup_id,)).fetchone()
		if ret==None:
			exit('backup_id does not exist in filesystem')
		based_on_version=ret[0]

	if db.execute('SELECT count(*) FROM Versions WHERE backup_id=? AND version=?',(backup_id,based_on_version)).fetchone()[0]==0:
		exit('Cannot find specifed backup_id/version in filesystem')

	version=int(time.time())

	db.execute('INSERT INTO Versions (backup_id,version,based_on_version) VALUES (?,?,?)',
				(backup_id,version,based_on_version))

	db.commit()

	print version


if __name__ == '__main__':
	if len(sys.argv)<3:
		exit('Wrong number of arguments. \nUSAGE: '+__file__+' target-path backup-id version-based-on')

	if len(sys.argv)<4:
		based_on_version=None
	else:
		based_on_version=sys.argv[3]

	snapshot(target_path=sys.argv[1],backup_id=int(sys.argv[2]),based_on_version=based_on_version)