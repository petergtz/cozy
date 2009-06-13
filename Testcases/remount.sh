#!/bin/sh
fusermount -z -u /home/peter/Tolles/Cozy/MountPoints/MP1/
/home/peter/Tolles/Cozy/CozyFS/CozyFS.py /home/peter/Tolles/Cozy/MountPoints/MP1 -o based_on=kkk -f &