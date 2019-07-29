"""
   This fill will map to objects returned by the API. The idea is each class will provide
   handy getter methods, but otherwise you can just use a .json property to access the
   raw json passed back by the client.
"""
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import quote_plus

from feedly.api_client.protocol import APIClient
from feedly.api_client.stream import EnterpriseStreamId, STREAM_SOURCE_ENTERPRISE, STREAM_SOURCE_USER, StreamBase, StreamIdBase, StreamOptions, UserStreamId


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

    def tag_entries(self, entry_ids: List[str]):
        self._client.do_api_request(f'/v3/tags/{quote_plus(self["id"])}', method='put',
                                    data={'entryIds': [entry_id for entry_id in entry_ids]})

    def delete_tags(self, options: StreamOptions = None):
        """
        *** WARNING *** Non-reversible operation
        Given a TagBase Streamable, remove tags corresponding to this tag stream, for all articles downloaded
        with options StreamOptions. If User is part of a Team, this will also delete the teammate tags that correspond
        to this board
        :param options: specify high max_count to empty the board.
        :return:
        """
        a_ids = [a["id"] for a in self.stream_contents(options)]
        tag_id = self._get_id()
        while len(a_ids) > 0:
            batch_size = 50  # limitation due to the url length: articles are "de-tagged" by batch of 50.
            to_delete = a_ids[:batch_size]
            a_ids = a_ids[batch_size:]
            self._client.do_api_request(
                f'/v3/tags/{quote_plus(tag_id)}/{",".join([quote_plus(d) for d in to_delete])}', method='DELETE'
            )


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

    def archive(self):
        """
        Once archived, a tag will not be returned in the list of enterprise tags.
        It will not be returned in the list of tag subscriptions.
        """
        self._client.do_api_request('v3/enterprise/tags/'+quote_plus(self.stream_id.id), method='delete')

    def delete(self):
        """
        *** WARNING *** Non-reversible operation
        The tag will be permanently deleted:
        All tagged articles will be untagged, and the tag subscription will be removed from all members subscriptions.
        """
        self._client.do_api_request('v3/enterprise/tags/'+quote_plus(self.stream_id.id)+'?deleteContent=true', method='delete')

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
                self.json['enterpriseName'] = next(iter(self._enterprise_categories.values())).stream_id.source_id

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

    def _get_category_or_tag(self, stream_id:StreamIdBase, cache:Dict[str,Streamable], factory:Callable[[Dict[str,str]], Streamable], auto_create:bool):
        if cache:
            data = cache.get(stream_id.content_id)
            if data:
                return data

            if not auto_create:
                raise ValueError(f'{stream_id.id} does not exist')
            else:
                cache.clear()

        return factory({'id': stream_id.id}, self._client)

    def get_category(self, key:Union[str, UserStreamId]):
        """
        :param key: the id of the category (e.g. "recipes"), or stream ID object
        :return: the category
        """
        if isinstance(key, str):
            id_ = UserStreamId(parts=[STREAM_SOURCE_USER, self.id, 'category', key])
        else:
            id_ = key

        return self._get_category_or_tag(id_, self._categories, UserCategory, False)

    def get_tag(self, key:Union[str, UserStreamId]) -> 'UserTag':
        """
        :param key: the id of the tag (e.g. "recipes"), or stream ID object
        :return: the tag
        """
        if isinstance(key, str):
            id_ = UserStreamId(parts=[STREAM_SOURCE_USER, self.id, 'tag', key])
        else:
            id_ = key

        return self._get_category_or_tag(id_, self._tags, UserTag, True)

    def get_enterprise_category(self, key:Union[str, EnterpriseStreamId]) -> 'EnterpriseCategory':
        """
        :param key: the UUID of the category (dash separated hex numbers), or a stream ID object)
        :return: the enterprise category
        """
        if isinstance(key, str):
            id_ = EnterpriseStreamId(parts=[STREAM_SOURCE_ENTERPRISE, self.enterprise_name, 'category', key])
        else:
            id_ = key

        return self._get_category_or_tag(id_, self._enterprise_categories, EnterpriseCategory, False)

    def get_enterprise_tag(self, key:Union[str, EnterpriseStreamId]) -> 'EnterpriseTag':
        """
        :param key: the UUID of the tag (dash separated hex numbers), or a stream ID object)
        :return: the enterprise tag
        """
        if isinstance(key, str):
            id_ = EnterpriseStreamId(parts=[STREAM_SOURCE_ENTERPRISE, self.enterprise_name, 'tag', key])
        else:
            id_ = key

        return self._get_category_or_tag(id_, self._enterprise_tags, EnterpriseTag, False)

    def create_enterprise_tag(self, data: Dict[str, Any]) -> 'EnterpriseTag':
        """
        :param data: The dictionary with the info for the new tag creation.
        :return: the newly created enterprise tag
        """
        assert "emailSettings" not in data or data["emailSettings"].get("includeFollowers")
        items = self._client.do_api_request('v3/enterprise/tags', method="post", data=data)
        return EnterpriseTag(items[0], self._client)

    def delete_annotations(self, streamable: Streamable, options: StreamOptions = None):
        """
        *** WARNING *** Non-reversible operation
        Given a streamable, remove all annotations made by the user (identified with self['id'])
        :param streamable:
        :param options:
        :return:
        """
        for a in streamable.stream_contents(options):
            if 'annotations' in a.json:
                for annotation in a.json['annotations']:
                    if self['id'] == annotation['author']:
                        self._client.do_api_request(f"v3/annotations/{quote_plus(annotation['id'])}", method='DELETE')

    def delete_tags(self, streamable: Streamable, options: StreamOptions = None):
        """
        *** WARNING *** Non-reversible operation
        Given a streamable, remove all tags made by the user (identified with self['id'])
        :param streamable:
        :param options:
        :return:
        """
        a_ids = []
        for a in streamable.stream_contents(options):
            if 'tags' in a.json:
                for t in a['tags']:
                    if t['label'] == '':
                        continue
                    tag_id = t['id']
                    if tag_id.startswith('enterprise'):
                        tagged_by_user = t.get('addedBy')
                    else:
                        tagged_by_user = tag_id[5:tag_id.find('/', 5)]
                    if tagged_by_user == self['id']:
                        a_ids += [a["id"]]
        while len(a_ids)>0:
            batch_size = 50  # limitation due to the url length: articles are "de-tagged" by batch of 50.
            to_delete = a_ids[:batch_size]
            a_ids = a_ids[batch_size:]
            self._client.do_api_request(
                f'/v3/tags/{quote_plus(tag_id)}/{",".join([quote_plus(d) for d in to_delete])}', method='DELETE')

    def annotate_entry(self, entry_id: str, comment: str, slackMentions=[], emailMentions=[]):
        self._client.do_api_request(f'/v3/annotations', method='post',
                                    data={'comment': comment, 'entryId': entry_id, 'emailMentions': emailMentions,
                                          'slackMentions': slackMentions})
