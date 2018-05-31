# LocalChat Server


## About

Localchat is a simple and lightweight chat application. It's primary purpose is to provide a means to have a multi-user Off-The-Record transient chat, minimising the likelihood that anyone but the chat participants has even a record that the chat took place.

It binds to the loopback adapter, and uses ad-hoc SSL to ensure that chat messages aren't available to anyone capable of sniffing loopback traffic. Where clients are remote, there are a number of possible deployment options, see [The main README](../README.md) for more information on these.

The internal database is stored in memory only, to ensure that metadata isn't written to (and therefore recoverable from) disk.

It's intended to be incredibly lightweight, so is provided as a single Python file rather than being broken out into multiple files. Although it can support a reasonable number of active clients, it *is* a single threaded application and isn't designed to support 1000's of active users.




## Dependancies

The following non-standard modules are required

* flask
* urllib2
* sqlite3
* bcrypt
* gnupg



## Usage Instructions

To start the server, simply run it

    ./LocalChat.py
    

## Commandline Arguments

The server takes a limited number of commandline arguments. By default, none are needed.


    ./LocalChat.py [--testing-mode-enable]
    

When `--testing-mode-enable` is present, the internal database is written to disk rather than being kept in memory. This is for testing purposes only, and is outright dangerous for use in production. When this mode is enabled, whenever a user joins a room, `SYSTEM` will push a message to warn the room that messages are being written to disk. Testing mode also changes purge thresholds to a lower number so that the automated cleans will complete in a time more conduicive to testing. *Do Not* use this argument without very, very good reason.





