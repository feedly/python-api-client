"""
   This fill will map to objects returned by the API. The idea is each class will provide
   handy getter methods, but otherwise you can just use a .json property to access the
   raw json passed back by the client.
"""
from typing import Any, Dict, Optional
from urllib.parse import quote_plus

from feedly.protocol import APIClient
from feedly.stream import STREAM_SOURCE_USER, StreamOptions, StreamBase, UserStreamId, EnterpriseStreamId, StreamIdBase, STREAM_SOURCE_ENTERPRISE


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
        return f'<{type(self).__name__}: {self._get_id()}>'

class TagBase(Streamable):

    def tag_entry(self, entry_id:str):
        self._client.do_api_request(f'/v3/tags/{quote_plus(self["id"])}', method='put', data={'entryId': entry_id})

class UserCategory(Streamable):

    @property
    def stream_id(self):
        return UserStreamId(self['id'], self['id'].split('/'))


class UserTag(TagBase):

    @property
    def stream_id(self):
        return UserStreamId(self['id'], self['id'].split('/'))

class EnterpriseCategory(Streamable):

    @property
    def stream_id(self):
        return EnterpriseStreamId(self['id'], self['id'].split('/'))


class EnterpriseTag(TagBase):

    @property
    def stream_id(self):
        return EnterpriseStreamId(self['id'], self['id'].split('/'))

class Entry(FeedlyData):
    pass


class FeedlyUser(FeedlyData):
    def __init__(self, profile_json:Dict[str, Any], client:APIClient):
        super().__init__(profile_json, client)
        self._categories:Dict[str, 'UserCategory'] = None
        self._enterprise_categories:Dict[str, 'EnterpriseCategory'] = None
        self._tags: Dict[str: 'UserTag'] = None
        self._enterprise_tags: Dict[str: 'EnterpriseTag'] = None
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
        self._categories = None
        self._tags = None

    def _get_categories_or_tags(self, endpoint, factory):
        rv = {}
        resp = self._client.do_api_request(endpoint)
        for item in resp:
            item = factory(item, self._client)
            rv[item.stream_id.content_id] = item

        return rv

    def get_categories(self, refresh: bool = False) -> Dict[str, 'UserCategory']:
        if self._categories is None or refresh:
            self._categories = self._get_categories_or_tags('/v3/categories', UserCategory)

        return self._categories

    def get_enterprise_categories(self, refresh: bool = False) -> Dict[str, 'EnterpriseCategory']:
        if self._enterprise_categories is None or refresh:
            self._enterprise_categories = self._get_categories_or_tags('/v3/enterprise/collections', EnterpriseCategory)
            if self._enterprise_categories:
                self.json['enterpriseName'] = next(iter(self._enterprise_categories.values())).stream_id.source

        return self._enterprise_categories

    def get_tags(self, refresh: bool = False) -> Dict[str, 'UserTag']:
        if self._tags is None or refresh:
            self._tags = self._get_categories_or_tags('/v3/tags', UserTag)

        return self._tags

    def get_enterprise_tags(self, refresh: bool = False) -> Dict[str, 'EnterpriseTag']:
        if self._enterprise_tags is None or refresh:
            self._enterprise_tags = self._get_categories_or_tags('/v3/enterprise/tags', EnterpriseTag)
            if self._enterprise_tags:
                self.json['enterpriseName'] = next(iter(self._enterprise_tags.values())).stream_id.source

        return self._enterprise_tags

    def _get_category_or_tag(self, stream_id:StreamIdBase, cache, factory):
        if cache:
            data = cache.get(stream_id.content_id)
            if data:
                return data
            raise ValueError(f'{id_} does not exist')

        return factory({'id': stream_id.id}, self._client)

    def get_category(self, name:str):
        id_ = UserStreamId(parts=[STREAM_SOURCE_USER, self.id, 'category', name])

        return self._get_category_or_tag(id_, self._categories, UserCategory)

    def get_tag(self, name:str) -> 'UserTag':
        id_ = UserStreamId(parts=[STREAM_SOURCE_USER, self.id, 'tag', name])

        return self._get_category_or_tag(id_, self._tags, UserTag)

    def get_enterprise_category(self, stream_id:EnterpriseStreamId) -> 'EnterpriseCategory':
        return self._get_category_or_tag(stream_id, self._tags, EnterpriseCategory)

    def get_enterprise_tag(self, stream_id:EnterpriseStreamId) -> 'EnterpriseTag':
        return self._get_category_or_tag(stream_id, self._tags, EnterpriseTag)



