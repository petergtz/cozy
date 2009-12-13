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
import optparse

FSDB = 'fsdb'

def snapshot(target_path, backup_id, based_on_version=None):

    db = sqlite3.connect(os.path.join(target_path, FSDB))
    db.row_factory = sqlite3.Row
    db.text_factory = str

    if based_on_version is None:
        ret = db.execute('SELECT version FROM Versions WHERE backup_id=? ORDER BY version DESC', (backup_id,)).fetchone()
        if ret == None:
            based_on_version = None
        else:
            based_on_version = ret[0]

    version = int(time.time())

    db.execute('INSERT INTO Versions (backup_id,version,based_on_version) VALUES (?,?,?)',
                (backup_id, version, based_on_version))

    db.commit()

    return version


if __name__ == '__main__':
    option_parser = optparse.OptionParser(usage="%prog [-b <based-on-version>] <device-dir> <backup-id>")
    option_parser.add_option('-b', '--based_on_version', type='int', dest='based_on_version', default= -1, help='Specifies the version to this version should be based on.')
    (options, args) = option_parser.parse_args()
    if len(args) != 2:
        option_parser.print_help()
        sys.exit()
    device_dir = args[0]
    backup_id = args[1]

    if options.based_on_version == -1:
        version = snapshot(device_dir, int(backup_id))
    else:
        version = snapshot(device_dir, int(backup_id), options.based_on_version)
    print version
