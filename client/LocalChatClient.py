#!/usr/bin/env python
#
#
# Interface based upon https://github.com/izderadicka/xmpp-tester/blob/master/commander.py
#
# apt-get install:
#     python-urwid


import urwid
from collections import deque
from threading import Thread
import threading

import json
import urllib2

import datetime as dt


# We'll get these from the commandline later
USER='ben2'
SERVER='http://127.0.0.1:8090'
ROOMNAME='BenTest'


class msgHandler(object):
    
    def __init__(self):
        self.last = 0
        self.user = False
        self.server = SERVER
        self.room = False
    
    
    def pollForMessage(self):
        
        if not self.room:
            # We're not connected to a room
            return False
        
        
        payload = {"roomName": self.room, 
                   "mylast":self.last,
                   "user": self.user
                   }
        
        request = {"action":"pollMsg",
                   "payload": json.dumps(payload)
                   }

        resp = self.sendRequest(request)
        
        if resp == "BROKENLINK":
            return resp
        
        
        if resp['status'] == "unchanged":
            return False
        
        to_print = []
        # Otherwise, process the messages
        for i in resp["messages"]:
            self.last = i[0]
            msgbody = json.loads(self.decrypt(i[1]))
            
            # TODO - We'll need to json decode and extract the sending user's name
            # but not currently including that info in my curl tests. Also means test that part of the next block
            
            color = "green"
            upstruser = msgbody['user'] # Temporary placeholder
            
            if upstruser == self.user:
                # One of our own, change the color
                color = "blue"
            
            elif upstruser == "SYSTEM":
                color = "magenta"
                
            
            ts = dt.datetime.utcfromtimestamp(i[2]).strftime("[%H:%M:%S]")
            
            line = [
                ts, # timestamp
                "%s>" % (upstruser,), # To be replaced later
                msgbody['text']
                ]
            
            to_print.append([color,' '.join(line)])
        
        return to_print
        
        
    def sendMsg(self,line):
        ''' Send a message 
        '''
        
        if not self.room:
            # We're not in a room. Abort
            return False
        
        # Otherwise, build a payload
        
        
        msg = {
            'user': self.user,
            'text': line
            }
        
        payload = {"roomName": self.room, 
                   "msg":self.encrypt(json.dumps(msg)),
                   "user": self.user
                   }
        
        request = {"action":"sendMsg",
                   "payload": json.dumps(payload)
                   }

        resp = self.sendRequest(request)        
        
        if resp['status'] == "ok":
            return True
        
        return False
        


    def joinRoom(self,user,room,passw):
        ''' Join a room
        '''
        
        # TODO - this functionality isn't on the 
        # backend yet, so haven't defined the hashing mechanism etc
        passhash = self.hashpw(passw)
        
        payload = {"roomName": room, 
                   "passhash": passhash,
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
        return True




    def leaveRoom(self):
        ''' Leave the current room
        '''
        if not self.room:
            return False
        
        payload = {"roomName": self.room, 
                   "user": self.user
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
        
        return True
                


    def createRoom(self,room,passw,user=False):
        ''' Create a new room
        '''
        
        if not user and not self.user:
            return False
        
        if not user:
            user = self.user
        
        # Room passwords may well go way at some point, but honour the
        # api structure for now
        passhash = self.hashpw(passw)
        
        payload = {"roomName": room, 
                   "owner": user,
                   "passhash": passhash
                   }
        
        request = {"action":"createRoom",
                   "payload": json.dumps(payload)
                   }        
        
        resp = self.sendRequest(request)

        if resp == "BROKENLINK" or resp['status'] != "ok":
            return False
        
        return resp['name']
    


    def inviteUser(self,room,passw,user):
        ''' Invite a user into a room
        
        #TODO - Authentication
        '''
        
        payload = {"roomName": room, 
                   "user": user,
                   }
        
        request = {"action":"inviteUser",
                   "payload": json.dumps(payload)
                   }    
        
        resp = self.sendRequest(request)

        if resp == "BROKENLINK" or resp['status'] != "ok":
            return False
        
        return True


    def sendRequest(self,data):
        data = json.dumps(data)
        
        try:
            req = urllib2.Request(self.server, data, {'Content-Type': 'application/json'})
            f = urllib2.urlopen(req)
            response = f.read()
            f.close()
            return json.loads(response)
        except:
            return "BROKENLINK"



    def decrypt(self,msg):
        ''' Placeholder
        '''
        return msg
    

    def encrypt(self,msg):
        ''' Placeholder
        '''
        return msg


    def hashpw(self,passw):
        ''' Placeholder
        '''
        return passw



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
            
            if cmd == "join":
                # /join [username] [room] [password]
                
                if len(args) < 3:
                    raise InvalidCommand(line)
                    return
                
                if not msg.joinRoom(args[0],args[1],args[2]):
                    raise UnableTo('join',line)
                return
            
            if cmd == "leave":
                # /leave
                if not msg.leaveRoom():
                    raise UnableTo('leave',line)
                    return
                
                global c
                c.output('Left the room','magenta')
                return
        
            if cmd == "room":
                # /room [create|invite] [roomname] [roompass] [[user]]
                if args[0] == "create":
                    
                    if len(args) < 4:
                        args[3] = False
                    
                    n = msg.createRoom(args[1],args[2],args[3])
                    if not n:
                        raise UnableTo('create room',line)
                        return
                    
                    global c
                    c.output('Created Room %s' %(n))
                    return
                
                elif args[0] == "invite":
                    if len(args) < 4:
                        raise InvalidCommand(line)
                    
                    n = msg.inviteUser(args[1],args[2],args[3])
                    if not n:
                        raise UnableTo('invite user',line)
                        return
                    
                    global c
                    c.output('User %s may now join room %s' %(args[1],args[3]))
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
            res='Type [%s] command_name to get more help about particular command\n' % hc
            res+='Type [%s] to quit program\n' % qc
            cl=[name[3:] for name in dir(self) if name.startswith('do_') and len(name)>3]
            res += 'Available commands: %s' %(' '.join(sorted(cl)))
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
              ('magenta', urwid.DARK_MAGENTA, urwid.BLACK), ]
    
    
    def __init__(self, title, command_caption='Command:  (Tab to switch focus to upper frame, where you can scroll text)', cmd_cb=None, max_size=1000):
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
        
