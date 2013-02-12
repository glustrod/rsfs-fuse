#!/usr/bin/python3

# FUSE driver for the rapidshare cloud service
# Copyright (C) 2013 Glustrod
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn

from time import time

from sys import argv, exit

from stat import S_IFDIR, S_IFLNK, S_IFREG

from errno import ENOENT

import http.client
import stat
import os
import getpass
import urllib
import logging

username = ''
password = ''

class Folder:
	id = 0
	parent_id = 0
	name = None
	path = None
	basename = None
	def __init__(self, data):
		parts = data.split(",")
		self.id = int(parts[0])
		self.parent_id = int(parts[1])
		self.name = urllib.parse.unquote(parts[2])
	
	def __repr__(self):
		return 'Folder <' + str(self.id) + ", " + str(self.parent_id) + ", " + str(self.name) + ", " + str(self.path) + ", " + str(self.basename) + '>';

class File:
	id = 0
	filename = None
	size = 0
	realfolder = 0
	uploadtime = 0
	md5hex = None
	path = None
	basename = None

	def __init__(self, data):
		parts = data.split(",")
		self.id = parts[0]
		self.name = urllib.parse.unquote(parts[1])
		self.size = int(parts[2])
		self.realfolder = int(parts[3])
		self.uploadtime = int(parts[4])
		self.md5hex = parts[5]

	def __repr__(self):
		return 'File <' + str(self.id) + ', ' + self.name + ', ' + str(self.realfolder) +  ',' + self.path + '>'


