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
import time

FSDB = 'fsdb'

def snapshot(target_path, backup_id, based_on_version=None):

	db = sqlite3.connect(os.path.join(target_path, FSDB))
	db.row_factory = sqlite3.Row
	db.text_factory = str

	if based_on_version is None:
		ret = db.execute('SELECT version FROM Versions WHERE backup_id=? ORDER BY version DESC', (backup_id,)).fetchone()
		if ret == None:
			exit('backup_id does not exist in filesystem')
		based_on_version = ret[0]

	if db.execute('SELECT count(*) FROM Versions WHERE backup_id=? AND version=?', (backup_id, based_on_version)).fetchone()[0] == 0:
		exit('Cannot find specifed backup_id/version in filesystem')

	version = int(time.time())

	db.execute('INSERT INTO Versions (backup_id,version,based_on_version) VALUES (?,?,?)',
				(backup_id, version, based_on_version))

	db.commit()

	return version


if __name__ == '__main__':
	if len(sys.argv) < 3:
		exit('Wrong number of arguments. \nUSAGE: ' + __file__ + ' target-path backup-id version-based-on')

	if len(sys.argv) < 4:
		based_on_version = None
	else:
		based_on_version = int(sys.argv[3])

	version = snapshot(target_path=sys.argv[1], backup_id=int(sys.argv[2]), based_on_version=based_on_version)
	print version
