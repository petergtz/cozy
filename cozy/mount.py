
import subprocess
import time
import os


class MountException(Exception): pass

def mount(target_path, mountpoint, backup_id, version=None):
	if not os.path.exists(mountpoint):
		os.makedirs(mountpoint)

	cmdline = ['cozyfs.py', mountpoint, '-o', 'target_dir=' + target_path + ',backup_id=' + str(backup_id), '-f']

	if version is not None:
		cmdline[-2] = cmdline[-2] + ',version=' + str(version)

	print 'mounting: ' + ' '.join(cmdline)
	process = subprocess.Popen(cmdline)
	time.sleep(2)
	if process.poll() != None:
		if process.poll() == 3:
			raise MountException('Error: Mount failed because database couldn''t be found')
		else:
			raise MountException('Error: Mount failed due to unknown reasons')


def umount(mountpoint):
	print 'unmounting'
	os.system('fusermount -z -u ' + mountpoint)
	os.rmdir(mountpoint)

