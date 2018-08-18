"""
   This fill will map to objects returned by the API. The idea is each class will provide
   handy getter methods, but otherwise you can just use a .json property to access the
   raw json passed back by the client.
"""
from typing import Any, Dict, Optional

from feedly.protocol import APIClient
from feedly.stream import STREAM_SOURCE_USER, StreamOptions, StreamBase, UserStreamId


class FeedlyData:
    def __init__(self, json:Dict[str,Any], client:APIClient=None):
        self._json = json
        self._client = client
    def _onchange(self):
        # sub classes should clear any cached items here
        pass

    @property
    def json(self):
        return self._json

    @json.setter
    def json(self, json):
        self._json = json
        self._onchange()

    def __getitem__(self, name):
        return self.json.get(name)

    def __setitem__(self, key, value):
        self.json[key] = value

class IdStream(StreamBase):
    """
    stream entry ids, e.g. https://developers.feedly.com/v3/streams/#get-a-list-of-entry-ids-for-a-specific-stream
    """
    def __init__(self, client:APIClient, id_:str, options:StreamOptions):
        super().__init__(client, id_, options, 'ids', 'ids', lambda x: x)


class ContentStream(StreamBase):
    """
    stream entries, e.g. https://developers.feedly.com/v3/streams/#get-the-content-of-a-stream
    """
    def __init__(self, client:APIClient, id_:str, options:StreamOptions):
        super().__init__(client, id_, options, 'contents', 'items', Entry)


class Streamable(FeedlyData):
    def _get_id(self):
        return self['id']

    def stream_contents(self, options:StreamOptions=None):
        if not options:
            options = StreamOptions()
        return ContentStream(self._client, self._get_id(), options)

    def stream_ids(self, options:StreamOptions=None):
        if not options:
            options = StreamOptions()
        return IdStream(self._client, self._get_id(), options)

    def __repr__(self):
        return f'{type(self).__name__}: {self._get_id()}>'

class UserCategory(Streamable):

    @property
    def stream_id(self):
        return UserStreamId(self.id, self.id.split('/'))


class UserTag(Streamable):

    @property
    def stream_id(self):
        return UserStreamId(self.id, self.id.split('/'))

class Entry(FeedlyData):
    pass


class FeedlyUser(FeedlyData):
    def __init__(self, profile_json:Dict[str, Any], client:APIClient):
        super().__init__(profile_json, client)
        self.categories:Dict[str, 'UserCategory'] = None
        self.tags:Dict[str: 'UserTag'] = None
        self._populated = len(profile_json) > 1

    def __getitem__(self, item):
        if item != 'id':
            self._populate()

        return super().__getitem__(item)

    def _populate(self) -> None:
        if not self._populated:
            self.json = self._client.do_api_request('/v3/profile')
            self._populated = True

    @property
    def id(self) -> str:
        if 'id' not in self.json:
            self._populate()
        return self['id']

    @property
    def email(self) -> Optional[str]:
        self._populate()
        return self['email']

    @property
    def name(self):
        self._populate()
        return self['fullName']

    @property
    def enterprise_name(self):
        self._populate()
        return self['enterpriseName']

    def _onchange(self):
        self.categories = None
        self.tags = None

    def get_categories(self, refresh: bool = False) -> Dict[str, 'UserCategory']:
        if self.categories is None or refresh:
            resp = self._client.do_api_request('/v3/categories')
            categories = [UserCategory(j, self._client) for j in resp]
            self.categories = {c.stream_id.content_id: c for c in categories}

        return self.categories

    def get_tags(self, refresh: bool = False) -> Dict[str, 'UserCategory']:
        if self.tags is None or refresh:
            resp = self._client.do_api_request('/v3/tags')
            tags = [UserTag(j, self._client) for j in resp]
            self.tags = {t.stream_id.content_id: t for t in tags}

        return self.tags

    def get_category(self, name):
        id_ = '/'.join([STREAM_SOURCE_USER, self.id, 'category', name])

        if self.categories:
            data = self.categories.get(name)
            if data:
                return data
            raise ValueError(f'{id_} does not exist')

        return UserCategory({'id': id_}, self._client)

    def get_tag(self, name) -> 'UserTag':
        id_ = '/'.join([STREAM_SOURCE_USER, self.id, 'tag', name])

        if self.tags:
            data = self.tags.get(name)
            if data:
                return data
            raise ValueError(f'{id_} does not exist')

        return UserTag({'id': id_}, self._client)


