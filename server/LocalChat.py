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
from flask import request



import sqlite3
import time
import os
import json

app = Flask(__name__)



@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def index(path):
    
    print "%.6f Request start" % (time.time())   # DEBUGONLY
    

    reqdets = {
            'hostname':request.host.lower(),
            'request':path,
            'client_ip':request.remote_addr,
            'client_subnet': False,
            'subnet_mask': False,
            'sourcezone': False,
            'altlocs': False,
            'aliasedlocs': False,
            'prefedge': False,
            'choices': False,
            'newurl': False,
            'complete':False,
            'retcode':0
        }

    a = msghandler.test()
    return json.dumps(a)

    


class MsgHandler(object):

    def test(self):
        return ['foo']




# Create a global instance of the wrapper so that state can be retained
msghandler = MsgHandler()


if __name__ == '__main__':
    # Bind to PORT if defined, otherwise default to 8090.
    port = int(os.environ.get('PORT', 8090))
    app.run(host='0.0.0.0', port=port,debug=True)
