#!/usr/bin/env python
#
#
# Interface based upon https://github.com/izderadicka/xmpp-tester/blob/master/commander.py
#
# apt-get install:
#     python-urwid
#     python-gnupg


import urwid
from collections import deque
from threading import Thread
import threading

import json
import urllib2
import ssl
import string
import random

import datetime as dt

import gnupg



# We'll get these from the commandline later
USER='ben2'
SERVER='https://127.0.0.1:8090'
ROOMNAME='BenTest'


class msgHandler(object):
    
    def __init__(self):
        self.last = 0
        self.user = False
        self.server = SERVER
        self.room = False
        self.roompass = False
        self.sesskey = False
        self.syskey = False
        self.gpg = gnupg.GPG()
    
    
    def pollForMessage(self):
        
        if not self.room:
            # We're not connected to a room
            return False
        
        
        payload = {"roomName": self.room, 
                   "mylast":self.last,
                   "user": self.user,
                   "sesskey": self.sesskey
                   }
        
        request = {"action":"pollMsg",
                   "payload": json.dumps(payload)
                   }

        resp = self.sendRequest(request)
        
        if resp == "BROKENLINK":
            return resp
        
        
        if resp['status'] == "unchanged":
            return False
        
        
        if resp['status'] == "errmessage":
            # Got an error, we need to stop the poll and then return the text
            self.room = False
            self.roompass = False
            self.sesskey = False
            return [['reversed',resp['text']]]
        
        to_print = []
        # Otherwise, process the messages
        for i in resp["messages"]:
            self.last = i[0]
            upstruser = i[3]
            
            try:
                msgbody = json.loads(self.decrypt(i[1],upstruser))
            except:
                # Means an invalid message was received - LOC-8
                to_print.append(['error','Received message which could not be decrypted'])
                continue
            
            # TODO - We'll need to json decode and extract the sending user's name
            # but not currently including that info in my curl tests. Also means test that part of the next block
            
            color = "green"

            if upstruser == self.user:
                # One of our own, change the color
                color = "blue"
            
            elif upstruser == "SYSTEM":
                color = "magenta"
                if msgbody['verb'] == "sysalert":
                    color = 'reversed'
                elif msgbody['verb'] == 'syswarn':
                    color = 'cyan'
                
            
            ts = dt.datetime.utcfromtimestamp(i[2]).strftime("[%H:%M:%S]")
            
            if msgbody["verb"] == "do":
                color = 'yellow'
                line = [
                    "        ** %s %s **" % (upstruser,msgbody['text'])
                    ]
            else:
                
                if i[4] != "0":
                    color = 'brown'
                    upstruser = 'DM %s' % (upstruser,)
                
                line = [
                    ts, # timestamp
                    "%s>" % (upstruser,), # To be replaced later
                    msgbody['text']
                    ]
            
            to_print.append([color,' '.join(line)])
        
        return to_print
        
        
    def sendMsg(self,line,verb='say'):
        ''' Send a message 
        '''
        
        if not self.room:
            # We're not in a room. Abort
            return False
        
        # Otherwise, build a payload
        
        
        msg = {
            'user': self.user,
            'text': line,
            "verb": verb
            }
        
        payload = {"roomName": self.room, 
                   "msg":self.encrypt(json.dumps(msg)),
                   "user": self.user,
                   "sesskey": self.sesskey
                   }
        
        request = {"action":"sendMsg",
                   "payload": json.dumps(payload)
                   }

        resp = self.sendRequest(request)        
        
        if "status" in resp and resp['status'] == "ok":
            return True
        
        return False
        


    def sendDirectMsg(self,line,user,verb='say'):
        ''' Send a direct message
        '''
        
        if not self.room:
            # We're not in a room. Abort
            return False
        
        # Otherwise, build a payload
        
        msg = {
            'user': self.user,
            'text': line,
            "verb": verb
            }
        
        payload = {"roomName": self.room, 
                   "msg":self.encrypt(json.dumps(msg)), # TODO this should use the user's key
                   "to": user,
                   "user": self.user,
                   "sesskey": self.sesskey
                   }
        
        request = {"action":"sendDirectMsg",
                   "payload": json.dumps(payload)
                   }

        resp = self.sendRequest(request)        
        
        if "status" in resp and resp['status'] == "ok":
            return True
        
        return False




    def joinRoom(self,user,room,passw):
        ''' Join a room
        '''
        
        # We only want to send the user password section of the password
        p = passw.split(":")
        userpass = p[1]
        
        payload = {"roomName": room, 
                   "userpass": userpass.encode('utf-8'),
                   "user": user
                   }
        
        request = {"action":"joinRoom",
                   "payload": json.dumps(payload)
                   }        


        resp = self.sendRequest(request)

        if resp == "BROKENLINK" or resp['status'] != "ok":
            return False
        
        
        self.room = room
        self.user = user
        self.last = resp['last']
        self.roompass = p[0] # The room password is the first section of the password
        self.sesskey = resp['session']
        self.syskey = resp['syskey']
        return True




    def leaveRoom(self):
        ''' Leave the current room
        '''
        if not self.room:
            return False
        
        payload = {"roomName": self.room, 
                   "user": self.user,
                   "sesskey": self.sesskey
                   }
        
        request = {"action":"leaveRoom",
                   "payload": json.dumps(payload)
                   }        


        resp = self.sendRequest(request)

        if resp == "BROKENLINK" or resp['status'] != "ok":
            return False
        
        self.room = False
        self.user = False
        self.last = 0
        self.roompass = False
        self.sesskey = False
        
        return True
                


    def createRoom(self,room,user=False):
        ''' Create a new room
        '''
        
        if not user and not self.user:
            return False
        
        if not user:
            user = self.user


        # Generate a password for the admin
        passw = self.genpassw()
                
        payload = {"roomName": room, 
                   "owner": user,
                   "pass": passw
                   }
        
        request = {"action":"createRoom",
                   "payload": json.dumps(payload)
                   }        
        
        resp = self.sendRequest(request)

        if resp == "BROKENLINK" or resp['status'] != "ok":
            return False
        
        return [resp['name'],passw]
    

    def closeRoom(self):
        if not self.room:
            return False

        payload = {"roomName": self.room, 
                   "user": self.user,
                   "sesskey": self.sesskey
                   }
        
        request = {"action":"closeRoom",
                   "payload": json.dumps(payload)
                   }        

        resp = self.sendRequest(request)
        if resp == "BROKENLINK" or resp['status'] != "ok":
            return False
        
        return True
        
        

    def inviteUser(self,user):
        ''' Invite a user into a room
        
        #TODO - Authentication
        '''
        
        
        # Generate a password for the new user
        passw = self.genpassw()
        
        payload = {"roomName": self.room, 
                   "user": self.user,
                   "invite": user,
                   "pass": passw,
                   "sesskey": self.sesskey
                   }
        
        request = {"action":"inviteUser",
                   "payload": json.dumps(payload)
                   }    
        
        resp = self.sendRequest(request)

        if resp == "BROKENLINK" or resp['status'] != "ok":
            return False
        
        return [self.room,self.roompass,passw,user]



    def kickUser(self,user,ban=False):
        ''' Kick a user out of the room
        '''
        
        action = 'banUser'
        
        if not ban:
            action = 'kickUser'
        
        payload = {"roomName": self.room, 
                   "user": self.user,
                   "kick": user,
                   "sesskey": self.sesskey
                   }
        
        request = {"action":action,
                   "payload": json.dumps(payload)
                   }    
                
        resp = self.sendRequest(request)

        if resp == "BROKENLINK" or resp['status'] != "ok":
            return False
        
        return True

        
        

    def sendRequest(self,data):
        data = json.dumps(data)
        
        try:
            # The cert the other end will be considered invalid
            #
            # Ignore it
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            req = urllib2.Request(self.server, data, {'Content-Type': 'application/json'})
            f = urllib2.urlopen(req,context=ctx)
            response = f.read()
            f.close()
            return json.loads(response)
        except:
            return "BROKENLINK"



    def decrypt(self,msg,sender):
        ''' Placeholder
        '''
                
        try:       
            key = self.roompass
            if sender == "SYSTEM":
                key = self.syskey
                
            return str(self.gpg.decrypt(msg.decode("base64"),passphrase=key))
        
        except:
            return False
        
    

    def encrypt(self,msg):
        ''' Placeholder
        '''
        
        crypted = self.gpg.encrypt(msg,None,passphrase=self.roompass,symmetric="AES256",armor=False)
        return crypted.data.encode('base64')


    def hashpw(self,passw):
        ''' Placeholder
        '''
        return passw


    def genpassw(self,N=16):
        ''' Generate a random string of chars to act as a password
        '''
        
        return ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits).encode('utf-8') for _ in range(N))



