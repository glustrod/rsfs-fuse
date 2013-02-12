rsfs-fuse
=========

FUSE driver for the rapidshare cloud service

!!!ATTENTION!!!
===============

The driver is currently in pre alpha state and has some limitations:

* Files can only copied to the drive **NOT edited**
* Don't copy files bigger than 2GB to the drive
* Before the upload the file is stored **COMPLETE in the RAM**
* Rename/moving is currently not working

Installation
============

Download the fuse.py from https://github.com/terencehonles/fusepy and put it in the same directory as the rsfs.py.
Follow the instruction to convert the file with 2to3.
Run rsfs.py.
