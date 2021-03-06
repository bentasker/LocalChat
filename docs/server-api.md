Server API
============

All requests to the server are placed with the `POST` method, using a JSON request body

The basic structure is

    {
        "action":"[api action]",
        "payload": [json payload]
    }

Which, if successful, will result in a `HTTP 200` and a JSON encapsulated response body.

----

Response Codes
---------------

The following HTTP statuses may be returned

* `200` - Request was successful
* `400` - Invalid request
* `403` - Authentication Invalid/Permission Denied
* `500` - Server had an issue

----

Authentication
---------------

Authentication is performed on a per-room basis, so certain calls (such as `createRoom`) are currently entirely unauthenticated (a form of auth may be introduced for those later).

User's are required to authenticate themselves (via password) when they attempt to enter a room with a `joinRoom` call. If that call is successful then a session key will be provided in the response. This must be embedded into every payload (as attribute `sesskey`) after that.

The server uses `bcrypt` for storing authentication credentials.

----

Supported Actions
-------------------


### banUser

Can only be called by the room admin, kicks a user out of the room, and does not allow them to return (unless re-invited)

    {
        "action":"banUser",
        "payload": {    
                    "roomName": "[name of room]",
                    "user": user,
                    "kick": [user to kick],
                    "sesskey": sessionkey
        }
    }

*Response*

If successful, the value of `status` will be `ok` and the kicked user's session will be terminated and their user record removed. A message will be pushed to the room by `SYSTEM` to note that that user has been kicked and banned.

If the requesting user lacks the privileges to kick a user, `SYSTEM` will push a message to warn that `user` tried to ban `tokick`.

----

### closeRoom

This can only be successfully called by the room's owner. `closeRoom` will close the current room, remove all associated messages, sessions and user accounts.


    {
        "action":"closeRoom",
        "payload": {    
                    "roomName": "[name of room]",
                    "user": user,
                    "sesskey": sessionkey
        }
    }

*Response*

If successful, the value of `status` will be `ok`.

Rooms should always be closed when they are no longer required. The server will (by default) automatically close inactive rooms after a period, but this is intended as a safety net (in case the admin gets disconnected and cannot reconnect for some reason).

----

### createRoom

