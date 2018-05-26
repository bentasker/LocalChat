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

`TODO`
