#!/usr/bin/env python
#
# apt-get install:
#   python-psutil
#
import subprocess
import psutil
import os
import sys
import time


try:
    from subprocess import DEVNULL # py3k
except ImportError:
    import os
    DEVNULL = open(os.devnull, 'wb')



def restartServer(proc1):
    ''' Start the server component
    
    If already running (i.e. proc1 != False) kill the existing instance
    '''
    
    # If we've already got a process, kill it
    if proc1:
        kill(proc1.pid)
    
    try:
        serverloc = "%s/../server/LocalChat.py" % (os.path.dirname(os.path.abspath(__file__)),)
        print serverloc
        proc1 = subprocess.Popen([serverloc,'--testing-mode-enable'],stderr=subprocess.STDOUT,stdout=DEVNULL)
    except Exception as e:
        print "Failed to start server"
        print e
        return False
    
    return proc1


def exit(proc1,code=0):
    ''' Tidy up and exit
    '''
    
    if proc1:
        kill(proc1.pid)
        
    sys.exit(code)


def kill(proc_pid):
    ''' Kill the process and it's children
    
    From https://stackoverflow.com/a/25134985
    
    We use this because proc1.kill() doesn't seem to kill of the child thread of the server, even if shell=True
    '''
    process = psutil.Process(proc_pid)
    for proc in process.children(recursive=True):
        proc.kill()
    process.kill()



if __name__ == '__main__':
    # Start the server
    proc1 = restartServer(False)

    if not proc1:
        # Server start failed.
        # abort, abort, abort
        exit(proc1,1)

    time.sleep(10)
    exit(proc1,0)
    