class NotInRoom(Exception):
    def __init__(self,cmd):
        Exception.__init__(self,'Message not sent')


class UnableTo(Exception):
    def __init__(self,action,cmd):
        Exception.__init__(self,'Could not %s: %s' % (action,cmd))


class InvalidCommand(Exception):
    def __init__(self,cmd):
        Exception.__init__(self,'Command is invalid: %s' % (cmd,))


class Command(object):
    """ Base class to manage commands in commander
similar to cmd.Cmd in standard library
just extend with do_something  method to handle your commands"""

    def __init__(self,quit_commands=['q','quit','exit'], help_commands=['help','?', 'h']):
        self._quit_cmd=quit_commands
        self._help_cmd=help_commands
        
    def __call__(self,line):
        global msg
        tokens=line.split()
        cmd=tokens[0].lower()
        args=tokens[1:]
        
        if cmd[0] == "/":
            # It's a command
            cmd = cmd[1:]
            
            
            if cmd == "me":
                #/me [string]
                r = msg.sendMsg(' '.join(args),'do')
                if not r:
                    raise NotInRoom(line)
                return

            
            if cmd == "ban":
                # /kick [user]
                
                if len(args) < 1:
                    raise InvalidCommand(line)
                
                
                m = msg.kickUser(args[0],True)
                return
                        
            
            if cmd == "join":
                # /join [room] [password] [username] 
                
                if len(args) < 3:
                    raise InvalidCommand(line)
                    return
                
                if not msg.joinRoom(args[2],args[0],args[1]):
                    raise UnableTo('join',line)
                return
            
            
            if cmd == "kick":
                # /kick [user]
                
                if len(args) < 1:
                    raise InvalidCommand(line)
                
                
                m = msg.kickUser(args[0])
                return
            
            
            if cmd == "leave":
                # /leave
                if not msg.leaveRoom():
                    raise UnableTo('leave',line)
                    return
                
                global c
                c.output('Left the room','magenta')
                return


            if cmd == 'msg':
                # /msg ben Hello ben this is a DM
                line = ' '.join(args[1:])
                r = msg.sendDirectMsg(line,args[0])
                if not r:
                    raise NotInRoom(line)
                
                # Otherwise push a copy of the message to display
                # cos we won't get this one back from pollMsg
                global c
                
                m = "%s DM %s>%s" % (msg.user,args[0],line)
                
                c.output(m,'blue')
                
                return

        
            if cmd == "room":
                
                # /room close [roompass]
                if args[0] == "close":
                    if len(args) < 2:
                        raise InvalidCommand('/room close [pass]')
                    
                    if not msg.closeRoom():
                        raise UnableTo('Close Room','')
                                        
                    return
                
                
                # /room create [roomname] [[user]]
                if args[0] == "create":
                    
                    if len(args) < 3:
                        args[2] = False
                    
                    n = msg.createRoom(args[1],args[2])
                    if not n:
                        raise UnableTo('create room',line)
                        return
                    
                    # Seperate out the return value
                    rm = n[0]
                    up = n[1] # user specific password
                    global c
                    
                    # Generate a room password
                    p = msg.genpassw()
                    c.output('Created Room %s' %(rm))
                    c.output('To join the room, do /join %s %s:%s %s' %(args[1],p,up,args[2]))
                    return
                
                elif args[0] == "invite":
                    if len(args) < 2:
                        raise InvalidCommand(line)
                    
                    n = msg.inviteUser(args[1])
                    if not n:
                        raise UnableTo('invite user',line)
                        return
                    
                    global c
                    c.output('User %s may now join room' %(args[1],))
                    c.output('To join the room, they should do /join %s %s:%s %s' %(n[0],n[1],n[2],n[3]))
                    return                                        
                    

        if cmd in self._quit_cmd:
            return Commander.Exit
        elif cmd in self._help_cmd:
            return self.help(args[0] if args else None)
        elif hasattr(self, 'do_'+cmd):
            return getattr(self, 'do_'+cmd)(*args)
        else:
            # If it's not a command, then we're trying to send a message
            r = msg.sendMsg(line)
            if not r:
                raise NotInRoom(line)
            
        
    def help(self,cmd=None):
        def std_help():
            qc='|'.join(self._quit_cmd)
            hc ='|'.join(self._help_cmd)
            res='Type [%s] to quit program\n' % qc
            res += """Available commands: 
            
            /join [room] [password] [username]                          Join a room
            /leave                                                      Leave current room
            /room create [roomname] [roompass] [admin user]             New room management 
            
            
            /room invite [user]                                         Invite a user into the current room
            /me [string]                                                Send an 'action' instead of a message
            
            Room Admin commands:
            
            /kick [user]                                                Kick a user out of the room (they can return)
            /ban [user]                                                 Kick a user out and disinvite them (they cannot return)
            /room close [roompass]                                      Kick all users out and close the room
            
            Once in a room, to send a message, just type it.
            
            
            """
            return res
        if not cmd:
            return std_help()
        else:
            try:
                fn=getattr(self,'do_'+cmd)
                doc=fn.__doc__
                return doc or 'No documentation available for %s'%cmd
            except AttributeError:
                return std_help()
 
