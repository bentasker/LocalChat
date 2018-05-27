# LocalChat Client


## About

Localchat is a simple and lightweight chat application. It's primary purpose is to provide a means to have a multi-user Off-The-Record transient chat, minimising the likelihood that anyone but the chat participants has even a record that the chat took place.

This client uses basic End To End encryption (currently using PGP as the encryption mechanism), and the server holds encrypted payloads in memory only (to ensure the ciphertext doesn't end up captured on the hosting provider's SAN for a time). 

The default behaviour is a Multi-User Chat (MUC), however direct messaging between participants within a room is also supported.




## Dependancies


`TODO`



## Usage Instructions

Commands are IRC like:

            /help                                                       Print Usage information

            /join [room] [password] [username]                          Join a room
            /leave                                                      Leave current room
            /room create [roomname] [roompass] [admin user]             New room management


            /room invite [user]                                         Invite a user into the current room
            /me [string]                                                Send an 'action' instead of a message
            /msg [user] message                                         Send a direct message to [user]

            Room Admin commands:

            /kick [user]                                                Kick a user out of the room (they can return)
            /ban [user]                                                 Kick a user out and disinvite them (they cannot return)
            /room close [roompass]                                      Kick all users out and close the room


            /exit                                                       Quit the client



## Commandline Arguments

The client takes a limited number of commandline arguments. By default, none are needed, but depending on your deployment methodology, some of the following may be required.


    ./LocalChatClient.py [--verify] [server]
    

When `--verify` is present, SSL certificate verification will be enabled (which means the server must present a certificate trusted by your system and valid for the server's address. By default that's not the case).

If specified, `server` should be the last argument and must be of the format `https://[servername/ip[:port]]/[path]` (port is optional, default is `8090`).

See the main [README](../README.md) for examples of deployments where these flags may be required.
