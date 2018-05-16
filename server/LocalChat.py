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



import sqlite3
import time
import os
import json
import bcrypt
import random
import string

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


    def __init__(self):
        self.conn = False
        self.cursor = False



    def createDB(self):
        ''' Create the in-memory database ready for use 
        '''
        self.conn = sqlite3.connect(':memory:')
        self.cursor = self.conn.cursor()
        
        sql = """ CREATE TABLE rooms (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            owner TEXT NOT NULL
        );
        
        
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            room INTEGER NOT NULL,
            user NOT NULL,
            msg TEXT NOT NULL
        );
        
        
        CREATE TABLE users (
            username TEXT NOT NULL,
            room INTEGER NOT NULL,
            active INTEGER DEFAULT 0,
            passhash TEXT NOT NULL,
            PRIMARY KEY (username,room)
        );
        
        
        CREATE TABLE sessions (
            username TEXT NOT NULL,
            sesskey TEXT NOT NULL,
            PRIMARY KEY(sesskey)
        );
        
        
        CREATE TABLE failuremsgs (
            username TEXT NOT NULL,
            room INTEGER NOT NULL,
            expires INTEGER NOT NULL,
            msg TEXT NOT NULL,
            PRIMARY KEY (username,room)
        );
        
        """
        
        self.conn.executescript(sql)



    def processSubmission(self,reqjson):
        ''' Process an incoming request and route it to
        the correct function
        
        '''
        
        if not self.conn or not self.cursor:
            self.createDB()
        
        
        print reqjson
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
                
        return {"status":"ok","last":last,"session":sesskey}
        
        
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
        
        self.cursor.execute("""SELECT id,msg,ts,user FROM messages
            WHERE room=? AND
            id > ?
            ORDER BY ts ASC           
            """,(room,reqjson['payload']['mylast']))
        
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



    def pushSystemMsg(self,msg,room,verb="sysinfo"):
        ''' Push a message from the SYSTEM user into the queue
        '''
        m = {
            "text":msg,
            "verb":verb
        }
        self.cursor.execute("INSERT INTO messages (ts,room,msg,user) VALUES (?,?,?,'SYSTEM')",(time.time(),room,json.dumps(m)))
        msgid = self.cursor.lastrowid
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
        


    def genSessionKey(self,N=128):
        return ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits).encode('utf-8') for _ in range(N))


    def test(self):
        return ['foo']




# Create a global instance of the wrapper so that state can be retained
msghandler = MsgHandler()


if __name__ == '__main__':
    # Bind to PORT if defined, otherwise default to 8090.
    port = int(os.environ.get('PORT', 8090))
    app.run(host='0.0.0.0', port=port,debug=True,ssl_context='adhoc')
