# LocalChat


## About

Localchat is a simple and lightweight chat application. It's primary purpose is to provide a means to have a multi-user Off-The-Record transient chat, minimising the likelihood that anyone but the chat participants has even a record that the chat took place.

It is not designed to be exposed to the internet at large. Instead, the primary intended means of use is to deploy it onto a new system (such as an EC2 instance), have user's SSH tunnel in (or use other supported methods) to use it and then discard the system once that chat has completed.

In other words, it's not designed as a generic chat application, but as one to be used for clandestine chats that are hard to monitor/intercept.

The provided client uses basic End To End encryption (currently using PGP as the encryption mechanism), and the server holds encrypted payloads in memory only (to ensure the ciphertext doesn't end up captured on the hosting provider's SAN for a time). Message payloads are purged after a short interval to help reduce the potential exposure were someone to be monitoring the server's memory.

The default behaviour is a Multi-User Chat (MUC), however direct messaging between participants within a room is also supported.


## Project Management

Planned features, bugfixes etc can all be viewed at [project.bentasker.co.uk](https://projects.bentasker.co.uk/jira_projects/browse/LOC.html). Release notes are at [bentasker.co.uk](https://www.bentasker.co.uk/documentation/release-notes/91-localchat)






## Dependancies

### Server

See [server/README.md](server/README.md)


### Client

See [client/README.md](client/README.md)





## Deployment Options

LocalChat is not designed to be publicly accessible and discoverable. It's been written to be relatively light-weight for ease of deployment (and subsequent destruction).

Under no circumstances should you configure it to bind to `0.0.0.0` as doing so would allow adversaries to not only discover it, but to start probing it in order to try and establish whether it's in use (and who's using it). There should *always* be some additional step (i.e. being able to SSH into a server, or knowing exactly where to find it) required before access is available.

Over time, it will likely be hardened further, but it's unlikely it will ever be considered safe for completely unrestricted access - allowing discoverability would allow adversaries to establish likely meeting places in advance.

### Docker

It's possible to [run the client and the server software in docker](docker/README.md). This greatly simplifies some of the client dependencies.


### Direct Communication

The most simple deployment method is to run the server component somewhere, and then simply run the client on the same system. The problem with this is it means that the E2E encryption keys are in memory on the same system as the server.

    ./server/LocalChat.py
    ./client/LocalChatClient.py


So, it's recommended that you run the client on a seperate system and use a SSH tunnel to allow communication

    user@server1 $ ./server/LocalChat.py

    remuser@mymachine $ ssh -L 8090:127.0.0.1:8090 user@server1
    remuser@mymachine $ ./client/LocalChatClient.py

This ensures that anyone able to observe memory on the server cannot see the E2E keys.

As a variation of this, if you do not want the server component to appear on the server's filesystem (you will still need to install dependancies though) then you can also create a reverse tunnel back to another machine. Just be aware that if the connection drops, the server will be unavailable, so ensure you've a reliable connection


    user@server2 $ ./server/LocalChat.py
    user@server2 $ ssh -R 127.0.0.1:8090:127.0.0.1:8090 user@server1

    remuser@mymachine $ ssh -L 8090:127.0.0.1:8090 user@server1
    remuser@mymachine $ ./client/LocalChatClient.py
    

    
### Proxied Communications

It may be that you decide it's better to "hide" the server within an existing website, so that chat connections are mixed in with traffic to that site.

To do this, you simply need to proxy a path on that website back to the server. So you may have an existing Nginx server block like this:

    server {
            listen 443;

            root /usr/share/nginx/example.com/;
            index index.html;

            server_name example.com;

            ssl                  on;
            ssl_certificate      /etc/pki/tls/certs/example.com.crt;
            ssl_certificate_key  /etc/pki/tls/private/example.com.key;

            ssl_session_timeout  5m;

            location / {
                try_files $uri $uri/ =404;
            }

    }

You'd then add a `location` statement with a hard to guess path to handle the chat client

    server {
            listen 443;

            root /usr/share/nginx/example.com/;
            index index.html;

            server_name example.com;

            ssl                  on;
            ssl_certificate      /etc/pki/tls/certs/example.com.crt;
            ssl_certificate_key  /etc/pki/tls/private/example.com.key;

            ssl_session_timeout  5m;

            location / {
                try_files $uri $uri/ =404;
            }
            
            
            location /SM9vbtNrnZ0d6WQa1ByLjZEX/ {
                proxy_pass https://127.0.0.1:8090/;
            }        

    }

And make the server component available on that port (either by running directly, or using a SSH reverse tunnel as described above).

Assuming `example.com` serves a publicly signed and trusted certificate (you'd hope it does), we'll also want to re-enable cert verification. So the client is called with verification enabled and being passed the URL to use for requests

    ./client/LocalChatClient.py --verify https://example.com/SM9vbtNrnZ0d6WQa1ByLjZEX/
 
Later versions will implement the ability to include auth headers in the request so that you can 404 unauthorised requests to the 'hidden' path. Until then, unless there's a particularly strong reason not to, the SSH methods described above are the recommended routes of access.




## Copyright

LocalChat is Copyright (C) 2018 B Tasker. All Rights Reserved. 

Released Under GNU GPL V2 License, see LICENSE.