This is used to create a room. Calls are currently unauthenticated because user accounts are tied to a room rather than existing in a global namespace (this is done to limit the risk of a list of possible users sitting on the server until they're likely to be needed).

    {
        "action":"createRoom",
        "payload": {    
                    "roomName": "[name of room]",
                    "owner": [name of user],
                    "pass": password
        }
    }

When creating a room, we specify the username of the user who will be the room owner/admin, and the password they will use to join the room. In the background this will set up the requisite user account.


*Response*

If the room is successfully created, the value of `status` will be `ok`. The roomname will also be confirmed back as the attribute `name`.

The user will then need to call `joinRoom` in order to enter the room (the client could do this automatically, but the current client version does not).

----

### inviteUser

Used to invite a user into the current room. Can be called by admin's and users alike (`SYSTEM` will push a message into the room to notify others of the invite)

    {
        "action":"inviteUser",
        "payload": {    
                    "roomName": "[name of room]",
                    "user": user,
                    "invite": [user to invite],
                    "pass": [new users pass]
                    "sesskey": sessionkey
        }
    }

When inviting a user, we need to specify their username as `invite` and their authentication password as `pass`

*Response*

If successful, the value of `status` will be `ok`. `SYSTEM` will also push a message into the room that `user` invited `invite`

----

### joinRoom

Used to enter a room.

When the user was invited to the room, a password will have been set for them (the supplied client currently auto-generates that password), it will need to be provided for the user to authenticate.

    {
        "action":"joinRoom",
        "payload": {    
                    "roomName": "[name of room]",
                    "userpass": password,
                    "user": user
        }
    }

*Response*

If authentication is successful, the response will include a number of details that the client will need to take note of for future requests

    {
        "status": "ok",
        "last": last,
        "session": sessionkey,
        "syskey": systemkey
    }
    
The value `last` is the ID of the latest message in the room you've just joined. It should be included in `pollMsg` calls.

The value `sessionkey` is a server generated sessionkey. It must be included in the payload of all future requests (it's used to help authenticate those requests).

The value `syskey` is a decryption passphrase. The server's internal user `SYSTEM` will E2E encrypt any messages it pushes into rooms, this is the key you should use to decrypt those messages.

----

### kickUser

Can only be called by the room admin, kicks a user out of the room (but allows them to return). Useful where you think a user's session has hung (for example)

    {
        "action":"kickUser",
        "payload": {    
                    "roomName": "[name of room]",
                    "user": user,
                    "kick": [user to kick],
                    "sesskey": sessionkey
        }
    }

*Response*

If successful, the value of `status` will be `ok` and the kicked user's session will be terminated. A message will be pushed to the room by `SYSTEM` to note that that user has been kicked.

If the requesting user lacks the privileges to kick a user, `SYSTEM` will push a message to warn that `user` tried to kick `tokick`.

----

### leaveRoom

Used to leave the current room

    {
        "action":"leaveRoom",
        "payload": {    
                    "roomName": "[name of room]",
                    "user": user,
                    "sesskey": sessionkey
        }
    }

*Response*

If successful, the value of `status` will be `ok`. Client's should then disable any automated message polling they are running.

----

### pollMsg

Used to check whether there are any messages since the last the client received. It will return room-wide messages and direct messages addressed to the polling user.

Client provides the ID of the last message they've received, as well as the room they're polling. Where this is the first request, `last` should be 0

    {
        "action":"pollMsg",
        "payload": {    
                    "roomName": "[name of room]",
                    "mylast": "[last]",
                    "user": user,
                    "sesskey": sessionkey
        }
    }


*Response*

If there are no messages, then the response status will be `unchanged`.
If a specific error is being returned, the response status will be `errmessage` - you should disable any automatic polling and the print the content of `text`

If status is `updated` then messages have been returned:

    {
        "status": "updated",
        "messages" : [
                        [msgid,msgtext,timestamp,fromuser,touser],
                        [msgid,msgtext,timestamp,fromuser,touser]    
        ]

    }

Once the client has processed the received messages, the value of `last` in the next `pollMsg` request should be the maximum ID in the resultset.

----

### sendDirectMsg

Used to send a message to a specific user within the room. The message will not be visible to other room occupants.

    {
        "action":"sendDirectMsg",
        "payload": {    
                    "roomName": "[name of room]",
                    "msg": "[message payload]",
                    "to": recipient
                    "user": user,
                    "sesskey": sessionkey
        }
    }

The message payload is encrypted and base64 encoded by the client, so the server only sees a base64 string. 

However, to keep compatability with the supplied client, your message payload (prior to encryption) should be a JSON encapsulated string of the format

        msg = {
            'user': user,
            'text': msg,
            "verb": verb
            }

This should then be PGP encrypted using the room passphrase, and then base64 encoded for embedding into the API payload.
            
Where `verb` is one of `do` or `say` (other values will be treated as `say` by the supplied client).


*Response*

If message sending is successful, the response will contain `status:"ok"`

----

### sendMsg

Used to send a message to the entire room

    {
        "action":"sendMsg",
        "payload": {    
                    "roomName": "[name of room]",
                    "msg": "[message payload]",
                    "user": user,
                    "sesskey": sessionkey
        }
    }

The message payload is encrypted and base64 encoded by the client, so the server only sees a base64 string. 

However, to keep compatability with the supplied client, your message payload (prior to encryption) should be a JSON encapsulated string of the format

        msg = {
            'user': user,
            'text': msg,
            "verb": verb
            }

This should then be PGP encrypted using the room passphrase, and then base64 encoded for embedding into the API payload.
            
Where `verb` is one of `do` or `say` (other values will be treated as `say` by the supplied client).


*Response*

If message sending is successful, the response will contain `status:"ok"`


----




    
    