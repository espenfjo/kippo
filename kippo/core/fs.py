# Copyright (c) 2009 Upi Tamminen <desaster@gmail.com>
# See the COPYRIGHT file for more information

import os, time, fnmatch, re, stat
from kippo.core.config import config

A_NAME, \
    A_TYPE, \
    A_UID, \
    A_GID, \
    A_SIZE, \
    A_MODE, \
    A_CTIME, \
    A_CONTENTS, \
    A_TARGET, \
    A_REALFILE = range(0, 10)

T_LINK, \
    T_DIR, \
    T_FILE, \
    T_BLK, \
    T_CHR, \
    T_SOCK, \
    T_FIFO = range(0, 7)

class TooManyLevels(Exception):
    pass

class FileNotFound(Exception):
    pass

class HoneyPotFilesystem(object):
    def __init__(self, fs):
        self.fs = fs

        # keep count of new files, so we can have an artificial limit
        self.newcount = 0 

    def resolve_path(self, path, cwd):
        pieces = path.rstrip('/').split('/')

        if path[0] == '/':
            cwd = []
        else:
            cwd = [x for x in cwd.split('/') if len(x) and x is not None]

        while 1:
            if not len(pieces):
                break
            piece = pieces.pop(0)
            if piece == '..':
                if len(cwd): cwd.pop()
                continue
            if piece in ('.', ''):
                continue
            cwd.append(piece)

        return '/%s' % '/'.join(cwd)

    def resolve_path_wc(self, path, cwd):
        pieces = path.rstrip('/').split('/')
        if len(pieces[0]):
            cwd = [x for x in cwd.split('/') if len(x) and x is not None]
            path = path[1:]
        else:
            cwd, pieces = [], pieces[1:]
        found = []
        def foo(p, cwd):
            if not len(p):
                found.append('/%s' % '/'.join(cwd))
            elif p[0] == '.':
                foo(p[1:], cwd)
            elif p[0] == '..':
                foo(p[1:], cwd[:-1])
            else:
                names = [x[A_NAME] for x in self.get_path('/'.join(cwd))]
                matches = [x for x in names if fnmatch.fnmatchcase(x, p[0])]
                for match in matches:
                    foo(p[1:], cwd + [match])
        foo(pieces, cwd)
        return found

    def get_path(self, path):
        p = self.fs
        for i in path.split('/'):
            if not i:
                continue
            p = [x for x in p[A_CONTENTS] if x[A_NAME] == i][0]
        return p[A_CONTENTS]

    def exists(self, path):
        f = self.getfile(path)
        if f is not False:
            return True

    def update_realfile(self, f, realfile):
        if not f[A_REALFILE] and os.path.exists(realfile) and \
                not os.path.islink(realfile) and os.path.isfile(realfile) and \
                f[A_SIZE] < 25000000:
            print 'Updating realfile to %s' % realfile
            f[A_REALFILE] = realfile

    def realfile(self, f, path):
        self.update_realfile(f, path)
        if f[A_REALFILE]:
            return f[A_REALFILE]
        return None

    def getfile(self, path):
        if path == '/':
            return self.fs
        pieces = path.strip('/').split('/')
        p = self.fs
        while 1:
            if not len(pieces):
                break
            piece = pieces.pop(0)
            if piece not in [x[A_NAME] for x in p[A_CONTENTS]]:
                return False
            p = [x for x in p[A_CONTENTS] \
                if x[A_NAME] == piece][0]
        return p

    def file_contents(self, target, count = 0):
        if count > 10:
            raise TooManyLevels
        path = self.resolve_path(target, os.path.dirname(target))
        print '%s resolved into %s' % (target, path)
        if not path or not self.exists(path):
            raise FileNotFound
        f = self.getfile(path)
        if f[A_TYPE] == T_LINK:
            return self.file_contents(f[A_TARGET], count + 1)

        realfile = self.realfile(f, '%s/%s' % \
            (config().get('honeypot', 'contents_path'), path))
        if realfile:
            return file(realfile, 'rb').read()

    def mkfile(self, path, uid, gid, size, mode, ctime = None):
        if self.newcount > 10000:
            return False
        if ctime is None:
            ctime = time.time()
        dir = self.get_path(os.path.dirname(path))
        outfile = os.path.basename(path)
        if outfile in [x[A_NAME] for x in dir]:
            dir.remove([x for x in dir if x[A_NAME] == outfile][0])
        dir.append([outfile, T_FILE, uid, gid, size, mode, ctime, [],
            None, None])
        self.newcount += 1
        return True

    def mkdir(self, path, uid, gid, size, mode, ctime = None):
        print "mkdir(%s,%s,%s,%s,%s)" % ( path, uid, gid, size, mode )
        if self.newcount > 10000:
            return False
        if ctime is None:
            ctime = time.time()
        if not len(path.strip('/')):
            return False
        try:
            dir = self.get_path(os.path.dirname(path.strip('/')))
        except IndexError:
            return False
        dir.append([os.path.basename(path), T_DIR, uid, gid, size, mode,
            ctime, [], None, None])
        self.newcount += 1
        return True

    def is_dir(self, path):
        if path == '/':
            return True
        dir = self.get_path(os.path.dirname(path))
        l = [x for x in dir
            if x[A_NAME] == os.path.basename(path) and
            x[A_TYPE] == T_DIR]
        if l:
            return True
        return False

    # additions for SFTP support, try to keep functions here similar to os.*

    def open(self, filename, openFlags, mode):
	print "open %s" % filename
	if (openFlags & os.O_RDONLY == os.O_RDONLY):
	    # this should not be called, it'll already be intercepted by readChunk in sftp.py
            print "open rdonly"

	if (openFlags & os.O_WRONLY == os.O_WRONLY):
            safeoutfile = '%s/%s_%s' % \
	       	     (config().get('honeypot', 'download_path'),
	            time.strftime('%Y%m%d%H%M%S'),
	            re.sub('[^A-Za-z0-9]', '_', filename))
            print "open file for writing, saving to %s" % safeoutfile
            # FIXME could have function here to add it to the fake file system as well
            #mkfile(path, uid, gid, size, mode, ctime = None):
            return os.open(safeoutfile, openFlags, mode)

	if (openFlags & os.O_RDWR == os.O_RDWR):
		print "open rdwr"

	if (openFlags & os.O_APPEND == os.O_APPEND):
		print "open append"

	if (openFlags & os.O_CREAT == os.O_CREAT):
		print "open creat"

	if (openFlags & os.O_TRUNC == os.O_TRUNC):
		print "open trunc"

	if (openFlags & os.O_EXCL == os.O_EXCL):
		print "open excl"

	return None

    # FIXME mkdir() name conflicts with existing mkdir
    def mkdir2(self, path):
        if self.exists(path):
            return
        return self.mkdir(path, 0, 0, 4096, 16877) 

    def rmdir(self, path):
	raise notImplementedError

    def utime(self, path, atime, mtime):
        p = self.getfile(path)
        if (p == False):
            return 
        p[A_CTIME] = mtime

    def chmod(self, path, perm):
        p = self.getfile(path)
        if (p == False): 
            return
	p[A_MODE] = stat.S_IFMT(p[A_MODE]) | perm

    def chown(self, path, uid, gid):
        p = self.getfile(path)
        if (p == False):
            return 
        if (uid != -1):
            p[A_UID] = uid
        if (gid != -1):
            p[A_GID] = gid

    def remove(self, filename):
        p = self.getfile(path)
        if (p == False):
            return 

	raise notImplementedError
        # FIXME remove entry & remove from parent contents

    def readlink(self, path):
	raise notImplementedError

    def symlink(self, targetPath, linkPath):
	raise notImplementedError

    def rename(self, oldpath, newpath):
        p = self.getfile(oldpath)
	if (p == False):
            return
	raise notImplementedError
        # FIXME do two things, modify A_NAME and modify the contents of its directory

    def read(self, fd, size):
	# this should not be called, we intercept at readChunk in sftp.py
	raise notImplementedError

    def write(self, fd, string):
	return os.write(fd, string)

    def close(self, fd):
	if (fd == None): 
            return True
	return os.close(fd)

    def lseek(self, fd, offset, whence):
        if (fd == None):
            return True
        return os.lseek(fd, offset, whence)

    # compatibility with os.listdir
    def listdir(self, path):
        names = [x[A_NAME] for x in self.get_path(path)]
	return names

    # our own stat function. need to treat / as exception
    def stat(self, path):

        if (path == "/"):
            p = { A_UID:0, A_GID:0, A_SIZE:4096, A_MODE:16877, A_CTIME:time.time() }
        else:
            p = self.getfile(path)

        return _statobj(
      	 p[A_MODE],
	 0,
	 0,
	 1,
	 p[A_UID],
	 p[A_GID],
	 p[A_SIZE],
	 p[A_CTIME],
	 p[A_CTIME],
	 p[A_CTIME])

    # for now, ignore symlinks
    def lstat(self, path):
	return self.stat(path)

    def realpath(self, path):
        return path

# transform a tuple into a stat object
class _statobj:
    def __init__(self, st_mode, st_ino, st_dev, st_nlink, st_uid, st_gid, st_size, st_atime, st_mtime, st_ctime):
        self.st_mode = st_mode
        self.st_ino = st_ino
        self.st_dev = st_dev
        self.st_nlink = st_nlink
        self.st_uid = st_uid
        self.st_gid = st_gid
        self.st_size = st_size
        self.st_atime = st_atime
        self.st_mtime = st_mtime
        self.st_ctime = st_ctime

# vim: set sw=4 et:
