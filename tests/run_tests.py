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
import sqlite3
import traceback
import json


try:
    from subprocess import DEVNULL # py3k
except ImportError:
    import os
    DEVNULL = open(os.devnull, 'wb')


DB_FILE = "%s/localchat-testing.db" % (os.getcwd(),)
PARENT_DIR = "%s/.." % (os.path.dirname(os.path.abspath(__file__)),)
sys.path.append('%s/client/' % (PARENT_DIR,))

import LocalChatClient
STORAGE = {}


def restartServer(proc1):
    ''' Start the server component
    
    If already running (i.e. proc1 != False) kill the existing instance
    '''
    
    # If we've already got a process, kill it
    if proc1:
        kill(proc1.pid)
    
    try:
        serverloc = "%s/server/LocalChat.py" % (PARENT_DIR,)
        proc1 = subprocess.Popen([serverloc,'--testing-mode-enable'],stderr=subprocess.STDOUT,stdout=DEVNULL)
    except Exception as e:
        print "Failed to start server"
        print e
        return False
    
    # Give it time to start up
    time.sleep(5)
    return proc1


def getClientInstance():
    ''' Get an instance of the client class
    '''
    return LocalChatClient.msgHandler()


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



def make_table(columns, data):
    """Create an ASCII table and return it as a string.

    Pass a list of strings to use as columns in the table and a list of
    dicts. The strings in 'columns' will be used as the keys to the dicts in
    'data.'


    https://snippets.bentasker.co.uk/page-1705192300-Make-ASCII-Table-Python.html
    """
    # Calculate how wide each cell needs to be
    cell_widths = {}
    for c in columns:
        lens = []
        values = [lens.append(len(str(d.get(c, "")))) for d in data]
        lens.append(len(c))
        lens.sort()
        cell_widths[c] = max(lens)

    # Used for formatting rows of data
    row_template = "|" + " {} |" * len(columns)

    # CONSTRUCT THE TABLE

    # The top row with the column titles
    justified_column_heads = [c.ljust(cell_widths[c]) for c in columns]
    header = row_template.format(*justified_column_heads)
    # The second row contains separators
    sep = "|" + "-" * (len(header) - 2) + "|"
    end = "-" * len(header)
    # Rows of data
    rows = []

    for d in data:
        fields = [str(d.get(c, "")).ljust(cell_widths[c]) for c in columns]
        row = row_template.format(*fields)
        rows.append(row)
    rows.append(end)
    return "\n".join([header, sep] + rows)



def opendb():
    ''' We'll do this and then close after every query to make sure we don't
    inadvertantly lock the DB and force tests to fail.
    
    '''
    CONN = sqlite3.connect(DB_FILE)
    CURSOR = CONN.cursor()

    return [CONN,CURSOR]
    

def run_tests():
    
    # Get an instance of the client
    msg = getClientInstance();
    
    test_results = []
    tests = ['test_one','test_two','test_three','test_four',
             'test_five','test_six']
    x = 1
    for test in tests:
        print "Running %s " % (test,)
        stat,isFatal = globals()[test](msg)
        stat['No'] = x
        test_results.append(stat)
        if isFatal and stat['Result'] == 'FAIL':
            break

        x = x + 1

    return test_results




def test_one(msg):
    ''' Create a room and verify that it gets created
    '''
    
    result = {'Test' : 'Create a Room','Result' : 'FAIL', 'Notes': '' }
    isFatal = True
    # Test 1 - create a room and check it's recorded in the DB
    n = msg.createRoom('TestRoom1','testadmin')
    
    if not n:
        result['Notes'] = 'Empty Response'
        return [result,isFatal]
    
    # The client should have given us two passwords
    if len(n) < 2:
        result['Notes'] = 'Response too small'
        return [result,isFatal]
    
    # Seperate out the return value
    roompass = n[0]
    userpass = n[1] # user specific password    

    STORAGE['room'] = {"name":"TestRoom1",
                       "RoomPass":roompass,
                       "UserPass":userpass,
                       'User':'testadmin'
                       }
    
    
    CONN,CURSOR = opendb()
    
    # Check the DB to ensure the room was actually created
    CURSOR.execute("SELECT * from rooms where name=?",('TestRoom1',))
    r = CURSOR.fetchone()
    CONN.close()
    
    if not r:
        result['Notes'] = 'Room not in DB'
        return [result,isFatal]
    
    result['Result'] = 'Pass'
    return [result,isFatal]




def test_two(msg):
    ''' Try joining the previously created room with invalid credentials
    '''
    
    result = {'Test' : 'Join the room with invalid creds','Result' : 'FAIL', 'Notes': '' }
    isFatal = False
    n = msg.joinRoom(STORAGE['room']['User'],STORAGE['room']['name'],
                     "%s:%s" % (STORAGE['room']['RoomPass'],'BlatantlyWrong'))
    
    if n:
        result['Notes'] = 'Allowed to join with invalid pass'
        return [result,isFatal]
    
    
    # Now try with an invalid username
    result = {'Test' : 'Join the room with invalid creds','Result' : 'FAIL', 'Notes': '' }
    n = msg.joinRoom('AlsoWrong',STORAGE['room']['name'],"%s:%s" % (STORAGE['room']['RoomPass'],'BlatantlyWrong'))
    
    if n:
        result['Notes'] = 'Invalid user Allowed to join'
        return [result,isFatal]
        
    result['Result'] = 'Pass'
    return [result,isFatal]




