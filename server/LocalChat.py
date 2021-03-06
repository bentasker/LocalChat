#!/usr/bin/env python
#
#
# LocalChat Server Script
#
#
# apt-get install:
#   python-flask
#   python-openssl
#   python-bcrypt
#

from flask import Flask
from flask import request, make_response

import thread
import urllib2
import ssl
import sqlite3
import time
import os
import json
import bcrypt
import random
import string
import gnupg
import sys


app = Flask(__name__)



@app.route('/', defaults={'path': ''},methods=["POST"])
@app.route('/<path:path>',methods=["POST"])
def index(path):
    
    print "%.6f Request start" % (time.time())   # DEBUGONLY
    
    reqdata =  request.get_data()
    
    try:
        reqjson = json.loads(reqdata)
    except:
        return make_response("",400)
    
    a = msghandler.processSubmission(reqjson)

    # Check the status
    if a in [400,403,500]:
        response = make_response("",a)
        return response
        
    return json.dumps(a)


class MsgHandler(object):


    def __init__(self,cronpass,bindpoint,purgeinterval,closethresh,testingmode):
        self.conn = False
        self.cursor = False
        # Generate a key for encryption of SYSTEM messages (LOC-13)
        self.syskey = self.genpassw(16)
        self.gpg = gnupg.GPG()
        self.cronpass = cronpass
        self.bindpoint = bindpoint
        self.purgeInterval = purgeinterval
        self.roomCloseThresh = closethresh
        self.testingMode = testingmode
        
        if self.testingMode:
            print "WARNING - Messages will be written to disk"


    def createDB(self):
        ''' Create the in-memory database ready for use 
        '''
        
        dbpath=':memory:'
        if self.testingMode:
            # LOC-15 - allow DB to written to disk in test mode
            dbpath = "%s/localchat-testing.db" % (os.getcwd(),)
        
        self.conn = sqlite3.connect(dbpath)
        self.cursor = self.conn.cursor()
        
        sql = """
        
        DROP TABLE IF EXISTS rooms;
        CREATE TABLE rooms (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            owner TEXT NOT NULL,
            lastactivity INTEGER DEFAULT 0
        );
        
        DROP TABLE IF EXISTS messages;
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            room INTEGER NOT NULL,
            user NOT NULL,
            touser TEXT DEFAULT '0',
            msg TEXT NOT NULL
        );
        
        DROP TABLE IF EXISTS users;
        CREATE TABLE users (
            username TEXT NOT NULL,
            room INTEGER NOT NULL,
            active INTEGER DEFAULT 0,
            passhash TEXT NOT NULL,
            PRIMARY KEY (username,room)
        );
        
        DROP TABLE IF EXISTS sessions;
        CREATE TABLE sessions (
            username TEXT NOT NULL,
            sesskey TEXT NOT NULL,
            PRIMARY KEY(sesskey)
        );
        
        DROP TABLE IF EXISTS failuremsgs;
        CREATE TABLE failuremsgs (
            username TEXT NOT NULL,
            room INTEGER NOT NULL,
            expires INTEGER NOT NULL,
            msg TEXT NOT NULL,
            PRIMARY KEY (username,room)
        );
        
        """
        
        self.conn.executescript(sql)
        
        # We also need to start the scheduler thread (LOC-6)
        thread.start_new_thread(taskScheduler,(self.cronpass,self.bindpoint))


    def processSubmission(self,reqjson):
        ''' Process an incoming request and route it to
        the correct function
        
        '''
        
        if not self.conn or not self.cursor:
            self.createDB()
        
        
        print reqjson
        
        if "action" in reqjson and reqjson['action'] == 'schedulerTrigger':
            return self.triggerClean(reqjson)
        
        if "action" not in reqjson or "payload" not in reqjson:
            return self.returnFailure(400)
        
        
        # Decrypt the payload
        reqjson['payload'] = self.decrypt(reqjson['payload'])
        
        try:
            reqjson['payload'] = json.loads(reqjson['payload'])
        except:
            return self.returnFailure(400)
        
        if reqjson['action'] == "createRoom":
            return self.createRoom(reqjson)
        
        if reqjson['action'] == "closeRoom":
            return self.closeRoom(reqjson)
        
        elif reqjson['action'] == "joinRoom":
            return self.processjoinRoom(reqjson)
        
        elif reqjson['action'] == "leaveRoom":
            return self.processleaveRoom(reqjson)

        elif reqjson['action'] == "banUser":
            return self.kickUser(reqjson,True)
        
        elif reqjson['action'] == "inviteUser":
            return self.inviteUser(reqjson)
        
        elif reqjson['action'] == "kickUser":
            return self.kickUser(reqjson,False)
        
        elif reqjson['action'] == 'sendDirectMsg':
            return self.sendDirectMsg(reqjson)
        
        elif reqjson['action'] == 'sendMsg':
            return self.sendMsg(reqjson)
        
        elif reqjson['action'] == 'pollMsg':
            return self.fetchMsgs(reqjson)
         

    def decrypt(self,msg):
        ''' This is currently just a placeholder
        Will be updated later
        '''
        return msg


    def createRoom(self,reqjson):
        '''
        
        Payload should contain a JSON object consisting of
        
        roomName
        owner
        passhash
        
        e.g.
        
        curl -v -X POST http://127.0.0.1:8090/ -H "Content-Type: application/json" --data '{"action":"createRoom","payload":"{
        \"roomName\":\"BenTest\",
        \"owner\":\"ben\",
        \"passhash\":\"abcdefg\"        
        }"
        
        }'
        
        '''
        
        # Validate the request
        #
        # All validation snippets will change to this format soon
        required = ['roomName','owner','pass']
        for i in required:
            if i not in reqjson['payload']:
                return self.returnFailure(400)
        
        print "Creating room %s" % (reqjson['payload'])
        
        # Create a tuple for sqlite3
        t = (reqjson['payload']['roomName'],
             reqjson['payload']['owner']
             )
        
        try:
            self.cursor.execute("INSERT INTO rooms (name,owner) VALUES (?,?)",t)
            roomid = self.cursor.lastrowid
        except:
            # Probably a duplicate name, but we don't want to give the other end a reason anyway
            return self.returnFailure(500)
        
        
        # Generate a password hash for the owners password
        passhash = bcrypt.hashpw(reqjson['payload']['pass'].encode('utf-8'),bcrypt.gensalt())
        
        self.cursor.execute("INSERT INTO users (username,room,passhash) values (?,?,?)",(reqjson['payload']['owner'],roomid,passhash))
        self.conn.commit()
        
        return {
                'status':'ok',
                'roomid': roomid,
                'name' : reqjson['payload']['roomName']
            }
        

    def closeRoom(self,reqjson):
        ''' Close a room.
        
        Means we need to
        
        - Ban all the users
        - Scrub the message queue
        - Remove the room record
        '''
        
        if "roomName" not in reqjson['payload'] or "user" not in reqjson['payload']:
            return self.returnFailure(400)
        
        room = self.getRoomID(reqjson['payload']["roomName"])
        
        if not room:
            return self.returnFailure(400)
        
        
        # Check the requesting user is the admin
        self.cursor.execute("SELECT * from rooms where id=? and owner=?",(room,reqjson["payload"]["user"]))
        n = self.cursor.fetchone()
        
        if not n:
            return self.returnFailure(403)
        

        self.pushSystemMsg("Room has been closed. Buh-Bye",room,'syswarn')
                
        self.cursor.execute("DELETE FROM users where room=?",(room,))
        self.cursor.execute("DELETE FROM rooms where id=?",(room,))
        self.cursor.execute("DELETE FROM messages where room=?",(room,))
        self.cursor.execute("DELETE FROM sessions where sesskey like ?", (reqjson['payload']["roomName"] + '-%',))
        
        self.conn.commit()
        
        return { "status" : "ok" }


    def inviteUser(self,reqjson):
        ''' Link a username into a room
        '''
        
        if "roomName" not in reqjson['payload'] or "pass" not in reqjson['payload'] or "invite" not in reqjson['payload']:
            return self.returnFailure(400)
        
        room = self.getRoomID(reqjson['payload']["roomName"])
        
        if not room:
            return self.returnFailure(400)
        
        if not self.validateUser(reqjson['payload']):
            return self.returnFailure(403,reqjson['payload'],room)
        
        
        if reqjson['payload']['invite'] == "SYSTEM":
            # Push a notification into the group
            self.pushSystemMsg("ALERT: User %s tried to invite SYSTEM" % (reqjson['payload']['user']),room,'sysalert')
            return self.returnFailure(403)
       
        
        # Generate a hash of the submitted password
        passhash = bcrypt.hashpw(reqjson['payload']['pass'].encode('utf-8'),bcrypt.gensalt())
        
        # Otherwise, link the user in
        self.cursor.execute("INSERT INTO users (username,room,passhash) values (?,?,?)",(reqjson['payload']['invite'],room,passhash))
        
        # Push a notification into the group
        self.pushSystemMsg("User %s invited %s to the room" % (reqjson['payload']['user'],reqjson['payload']['invite']),room)
        
        return {
                "status":'ok'
            }

    
    def kickUser(self,reqjson,ban=False):
        ''' Kick a user out of room
        
        Default is just to boot them out, but can also remove their authorisation to enter
        '''
        
        if "roomName" not in reqjson['payload'] or "user" not in reqjson['payload'] or "kick" not in reqjson['payload']:
            return self.returnFailure(400)
        
        room = self.getRoomID(reqjson['payload']["roomName"])
        
        if not room:
            return self.returnFailure(400)
        
        
        # Check the requesting user is the admin
        self.cursor.execute("SELECT * from rooms where id=? and owner=?",(room,reqjson["payload"]["user"]))
        n = self.cursor.fetchone()
        
        if not n:
            return self.returnFailure(403)
        
        self.cursor.execute("UPDATE users set active=0 where room=? and username=?",(room,reqjson["payload"]["kick"]))
        
        # Delete their session
        self.cursor.execute("DELETE FROM sessions where username=? and sesskey like ?", (reqjson['payload']['kick'],reqjson['payload']["roomName"] + '-%'))
        
        self.pushSystemMsg("User %s kicked %s from the room" % (reqjson['payload']['user'],reqjson['payload']['kick']),room,'syswarn')
        
        self.pushFailureMessage(reqjson['payload']['kick'],room,'You have been kicked from the room')
        
        
        if ban:
            # If we're banning them, also need to disinvite them
            self.cursor.execute("DELETE from users where room=? and username=?",(room,reqjson["payload"]["kick"]))
            self.pushSystemMsg("User %s banned %s from the room" % (reqjson['payload']['user'],reqjson['payload']['kick']),room,'syswarn')
            
        return { "status" : "ok" }


    def processjoinRoom(self,reqjson):
        ''' Process a request from a user to login to a room
        
        Not yet defined the authentication mechanism to use, so that's a TODO
        '''

        # Check the required information is present
        required = ['roomName','user','userpass']
        for i in required:
            if i not in reqjson['payload']:
                return self.returnFailure(400)
                
        room = self.getRoomID(reqjson['payload']["roomName"])
        
        if not room:
            return self.returnFailure(400)
        
        if reqjson["payload"]["user"] == "SYSTEM":
            return self.returnFailure(403)
        
        # Check whether that user is authorised to connect to that room
        self.cursor.execute("SELECT username, room,passhash from users where username=? and room=?",(reqjson['payload']['user'],room))
        r = self.cursor.fetchone()
        
        if not r:
            return { "status": "NOK" }
        
        # Now we need to verify they've supplied a correct password for that user
        stored = r[2].encode("utf-8")
        if stored != bcrypt.hashpw(reqjson['payload']['userpass'].encode('utf-8'),stored):
            return self.returnFailure(403)
            
        # Tidy older messages away.
        #
        # We do this so that a user who joins can't then send a poll with last:0 to retrieve the full history
        #
        # Basically, anything older than 10 seconds should go. Users who were already present will be able
        # to scroll up and down in their client anyway
        self.tidyMsgs(time.time()-10,room)
        
        # Push a message to the room to note that the user joined
        msgid = self.pushSystemMsg("User %s joined the room" % (reqjson['payload']['user']),room)

        # If we're in testing mode, push a warning so the new user can see it
        if self.testingMode:
            msgid = self.pushSystemMsg("Server is in testing mode. Messages are being written to disk",room,'syswarn')

        # Check the latest message ID for that room
        self.cursor.execute("SELECT id from messages WHERE room=? and id != ? ORDER BY id DESC",(room,msgid))
        r = self.cursor.fetchone()
        
        if not r:
            last = 0
        else:
            last = r[0]
                
        # Mark the user as active in the users table
        self.cursor.execute("UPDATE users set active=1 where username=? and room=?", (reqjson['payload']['user'],room))
        
        # Create a session for the user
        sesskey = "%s-%s" % (reqjson['payload']["roomName"],self.genSessionKey())
        self.cursor.execute("INSERT INTO sessions (username,sesskey) values (?,?)", (reqjson['payload']['user'],sesskey))
        self.conn.commit()
                
        return {"status":"ok","last":last,"session":sesskey,"syskey":self.syskey}


    def processleaveRoom(self,reqjson):
        ''' Process a user's request to leave a room
        '''
        if "roomName" not in reqjson['payload'] or "user" not in reqjson['payload']:
            return self.returnFailure(400)
        
        room = self.getRoomID(reqjson['payload']["roomName"])
        
        if not room:
            return self.returnFailure(400)
        
        # Check the user is actually in the room and authorised
        if not self.validateUser(reqjson['payload']):
            return self.returnFailure(400)
        
        # Mark them as not in the room
        self.cursor.execute("UPDATE users set active=0 where username=? and room=?", (reqjson['payload']['user'],room))
        self.conn.commit()
        
        # Delete their session
        self.cursor.execute("DELETE FROM sessions where username=? and sesskey = ?", (reqjson['payload']['user'],reqjson['payload']["sesskey"]))
        
        # Push a message to the room to note they left
        self.pushSystemMsg("User %s left the room" % (reqjson['payload']['user']),room)
        return {"status":"ok"}


    def sendMsg(self,reqjson):
        ''' Push a message into a room
        
        curl -v -X POST http://127.0.0.1:8090/ -H "Content-Type: application/json" --data '{"action":"sendMsg","payload":"{\"roomName\":\"BenTest\", \"msg\":\"ENCRYPTED-DATA\",\"user\":\"ben2\"}"}'
        
        '''
        
        if not self.validateUser(reqjson['payload']):
            return self.returnFailure(403)
        
        if "roomName" not in reqjson['payload'] or "msg" not in reqjson['payload']:
            return self.returnFailure(400)
        
        room = self.getRoomID(reqjson['payload']["roomName"])
        print room
        if not room:
            return self.returnFailure(400)
        
        self.cursor.execute("INSERT INTO messages (ts,room,msg,user) VALUES (?,?,?,?)",(time.time(),room,reqjson['payload']['msg'],reqjson['payload']['user']))
        msgid = self.cursor.lastrowid
        self.conn.commit()
        
        # Check the latest message ID for that room
        self.cursor.execute("SELECT id from messages WHERE room=? and id != ? ORDER BY id DESC",(room,msgid))
        r = self.cursor.fetchone()
        
        if not r:
            last = 0
        else:
            last = r[0]
        
        # Update the last activity field in the DB
        # See LOC-11
        self.cursor.execute("UPDATE rooms set lastactivity=? where id=?",(time.time(),room))
        self.conn.commit()
        
        return {
                "status" : "ok",
                "msgid" : msgid,
                "last" : last
            }


    def sendDirectMsg(self,reqjson):
        ''' Push a message to a user in the same room
        '''
        
        if not self.validateUser(reqjson['payload']):
            return self.returnFailure(403)
                
        required = ['roomName','msg','to']
        for i in required:
            if i not in reqjson['payload']:
                return self.returnFailure(400)
        
        room = self.getRoomID(reqjson['payload']["roomName"])
        print room
        if not room:
            return self.returnFailure(400)

        # Check the other user is in the room and active
        self.cursor.execute("SELECT username from users where username=? and room=? and active=1",(reqjson['payload']['to'],room))
        r = self.cursor.fetchone()
        
        if not r:
            return self.returnFailure(400)
            
        self.cursor.execute("INSERT INTO messages (ts,room,msg,user,touser) VALUES (?,?,?,?,?)",(time.time(),room,reqjson['payload']['msg'],reqjson['payload']['user'],reqjson['payload']['to']))
        msgid = self.cursor.lastrowid
        self.conn.commit()
        
        # Update the last activity field in the DB
        # See LOC-11
        self.cursor.execute("UPDATE rooms set lastactivity=? where id=?",(time.time(),room))
        self.conn.commit()        
        
        # Check the latest message ID for that room
        self.cursor.execute("SELECT id from messages WHERE room=? and id != ? ORDER BY id DESC",(room,msgid))
        r = self.cursor.fetchone()
        
        if not r:
            last = 0
        else:
            last = r[0]
        
        return {
                "status" : "ok",
                "msgid" : msgid,
                "last" : last
            }


    def fetchMsgs(self,reqjson):
        ''' Check to see if there are any new messages in the room
        
        curl -v -X POST http://127.0.0.1:8090/ -H "Content-Type: application/json" --data '{"action":"pollMsg","payload":"{\"roomName\":\"BenTest\", \"mylast\":1,\"user\":\"ben2\"}"}'
        
        '''

        if "mylast" not in reqjson['payload']:
            return self.returnFailure(400)
        
        room = self.getRoomID(reqjson['payload']["roomName"])
        print room
        if not room:
            return self.returnFailure(400)

        if not self.validateUser(reqjson['payload']):
            return self.returnFailure(403,reqjson['payload'],room)
        
        self.cursor.execute("""SELECT id,msg,ts,user,touser FROM messages
            WHERE room=? AND
            (touser = 0 OR touser = ?) AND 
            id > ?
            ORDER BY ts ASC           
            """,(room,reqjson['payload']['user'],reqjson['payload']['mylast']))
        
        r = self.cursor.fetchall()
        
        if not r:
            # No changes
            return {"status":"unchanged","last":reqjson['payload']['mylast']}
        
        # Otherwise, return the messages
        return {"status":"updated",
                "messages" : r
                }


    def validateUser(self,payload):
        ''' Placeholder for now. Auth will be handled in more depth later
        '''
        if "user" not in payload or "roomName" not in payload:
            return False
        
        # Validate the session information
        self.cursor.execute("SELECT username from sessions where username=? and sesskey=?",(payload['user'],payload['sesskey']))
        r = self.cursor.fetchone();
        
        if not r:
            return False
        
        room = self.getRoomID(payload["roomName"])
        if not room:
            return False        
        
        # Check whether the user has been marked as active
        self.cursor.execute("SELECT username, room from users where username=? and room=? and active=1",(payload['user'],room))
        r = self.cursor.fetchone()
        
        if not r:
            return False
        
        return True


    def getRoomID(self,roomname):
        ''' Get a room's ID from its name
        '''
        t = (roomname,)
        self.cursor.execute("SELECT id from rooms where name=?",t)
        r = self.cursor.fetchone()
        
        if not r:
            return False
        
        return r[0]


    def triggerClean(self,reqjson):
        ''' Trigger a clean of old messages etc
        '''
        
        if 'pass' not in reqjson:
            # No need for failure messages here
            return 403
        
        if reqjson['pass'] != self.cronpass:
            return 403
        
        # Tidy messages older than 10 minutes
        self.tidyMsgs(time.time() - self.purgeInterval);
        
        # Auto-close any rooms beyond the threshold
        self.autoCloseRooms()
        
        return {'status':'ok'}


    def tidyMsgs(self,thresholdtime,room=False):
        ''' Remove messages older than the threshold time
        '''

        if room:
            # Tidy from a specific room
            self.cursor.execute("DELETE FROM messages where ts < ? and room = ?",(thresholdtime,room))
            self.conn.commit()
            
        else:
            self.cursor.execute("DELETE FROM messages where ts < ?",(thresholdtime,))
            self.conn.commit()

        # Tidy away any failure messages
        self.cursor.execute("DELETE FROM failuremsgs  where expires < ?",(time.time(),))


    def autoCloseRooms(self):
        ''' Automatically close any rooms that have been sat idle for too long
        '''
        
        self.cursor.execute("SELECT id,name from rooms where lastactivity < ? and lastactivity > 0",(time.time() - self.roomCloseThresh,))
        rooms = self.cursor.fetchall()
        
        # Messages probably have been auto-purged, but make sure
        for r in rooms:
            self.cursor.execute("DELETE FROM messages where room=?",(r[0],))
            self.cursor.execute("DELETE FROM failuremsgs where room=?",(r[0],))
            self.cursor.execute("DELETE FROM users where room=?",(r[0],))
            self.cursor.execute("DELETE FROM sessions where sesskey like ?", (r[1] + '-%',))
            self.cursor.execute("DELETE FROM rooms where id=?",(r[0],))
            self.conn.commit()


    def pushSystemMsg(self,msg,room,verb="sysinfo"):
        ''' Push a message from the SYSTEM user into the queue
        '''
        m = {
            "text":msg,
            "verb":verb
        }
        
        m = self.encryptSysMsg(json.dumps(m))
        
        self.cursor.execute("INSERT INTO messages (ts,room,msg,user) VALUES (?,?,?,'SYSTEM')",(time.time(),room,m))
        msgid = self.cursor.lastrowid
        
        # Update the last activity field in the DB
        # See LOC-11
        self.cursor.execute("UPDATE rooms set lastactivity=? where id=?",(time.time(),room))
        
        self.conn.commit()
        return msgid


    def pushFailureMessage(self,user,room,msg):
        ''' Record a failure message against a user
        
        See LOC-14
        
        '''
        self.cursor.execute("INSERT INTO failuremsgs (username,room,expires,msg) values (?,?,?,?)",(user,room,time.time() + 300,msg))
        self.conn.commit()


    def returnFailure(self,status,reqjson=False,room=False):
        ''' For whatever reason, a request isn't being actioned. We need to return a status code
        
        However, in some instances, we may allow a HTTP 200 just once in order to send the user
        information on why their next request will fail 
        '''
        
        # TODO - implement the failure handling stuff
        
        if reqjson and room:
            # Check whether there's a failure message or not 
            self.cursor.execute("SELECT msg from failuremsgs where username=? and room=?",(reqjson['user'],room))
            r = self.cursor.fetchone()
            
            if not r:
                # No message to return
                return status
            
            # Otherwise, return the message and remove it
            self.cursor.execute("DELETE from failuremsgs where username=? and room=?",(reqjson['user'],room))
            self.conn.commit()
            return {"status":"errmessage","text":r[0]}
        
        return status


    def encryptSysMsg(self,msg):
        ''' Encrypt a message from system - LOC-13
        
            This isn't so much for protection of the data in memory (as the key is also in memory) as it
            is to protect against a couple of things you could otherwise do in the client. See LOC-13 for
            more info.
        
        '''

        crypted = self.gpg.encrypt(msg,None,passphrase=self.syskey,symmetric="AES256",armor=False,encrypt=False)
        return crypted.data.encode('base64')


    def genSessionKey(self,N=48):
        return ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits + '/=?&@#%^()+,.<>:!').encode('utf-8') for _ in range(N))


    def genpassw(self,N=16):
        ''' Generate a random string of chars to act as an encryption password
        '''
        
        return ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits).encode('utf-8') for _ in range(N))