class FocusMixin(object):
    def mouse_event(self, size, event, button, x, y, focus):
        if focus and hasattr(self, '_got_focus') and self._got_focus:
            self._got_focus()
        return super(FocusMixin,self).mouse_event(size, event, button, x, y, focus)    
    
class ListView(FocusMixin, urwid.ListBox):
    def __init__(self, model, got_focus, max_size=None):
        urwid.ListBox.__init__(self,model)
        self._got_focus=got_focus
        self.max_size=max_size
        self._lock=threading.Lock()
        
    def add(self,line):
        with self._lock:
            was_on_end=self.get_focus()[1] == len(self.body)-1
            if self.max_size and len(self.body)>self.max_size:
                del self.body[0]
            self.body.append(urwid.Text(line))
            last=len(self.body)-1
            if was_on_end:
                self.set_focus(last,'above')
        
    

class Input(FocusMixin, urwid.Edit):
    signals=['line_entered']
    def __init__(self, got_focus=None):
        urwid.Edit.__init__(self)
        self.history=deque(maxlen=1000)
        self._history_index=-1
        self._got_focus=got_focus
    
    def keypress(self, size, key):
        if key=='enter':
            line=self.edit_text.strip()
            if line:
                urwid.emit_signal(self,'line_entered', line)
                self.history.append(line)
            self._history_index=len(self.history)
            self.edit_text=u''
        if key=='up':
            
            self._history_index-=1
            if self._history_index< 0:
                self._history_index= 0
            else:
                self.edit_text=self.history[self._history_index]
        if key=='down':
            self._history_index+=1
            if self._history_index>=len(self.history):
                self._history_index=len(self.history) 
                self.edit_text=u''
            else:
                self.edit_text=self.history[self._history_index]
        else:
            urwid.Edit.keypress(self, size, key)
        


