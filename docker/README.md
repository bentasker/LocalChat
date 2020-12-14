Localchat Docker Images
==========================

Localchat was built into docker images in [LOC-30](https://projects.bentasker.co.uk/jira_projects/browse/LOC-30.html).

The docker imaged client needn't necessarily speak to a docker'd server, and vice versa, locally installed clients can be used to communicate with a docker'd server instance.



### Server

The server can be run by running

    docker run -p 127.0.0.1:8080:8080 bentasker12/localchat:server

This will bind to port 8080 of the loopback on the host machine. If you want to bind to (say) public 443 then run

    docker run -p 443:8080 bentasker12/localchat:server

If you don't want log information printing to stdout, you can daemonize

    docker run -d -p 443:8080 bentasker12/localchat:server


### Client

The client can be run as follows

	docker run -it bentasker12/localchat:client [URL of server]

For example

        ssh -L 8080:127.0.0.1:8080 user@localchatserver
	docker run -it bentasker12/localchat:client https://127.0.0.1:8080



