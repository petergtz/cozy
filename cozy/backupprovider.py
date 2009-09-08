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

import cozyfsbackup
import plainbackup

class BackupProvider:

    def get_backup(self, backup_path, config):
        if config.backup_type == 'PlainFS':
            return plainbackup.PlainBackup(backup_path, config.backup_id)
        elif config.backup_type == 'CozyFS':
            return cozyfsbackup.CozyFSBackup(backup_path, config.backup_id)
        else:
            raise Exception('Backup type does not exist')