class Http:

	def set_folder_paths(self, parent_id, path):
		if parent_id in self.folders:
			for folder in self.folders[parent_id]:
				folder.path = str(path) + '/' + str(folder.name)
				folder.basename = path if (len(str(path)) > 0) else '/';
				self.set_folder_paths(folder.id, folder.path)

	def readdir(self):
		h = http.client.HTTPSConnection("api.rapidshare.com")
		url = "/cgi-bin/rsapi.cgi?sub=listrealfolders&login=%s&password=%s" % (username, password)
		h.request('GET', url)
		response = h.getresponse()
		body = str(response.read(), "utf-8")
		h.close()
		if body.find("ERROR: Login failed. Password incorrect or account not found.") is not -1:
			exit(1)

		self.folders = {}
		lines = body.strip().split("\n")
		for line in lines:
			#folders.append(Folder(line))
			folder = Folder(line)
			if folder.parent_id not in self.folders:
				self.folders[folder.parent_id] = []
			self.folders[folder.parent_id].append(folder);
		self.set_folder_paths(0, '')	
		return self.folders

	def mkdir(self, parent_id, name):
		h = http.client.HTTPSConnection("api.rapidshare.com")
		url = "/cgi-bin/rsapi.cgi?sub=addrealfolder&login=%s&password=%s&name=%s&parent=%d" % (username, password, urllib.parse.quote(name), parent_id)

		h.request('GET', url)
		response = h.getresponse()
		body = str(response.read(), "utf-8")
		h.close()
	
	def rmdir(self, folder_id):
		h = http.client.HTTPSConnection("api.rapidshare.com")
		url = "/cgi-bin/rsapi.cgi?sub=delrealfolder&login=%s&password=%s&realfolder=%d" % (username, password, folder_id)

		h.request('GET', url)
		response = h.getresponse()
		body = str(response.read(), "utf-8")
		h.close()

	def readfiles(self, folder):
		h = http.client.HTTPSConnection("api.rapidshare.com")
		url = "/cgi-bin/rsapi.cgi?sub=listfiles&login=%s&password=%s&realfolder=%d&fields=filename,size,realfolder,uploadtime,md5hex" % (username, password, folder.id)

		h.request('GET', url)
		response = h.getresponse()
		body = str(response.read(), "utf-8")
		h.close()
		if body.strip() == 'NONE':
			return []
		lines = body.strip().split("\n")
		files = []
		for line in lines:
			#folders.append(Folder(line))
			file = File(line)
			file.basename = folder.path
			if file.realfolder == 0:
				file.path = '/' + file.name
			else:
				file.path = folder.path + '/' + file.name
			files.append(file);
		return files 

	def read(self, file, size, offset):
		h = http.client.HTTPSConnection("api.rapidshare.com")
		url = "/cgi-bin/rsapi.cgi?sub=download&login=%s&password=%s&fileid=%s&filename=%s&try=1" % (username, password, file.id, urllib.parse.quote(file.name))

		h.request('GET', url)
		response = h.getresponse()
		body = str(response.read(), "utf-8")
		h.close()
		server = body.strip().split(',')[0].replace('DL:', '')
		
		h = http.client.HTTPSConnection(server)
		if offset == 0:
			url = "/cgi-bin/rsapi.cgi?sub=download&login=%s&password=%s&fileid=%s&filename=%s&start=0-%d" % (username, password, file.id, urllib.parse.quote(file.name), size-1)
		else:
			url = "/cgi-bin/rsapi.cgi?sub=download&login=%s&password=%s&fileid=%s&filename=%s&position=%d-%d" % (username, password, file.id, urllib.parse.quote(file.name), offset, (offset+size-1))

		h.request('GET', url)
		response = h.getresponse()
		body = response.read()
		h.close()
		return body

	def upload(self, file):
		h = http.client.HTTPSConnection("api.rapidshare.com")
		url = "/cgi-bin/rsapi.cgi?sub=nextuploadserver"

		h.request('GET', url)
		response = h.getresponse()
		server_id = int(response.read())
		h.close()
		
		h = http.client.HTTPSConnection('rs%d.rapidshare.com' % (server_id))
		url = "/cgi-bin/rsapi.cgi?uploadid=83702401444"

		BOUNDARY = '----WebKitFormBoundaryhCABiZwpBkjAdGFo'
		CRLF = bytearray("\r\n", 'ascii')

		L = []
		#fields = {'sub': 'upload', 'login':username, 'password':password, 'folder': '0'}
		fields = {'sub': 'upload', 'login':username, 'password': password, 'folder': str(file.folder)}
		for key, value in fields.items():
			L.append(bytearray('--' + BOUNDARY, 'ascii'))
			L.append(bytearray('Content-Disposition: form-data; name="'+ key+'"', 'ascii'))
			L.append(b'')
			L.append(bytearray(value, 'ascii'))
		L.append(bytearray('--' + BOUNDARY, 'ascii'))
		L.append(bytearray('Content-Disposition: form-data; name="filecontent"; filename="' + file.name + '"', 'ascii'))
		L.append(bytearray('Content-Type: application/octet-stream', 'ascii'))
		#L.append(b'Content-Transfer-Encoding: binary')
		L.append(b'')
		L.append(b''.join(file.chunks))
		#L.append(bytearray('test', 'ascii'))
		L.append(bytearray('--' + BOUNDARY + '--', 'ascii'))
		L.append(b'')

		body = CRLF.join(L)

		headers = {
			'content-type': 'multipart/form-data; boundary=' + BOUNDARY,
			'content-length': str(len(body)),
			"Origin": "https://www.rapidshare.com",
			"Referer":"https://www.rapidshare.com/",
			"User-Agent":"Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.17 (KHTML, like Gecko) Chrome/24.0.1312.57 Safari/537.17"
		}
		h.request('POST', url, body, headers)
		#h.request('GET', url)
		response = h.getresponse()
		#@TODO: check for response COMPLETE
		h.close()



class Upload:
	chunks = []
	id = None
	uploadid = None
	name = None
	complete = False
	folder = None
	path = None

	def __init__(self, name, folder_id, path):
		self.name = name
		self.folder = folder_id
		self.path = path
		#self.uploadid = 
	

