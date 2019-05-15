# python-api-client
Python client code for the feedly api https://developers.feedly.com/

## Initializing a client
To initialize a client, first you need an access token. To just play around,
login to feedly and go to the [console](http://feedly.com/i/console). Then find 
the `feedlyToken` property. This is your web access token. You can make requests
with this token but it will expire. It's not suitable for building an application,
but will get you going.
 
If you're serious about building an app, you probably want to get a
 [developer token](https://developers.feedly.com/v3/developer/). Check the page for more details.

If we assume you saved the token value in a `access.token` file in your home directory, you can
initalize the client as follows:

```
from pathlib import Path
from feedly.api_client.session import FeedlySession

token = (Path.home() / 'access.token').read_text().strip()
sess = FeedlySession(token)
```
Clients are lightweight -- you can keep a client around for the lifetime of your program,
or you can create a new one when needed. It's a bit more efficient to keep it around. If you
do choose to create clients as needed, you should pass in the user's ID in the constructor, 
otherwise you'll incur a `/v3/profile` request. 

## API Oriented Usage
You can use the `FeedlySession` object to make arbitrary API requests. E.g.:

```
sess.do_api_request('/v3/feeds/feed%2Fhttp%3A%2F%2Fblog.feedly.com%2Ffeed%2F')

------------------

{
  "id": "feed/http://blog.feedly.com/feed/",
  "feedId": "feed/http://blog.feedly.com/feed/",
  "title": "Feedly Blog",
  ...
}
```

## Object Oriented Usage

#### Retrieving Articles
Alternatively, you can use the object oriented code, which facilitates common usage patterns.
E.g. you can list your user categories:
```
sess.user.get_categories()

------------------

{'comics': <UserCategory: user/xxx/category/comics>,
 'econ': <UserCategory: user/xxx/category/econ>,
 'global.must': <UserCategory: user/xxx/category/global.must>,
 'politics': <UserCategory: user/xxx/category/politics>,
}
```
where `xxx` is your actual user ID.

It's not necessary to list categories beforehand, if you know the ones that exist, you can 
get one on the fly:
```
sess.user.get_category('comics'))

------------------

<UserCategory: user/xxx/category/comics>
```

#### Accessing Entries (articles)
If you need to access entries or entry IDs, you can use easily stream them via `stream_contents`
and `stream_ids`, respectively:

```
with FeedlySession(auth_token=token) as sess:
    for eid in sess.user.get_category('politics').stream_ids():
         print(eid)

------------------

Dz51gkBgvGUvFOfTATCYLB2uqVaBIaGGazzxpZh2WL0=_16549c827dd:1645ba:3da9d93
Dz51gkBgvGUvFOfTATCYLB2uqVaBIaGGazzxpZh2WL0=_16549c827dd:1645bb:3da9d93
Z/Hzx8NYfSSE8sweA2v5+4r5h7HC5ALdE2YGYB8MYbQ=_1654a26f3fe:79d9ef9:6f86c10b
...
```

Take note of the `StreamOptions` class. There are important `max_count` and `count`
properties that control streaming. To download all items, something like this could
be done:

```
opts = StreamOptions(max_count=sys.maxsize) # down all items that exist
opts.count = sys.maxsize # download as many items as possible in every API request
with FeedlySession(auth_token=token) as sess:
    for eid in sess.user.get_category('politics').stream_ids(opts):
         print(eid)

```

#### Tagging Existing Entries
```
with FeedlySession(auth_token=token) as sess:
    sess.user.get_tag('politics').tag_entry(eid)
```

## Odds and Ends
Feedly APIs are rate limited. Do not make multiple requests concurrently. You can download
quite a few entries at a time, see the previous section for details. Once you get rate limited,
the client will stop any attempted requests until you have available quota.

To debug things, set the log level to `DEBUG`. This will print log messages on every API request.

### Token Management
The above examples assume the auth (access) token is valid. However these tokens do expire. Instead 
of passing the auth token itself, you can create a `feedly.session.Auth` implementation to refresh
the auth token. A file based implementation is already provided (`FileAuthStore`). Once this is done
the client will automatically try to refresh the auth token if a `401` response is encountered.
