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

from optparse import OptionParser

from cozy.back_up import back_up

option_parser = OptionParser()
option_parser.add_option('-s', '--start-immediately', dest='ask', default=True, action='store_false',
                         help='Do not ask for confirmation before backup, but start immediately.')
(options, args) = option_parser.parse_args()

if options.ask:
    answer = raw_input("Do you really want to back up your data?")
else:
    answer = 'y'

if answer in ['y', 'Y', 'yes', 'Yes']:
    back_up()
