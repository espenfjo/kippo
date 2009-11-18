from core.honeypot import HoneyPotCommand
from core.fstypes import *
from twisted.web import client
from twisted.internet import reactor
import stat, time, urlparse, random, re
import config

def tdiff(seconds):
    t = seconds
    days = int(t / (24 * 60 * 60))
    t -= (days * 24 * 60 * 60)
    hours = int(t / (60 * 60))
    t -= (hours * 60 * 60)
    minutes = int(t / 60)
    t -= (minutes * 60)

    s = '%ds' % int(t)
    if minutes >= 1: s = '%dm %s' % (minutes, s)
    if hours >= 1: s = '%dh %s' % (hours, s)
    if days >= 1: s = '%dd %s' % (days, s)
    return s

def sizeof_fmt(num):
    for x in ['bytes','K','M','G','T']:
        if num < 1024.0:
            return "%d%s" % (num, x)
        num /= 1024.0

# Luciano Ramalho @ http://code.activestate.com/recipes/498181/
def splitthousands( s, sep=','):  
    if len(s) <= 3: return s  
    return splitthousands(s[:-3], sep) + sep + s[-3:]

class command_wget(HoneyPotCommand):
    def start(self):
        url = None
        for arg in self.args.split():
            if arg.startswith('-'):
                continue
            url = arg.strip()

        if not url:
            self.writeln('wget: missing URL')
            self.writeln('Usage: wget [OPTION]... [URL]...')
            self.nextLine()
            self.writeln('Try `wget --help\' for more options.')
            self.exit()
            return

        urldata = urlparse.urlparse(url)

        outfile = urldata.path.split('/')[-1]
        if not len(outfile.strip()) or not urldata.path.count('/'):
            outfile = 'index.html'

        # now just dl the file in background...
        fn = '%s_%s' % \
            (time.strftime('%Y%m%d%H%M%S'),
            re.sub('[^A-Za-z0-9]', '_', url))
        self.deferred = self.download(url, outfile, file('%s/%s' % \
            (config.download_path, fn), 'w'))
        if self.deferred:
            self.deferred.addCallback(self.saveurl, fn)
            self.deferred.addErrback(self.error, url)

    def download(self, url, fakeoutfile, outputfile, *args, **kwargs):
        scheme, host, port, path = client._parse(url)
        if scheme == 'https':
            self.writeln('Sorry, SSL not supported in this release')
            return None

        self.writeln('--%s--  %s' % (time.strftime('%Y-%m-%d %T'), url))
        self.writeln('Connecting to %s:%d... connected.' % (host, port))
        self.write('HTTP request sent, awaiting response...')

        factory = HTTPProgressDownloader(
            self, fakeoutfile, url, outputfile, *args, **kwargs)
        reactor.connectTCP(host, port, factory)
        return factory.deferred

    # Dunno how to stop the transfer so let's just make it impossible
    def ctrl_c(self):
        self.writeln('^C')

    def saveurl(self, data, fn):
        print 'File download finished (%s)' % fn
        self.exit()

    def error(self, error, url):
        if hasattr(error, 'getErrorMessage'): # exceptions
            error = error.getErrorMessage()
        print 'wget error', error
        self.writeln('404 Not Found')
        self.writeln('%s ERROR 404: Not Found.' % \
            time.strftime('%Y-%m-%d %T'))
        self.exit()

# from http://code.activestate.com/recipes/525493/
class HTTPProgressDownloader(client.HTTPDownloader):    
    def __init__(self, wget, fakeoutfile, url, outfile, headers=None):
        client.HTTPDownloader.__init__(self, url, outfile, headers=headers)
        self.status = None
        self.wget = wget
        self.fakeoutfile = fakeoutfile
        self.lastupdate = 0
        self.started = time.time()
    
    def noPage(self, reason): # called for non-200 responses
        if self.status == '304':
            client.HTTPDownloader.page(self, '')
        else:
            client.HTTPDownloader.noPage(self, reason)

    def gotHeaders(self, headers):
        if self.status == '200':
            self.wget.writeln('200 OK')
            if headers.has_key('content-length'):
                self.totallength = int(headers['content-length'][0])
            else:
                self.totallength = 0
            if headers.has_key('content-type'):
                self.contenttype = headers['content-type'][0]
            else:
                self.contenttype = 'text/whatever'
            self.currentlength = 0.0

            self.wget.writeln('Length: %d (%s) [%s]' % \
                (self.totallength,
                sizeof_fmt(self.totallength),
                self.contenttype))
            self.wget.writeln('Saving to: `%s' % self.fakeoutfile)
            self.wget.honeypot.terminal.nextLine()

        return client.HTTPDownloader.gotHeaders(self, headers)

    def pagePart(self, data):
        if self.status == '200':
            self.currentlength += len(data)
            if (time.time() - self.lastupdate) < 0.5:
                return
            if self.totallength:
                percent = (self.currentlength/self.totallength)*100
                spercent = "%i%%" % percent
            else:
                spercent = '%dK' % (self.currentlength/1000)
                percent = 0
            self.speed = self.currentlength / (time.time() - self.started)
            eta = (self.totallength - self.currentlength) / self.speed
            # FIXME: output looks bugged (insertmode thing)
            self.wget.write(
                '\r%s [%s] %s %dK/s  eta %s' % \
                (spercent.rjust(3),
                ('%s>' % (int(39.0 / 100.0 * percent) * '=')).ljust(39),
                splitthousands(str(int(self.currentlength))).ljust(12),
                self.speed / 1000,
                tdiff(eta)))
            self.lastupdate = time.time()

        return client.HTTPDownloader.pagePart(self, data)

    def pageEnd(self):
        self.wget.write('\r100%%[%s] %s %dK/s' % \
            ('%s>' % (38 * '='),
            splitthousands(str(int(self.totallength))).ljust(12),
            self.speed / 1000))
        self.wget.honeypot.terminal.nextLine()
        self.wget.honeypot.terminal.nextLine()
        self.wget.writeln(
            '%s (%d KB/s) - `%s\' saved [%d/%d]' % \
            (time.strftime('%Y-%m-%d %T'),
            self.speed / 1000,
            self.fakeoutfile, self.currentlength, self.totallength))
        self.wget.fs.mkfile('%s/%s' % \
            (self.wget.honeypot.cwd, self.fakeoutfile), 0, 0,
            self.totallength, 33188)
        return client.HTTPDownloader.pageEnd(self)

# vim: set sw=4 et:
