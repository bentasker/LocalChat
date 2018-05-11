#!/usr/bin/env python
#
#
# LocalChat Server Script
#
#
# apt-get install:
#    python-flask
#

from flask import Flask
from flask import request, make_response



import sqlite3
import time
import os
import json

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
    if a in [400]:
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
            owner TEXT NOT NULL,
            pass TEXT NOT NULL
        );
        
        
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY,
            ts INTEGER NOT NULL,
            room INTEGER NOT NULL,
            msg TEXT NOT NULL
        );
        
        
        CREATE TABLE users (
            username TEXT NOT NULL,
            room INTEGER NOT NULL,
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
            return 400
        
        
        # Decrypt the payload
        reqjson['payload'] = self.decrypt(reqjson['payload'])
        
        try:
            reqjson['payload'] = json.loads(reqjson['payload'])
        except:
            return 400
        
        if reqjson['action'] == "createRoom":
            return self.createRoom(reqjson)
        
        elif reqjson['action'] == "inviteUser":
            return self.inviteUser(reqjson)
        
        
        
        
        

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
        print "Creating room %s" % (reqjson['payload'])
        
        # Create a tuple for sqlite3
        t = (reqjson['payload']['roomName'],
             reqjson['payload']['owner'],
             reqjson['payload']['passhash'])
        
        try:
            self.cursor.execute("INSERT INTO rooms (name,owner,pass) VALUES (?,?,?)",t)
            roomid = self.cursor.lastrowid
        except:
            # Probably a duplicate name, but we don't want to give the other end a reason anyway
            return 500
        
        
        self.cursor.execute("INSERT INTO users (username,room) values (?,?)",(reqjson['payload']['owner'],roomid))
        self.conn.commit()
        
        return {
                'status':'ok',
                'roomid': roomid,
                'name' : reqjson['payload']['roomName']
            }
        
    


    def inviteUser(self,reqjson):
        ''' Link a username into a room


        curl -v -X POST http://127.0.0.1:8090/ -H "Content-Type: application/json" --data '{"action":"inviteUser","payload":"{\"roomName\":\"BenTest\",\"user\":\"ben2\"}"}'

        '''
        
        if "roomName" not in reqjson['payload']:
            return 400
        
        room = self.getRoomID(reqjson['payload']["roomName"])
        
        if not room:
            return 400
        
        # Otherwise, link the user in
        self.cursor.execute("INSERT INTO users (username,room) values (?,?)",(reqjson['payload']['user'],room))
        self.conn.commit()
        return {
                "status":'ok'
            }
        
        
    def getRoomID(self,roomname):
        ''' Get a room's ID from its name
        '''
        t = (roomname,)
        self.cursor.execute("SELECT id from rooms where name=?",t)
        r = self.cursor.fetchone()
        
        if not r:
            return False
        
        return r[0]
    


    def test(self):
        return ['foo']




# Create a global instance of the wrapper so that state can be retained
msghandler = MsgHandler()


if __name__ == '__main__':
    # Bind to PORT if defined, otherwise default to 8090.
    port = int(os.environ.get('PORT', 8090))
    app.run(host='0.0.0.0', port=port,debug=True)