class Commander(urwid.Frame):
    """ Simple terminal UI with command input on bottom line and display frame above
similar to chat client etc.
Initialize with your Command instance to execute commands
and the start main loop Commander.loop().
You can also asynchronously output messages with Commander.output('message') """

    class Exit(object):
        pass
    
    PALLETE=[('reversed', urwid.BLACK, urwid.LIGHT_GRAY),
              ('normal', urwid.LIGHT_GRAY, urwid.BLACK),
              ('error', urwid.LIGHT_RED, urwid.BLACK),
              ('green', urwid.DARK_GREEN, urwid.BLACK),
              ('blue', urwid.LIGHT_BLUE, urwid.BLACK),
              ('magenta', urwid.DARK_MAGENTA, urwid.BLACK), 
              ('yellow', urwid.YELLOW, urwid.BLACK), 
              ('cyan', urwid.LIGHT_CYAN, urwid.BLACK), 
              ('brown', urwid.BROWN, urwid.BLACK), 
              
              ]
    
    
    def __init__(self, title, command_caption='Message:  (Tab to switch focus to upper frame, where you can scroll text)', cmd_cb=None, max_size=1000):
        self.header=urwid.Text(title)
        self.model=urwid.SimpleListWalker([])
        self.body=ListView(self.model, lambda: self._update_focus(False), max_size=max_size )
        self.input=Input(lambda: self._update_focus(True))
        foot=urwid.Pile([urwid.AttrMap(urwid.Text(command_caption), 'reversed'),
                        urwid.AttrMap(self.input,'normal')])
        urwid.Frame.__init__(self, 
                             urwid.AttrWrap(self.body, 'normal'),
                             urwid.AttrWrap(self.header, 'reversed'),
                             foot)
        self.set_focus_path(['footer',1])
        self._focus=True
        urwid.connect_signal(self.input,'line_entered',self.on_line_entered)
        self._cmd=cmd_cb
        self._output_styles=[s[0] for s in self.PALLETE]
        self.eloop=None
        
    def loop(self, handle_mouse=False):
        self.eloop=urwid.MainLoop(self, self.PALLETE, handle_mouse=handle_mouse)
        self._eloop_thread=threading.current_thread()
        self.eloop.run()
        
    def on_line_entered(self,line):
        if self._cmd:
            try:
                res = self._cmd(line)
            except Exception,e:
                self.output('Error: %s'%e, 'error')
                return
            if res==Commander.Exit:
                raise urwid.ExitMainLoop()
            elif res:
                self.output(str(res))
        else:
            if line in ('q','quit','exit'):
                raise urwid.ExitMainLoop()
            else:
                self.output(line)
    
    def output(self, line, style=None):
        if style and style in self._output_styles:
                line=(style,line) 
        self.body.add(line)
        #since output could be called asynchronously form other threads we need to refresh screen in these cases
        if self.eloop and self._eloop_thread != threading.current_thread():
            self.eloop.draw_screen()
        
        
    def _update_focus(self, focus):
        self._focus=focus
        
    def switch_focus(self):
        if self._focus:
            self.set_focus('body')
            self._focus=False
        else:
            self.set_focus_path(['footer',1])
            self._focus=True
        
    def keypress(self, size, key):
        if key=='tab':
            self.switch_focus()
        return urwid.Frame.keypress(self, size, key)
        


    
if __name__=='__main__':
    
    
    msg = msgHandler()
    
    
    class TestCmd(Command):
        def do_echo(self, *args):
            '''echo - Just echos all arguments'''
            return ' '.join(args)
        def do_raise(self, *args):
            raise Exception('Some Error')
        
    c=Commander('LocalChat', cmd_cb=TestCmd())
    
    #Test asynch output -  e.g. comming from different thread
    import time
    def run():
        state=1
        while True:
            time.sleep(1)
            
            m = msg.pollForMessage()
            
            if m == "BROKENLINK":
                if state == 1:
                    c.output("Server went away", 'Red')
                    state = 0
                continue
                
            if m:
                state = 1
                for i in m:
                    c.output(i[1], i[0])
                
    t=Thread(target=run)
    t.daemon=True
    t.start()
    
    #start main loop
    c.loop()
        