# Create the scheduler function
def taskScheduler(passw,bindpoint):
    
    # Ignore cert errors
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    data = json.dumps({"action":'schedulerTrigger',
            "pass": passw
            })
    
    while True:
        time.sleep(60)
        
        try:
            req = urllib2.Request(bindpoint, data, {'Content-Type': 'application/json'})
            f = urllib2.urlopen(req,context=ctx)
            response = f.read()
            f.close()  
        except:
            # Don't let the thread abort just because one request went wrong
            continue


if __name__ == '__main__':
    passw = ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits).encode('utf-8') for _ in range(64))
    bindpoint = "https://127.0.0.1:8090" 
    purgeinterval = 600 # Wipe messages older than 10 mins
    closethresh = 3600 * 6 # Auto-close rooms after 6 hours of inactivity
    
    # LOC-15
    testingmode = False
    if '--testing-mode-enable' in sys.argv:
        testingmode = True
        purgeinterval = 30
        closethresh = 180
    
    # Create a global instance of the wrapper so that state can be retained
    #
    # We pass in the password we generated for the scheduler thread to use
    # as well as the URL it should POST to
    msghandler = MsgHandler(passw,bindpoint,purgeinterval,closethresh,testingmode)

    # Bind to PORT if defined, otherwise default to 8090.
    #
    # This will likely become a CLI argument later
    port = int(os.environ.get('PORT', 8090))
    app.run(host='127.0.0.1', port=port,ssl_context='adhoc',threaded=False)