class Rsfs(Operations, LoggingMixIn):
	"""
	"""

	http = None
	folders = None
	files = None
	uploadfiles = []

	def __init__(self, *args, **kw):
		self.http = Http()
		self.files = {}
		self.loadfolders()

	def loadfolders(self):
		self.folders = self.http.readdir()

	def loadfiles(self, folder):
		self.files[folder.id] = self.http.readfiles(folder)
	
	def getattr(self, path, fh=None):
		now = time()
		folders = [folder.name for fl in self.folders.values() for folder in fl if folder.path == path]

		if len(folders) > 0 or path == '/':
			return dict(st_mode=(S_IFDIR | 0o755), st_ctime=now, st_mtime=now, st_atime=now, st_nlink=2)

		files = [file for fl in self.files.values() for file in fl if file.path == path]

		if len(files) > 0:
			now = files[0].uploadtime
			return dict(st_mode=(S_IFREG | 0o644), st_size=files[0].size, st_ctime=now, st_mtime=now, st_atime=now, st_nlink=1)

		uploadfiles = [file for file in self.uploadfiles if file.path == path]

		if len(uploadfiles) > 0:
			return dict(st_mode=(S_IFREG | 0o644), st_size=0, st_ctime=now, st_mtime=now, st_atime=now, st_nlink=1)

		raise FuseOSError(ENOENT)

	def readdir(self, path, fh):
		parent = [folder for fl in self.folders.values() for folder in fl if folder.path == path]
		files = []
		if len(parent) > 0:
			self.loadfiles(parent[0])
			files = self.files[parent[0].id]
		if path == '/':
			fake_folder = Folder('0,0,')
			fake_folder.path = '/'
			fake_folder.basename = ''
			self.loadfiles(fake_folder)
			files = self.files[0]
		return ['.', '..'] + [folder.name for fl in self.folders.values() for folder in fl if folder.basename == path] + [file.name for file in files]

	def mkdir(self, path, mode):
		parent = [folder for fl in self.folders.values() for folder in fl if folder.path == os.path.dirname(path)]

		if len(parent) == 0:
			raise FuseOSError(ENOENT)
		self.http.mkdir(parent[0].id, os.path.basename(path))
		self.loadfolders()
	
	def rmdir(self, path):
		folder = [folder for fl in self.folders.values() for folder in fl if folder.path == path]
		if len(folder) == 0:
			raise FuseOSError(ENOENT)
		self.http.rmdir(folder[0].id);
		self.loadfolders()

	def open(self, path, flags):
		file = [file.name for fl in self.files.values() for file in fl if file.path == path] 
		if len(file) > 0:
			return 1
		raise FuseOSError(ENOENT)

	def read(self, path, size, offset, fh):
		file = [file for fl in self.files.values() for file in fl if file.path == path] 
		if len(file) > 0:
			pass
		else:
			raise FuseOSError(ENOENT)

		return self.http.read(file[0], size, offset)

	def create(self, path, mode):
		dirname = os.path.dirname(path)
		if dirname == '/':
			file = Upload(os.path.basename(path), 0, path)
		else:	
			folder = [folder for fl in self.folders.values() for folder in fl if folder.path == dirname]
			if len(folder) == 0:
				raise FuseOSError(ENOENT)
			file = Upload(os.path.basename(path), folder[0].id, path)
		self.uploadfiles.append(file)
		return self.uploadfiles.index(file)+1

	def write(self, path, data, offset, fh):
		self.uploadfiles[fh-1].chunks.append(data)
		return len(data)

	def flush(self, path, fh):
		self.http.upload(self.uploadfiles[fh-1])


if __name__ == "__main__":
	if len(argv) != 2:
		print('usage: %s <mountpoint>' % argv[0])
		exit(1)

	username = input("Username: ")
	password = getpass.getpass()

	logging.getLogger().setLevel(logging.DEBUG)
	fuse = FUSE(Rsfs(), argv[1], foreground=True)

