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

from  cozy.backup_action import back_up


if __name__ == '__main__':

    if len(sys.argv) > 2:
        exit("USAGE: " + __name__ + "[-f]; -f = start immediately backing up data")


    if len(sys.argv) == 2 and sys.argv[1] == '-f':
        answer = 'y'
    else:
        answer = raw_input("Do you really want to back up your data?")

    if answer in ['y', 'Y', 'yes', 'Yes']:
        back_up()
