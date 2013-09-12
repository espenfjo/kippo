# TODO copyrights

from time import time, sleep, strftime
from kippo.core.config import config
from threading import Thread
import shlex, subprocess

class PacketCap(Thread):

    captures = {} # dict {'attacker_ip': {'time_out': <timestamp>, 'processhandle': <ph>}}

    def start_capture (self, attacker):
        ph = None
        cfg = config()
        timeout = int(cfg.get('packet_capture', 'timeout'))
        if attacker not in self.captures:
            # add attacker to captures and start capture
            self.captures[attacker] = {'timeout': time() + timeout}
            print "Starting new capture for %s" % (attacker)

            filter = 'tcp and dst port 22 and host %s' % (attacker)
            filename = 'log/pcap/%s-%s.pcap' % (strftime("%Y%m%d%H%M"), attacker)
            # http://www.stev.org/post/2012/01/19/Getting-tcpdump-to-run-as-non-root.aspx
            cmd = "tcpdump -w %s -i %s '%s'" % (filename, 'eth0', filter)
            cmd = shlex.split(cmd)

            # TODO improve exception handling
            try:
                ph = subprocess.Popen(cmd)
            except Exception,e:
                print "exception caught!: ", e
            self.captures[attacker]['processhandle'] = ph
        else:
            # update timeout
            self.captures[attacker]['timeout'] = time() + timeout


    def check_timeouts (self):
        for attacker, info in self.captures.items():
            if info['timeout'] < time():
                print "timeout for %s, removing .." % (attacker)
                info['processhandle'].terminate()
                self.captures.pop(attacker, None)


    def run(self):
        print "PacketCap thread started"
        while True:
            print "in while"
            self.check_timeouts ()
            sleep(2)
