Installation
=============

Please see file INSTALL.

Configuration
==============

Note: So far, only a single path can be set up for backup. In the ideal case you
would want to use your home directory.


Usage:
=======

From the command line call

    ./cozy-backup-applet
    
The rest should be self explaining.

For a manual backup you can also always call:

    ./cozy-backup


Whenever you need your backed up data, open the folder where you would like to
"travel back in time". Then click on the Cozy status icon and choose "Start
Restore Session" Find the file you're looking for and copy it to the desired
location.

Things that happen internally
==============================

Backup
-------

Executing cozy-backup
- create a new backup-version and mount it as a filesystem into a temporary directory
- it will then sync this temporary directory with your data
- then it will unmount the filesystem

Restore
--------

If you start a restore session
- the latest backup-version will be mounted into a temporary directory
- nautilus will move into this directory
