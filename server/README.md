# LocalChat Server


## About

Localchat is a simple and lightweight chat application. It's primary purpose is to provide a means to have a multi-user Off-The-Record transient chat, minimising the likelihood that anyone but the chat participants has even a record that the chat took place.

`TODO`



## Dependancies


`TODO`



## Usage Instructions

`TODO`




## Commandline Arguments

The server takes a limited number of commandline arguments. By default, none are needed.


    ./LocalChat.py [--testing-mode-enable]
    

When `--testing-mode-enable` is present, the internal database is written to disk rather than being kept in memory. This is for testing purposes only, and is outright dangerous for use in production. When this mode is enabled, whenever a user joins a room, `SYSTEM` will push a message to warn the room that messages are being written to disk. Testing mode also changes purge thresholds to a lower number so that the automated cleans will complete in a time more conduicive to testing. *Do Not* use this argument without very, very good reason.