def test_three(msg):
    ''' Join the previously created room
    '''
    
    result = {'Test' : 'Join the room','Result' : 'FAIL', 'Notes': '' }
    isFatal = True
    n = msg.joinRoom(STORAGE['room']['User'],STORAGE['room']['name'],
                     "%s:%s" % (STORAGE['room']['RoomPass'],STORAGE['room']['UserPass'])
                     )
    
    if not n:
        result['Notes'] = 'Could not join'
        return [result,isFatal]
    
    CONN,CURSOR = opendb()
    
    # Check the DB to ensure we're now active
    CURSOR.execute("SELECT * from users where username=? and active=1",(STORAGE['room']['User'],))
    r = CURSOR.fetchone()
    CONN.close()
    
    if not r:
        result['Notes'] = 'Not Active in DB'
        return [result,isFatal]
    
    # Check we've got a session token
    if not msg.sesskey:
        result['Notes'] = 'No Session Key'
        return [result,isFatal]
        
    # Check the client has recorded what it needs to
    if not msg.room:
        result['Notes'] = 'Client forgot room'
        return [result,isFatal]

    if not msg.user:
        result['Notes'] = 'Client forgot user'
        return [result,isFatal]

    if not msg.roompass:
        result['Notes'] = 'Client forgot roompass'
        return [result,isFatal]

    if not msg.syskey:
        result['Notes'] = 'No SYSTEM key'
        return [result,isFatal]
    
    
    result['Result'] = 'Pass'
    return [result,isFatal]


def test_four(msg):
    ''' When we joined, SYSTEM will have pushed a message. Ensure it's encrypted
    '''
    
    result = {'Test' : 'SYSTEM uses E2E','Result' : 'FAIL', 'Notes': '' }
    isFatal = False


    CONN,CURSOR = opendb()

    CURSOR.execute("SELECT msg FROM messages where user='SYSTEM' ORDER BY ts DESC")
    r = CURSOR.fetchone()
    CONN.close()
    
    if not r:
        result['Notes'] = 'No System Message'
        return [result,isFatal]
    
    
    try:
        json.loads(r[0])
        result['Notes'] = 'System Message not E2E encrypted'
        return [result,isFatal]       
    except:
        # This is a good thing in this case!
        
        # Now try and decrypt the message
        m = msg.decrypt(r[0],'SYSTEM')
        if not m:
            result['Notes'] = 'Could not decrypt'
            return [result,isFatal]     
    
        # Now check we got valid json
        try:
            j = json.loads(m)
            # Finally
            if "text" not in j or "verb" not in j:
                result['Notes'] = 'Not valid msg payload'
                return [result,isFatal]              
            
            # Otherwise, we're good
            result['Result'] = 'Pass'
            return [result,isFatal]
            
        except:
            result['Notes'] = 'Not valid JSON'
            return [result,isFatal]              
    

def test_five(msg):
    ''' Send a message and ensure it's encrypted in the DB
    '''
    
    result = {'Test' : 'Ensure payloads are encrypted','Result' : 'FAIL', 'Notes': '' }
    isFatal = False
    
    msg.sendMsg('Hello World')
    
    CONN,CURSOR = opendb()
    
    CURSOR.execute("SELECT msg FROM messages where user=? ORDER BY ts DESC",(STORAGE['room']['User'],))
    r = CURSOR.fetchone()
    CONN.close()
    
    if not r:
        result['Notes'] = 'Message not recorded'
        return [result,isFatal]
    
    
    try:
        json.loads(r[0])
        result['Notes'] = 'Message not E2E encrypted'
        return [result,isFatal]       
    except:
        # This is a good thing in this case!
        
        # Now try and decrypt the message
        m = msg.decrypt(r[0],STORAGE['room']['User'])
        if not m:
            result['Notes'] = 'Could not decrypt'
            return [result,isFatal]     
    
        # Now check we got valid json
        try:
            j = json.loads(m)
            # Finally
            if "text" not in j or "verb" not in j:
                result['Notes'] = 'Not valid msg payload'
                return [result,isFatal]              
            
            # Otherwise, we're good
            result['Result'] = 'Pass'
            return [result,isFatal]
            
        except:
            result['Notes'] = 'Not valid JSON'
            return [result,isFatal]              
    


def test_six(msg):
    ''' Invite a user
    '''
    result = {'Test' : 'Invite a user','Result' : 'FAIL', 'Notes': '' }
    isFatal = True
    
    n = msg.inviteUser('testuser')
    if not n:
        result['Notes'] = 'Could not invite testuser'
        return [result,isFatal]
    
    if len(n) < 4:
        result['Notes'] = 'Client returned too short response'
        return [result,isFatal]
        
    # Otherwise, we've got details for a new user to be able to join
    #
    # Store them for a later test
    
    STORAGE['testuser'] = {
        'room':n[0],
        'pass':"%s:%s" % (n[1],n[2]),
        'user':n[3]
        }
    
    result['Result'] = "Pass"
    return [result,isFatal]


if __name__ == '__main__':
    # Start the server
    proc1 = restartServer(False)

    if not proc1:
        # Server start failed.
        # abort, abort, abort
        exit(proc1,1)

    
    try:
        # I don't like generic catchall exceptions
        # but, we want to make sure we kill the background
        # process if there is one.
        results = run_tests()
    except Exception as e:
        print traceback.format_exc()
        print e
        exit(proc1,1)
    
    cols = ['No','Test','Result','Notes']
    print make_table(cols,results)
    
    exit(proc1,0)
    
