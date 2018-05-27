Server API
============

All requests to the server are placed with the `POST` method, using a JSON request body

The basic structure is

    {
        "action":"[api action]",
        "payload": [json payload]
    }

Which, if successful, will result in a `HTTP 200` and a JSON encapsulated response body.



Response Codes
---------------

The following HTTP statuses may be returned

* `200` - Request was successful
* `400` - Invalid request
* `403` - Authentication Invalid/Permission Denied
* `500` - Server had an issue




Supported Actions
-------------------



### PollMsg

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


If message sending is successful, the response will contain `status:"ok"`




    
    