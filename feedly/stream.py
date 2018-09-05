from typing import List
from urllib.parse import quote_plus

import logging

from feedly.protocol import APIClient

STREAM_SOURCE_USER:str = 'user'
STREAM_SOURCE_ENTERPRISE:str = 'enterprise'
STREAM_SOURCE_UNKNOWN:str = 'unk'


class StreamIdBase:
    """
    StreamIds are composed of several parts separated by a /.
    """
    def __init__(self, id_:str, source:str, source_id:str, type_:str, content_id:str):
        """
        :param id_: the full stream id string
        :param source: the source. typically this is "user" or "enterprise"
        :param source_id: the id of the source, e.g. a user ID.
        :param type_: the type of the stream, typically "category" or "tag"
        :param content_id: the content id, for user sourced strings, this is plain text like "gaming". For enterprise streams this is a UUID.
        """
        self.id = id_
        self.source = source
        self.source_id = source_id
        self.type = type_
        self.content_id = content_id

    @property
    def is_user_stream(self):
        return self.source == STREAM_SOURCE_USER

    @property
    def is_enterprise_stream(self):
        return self.source == STREAM_SOURCE_ENTERPRISE

    @staticmethod
    def from_string(self, id_:str):
        parts = id_.split('/')
        if len(parts) < 4:
            raise ValueError(f'invalid id {id_}')

        if id_.startswith(STREAM_SOURCE_USER):
            return UserStreamId(id_, parts)
        elif id_.startswith(STREAM_SOURCE_ENTERPRISE):
            return EnterpriseStreamId(id_)
        else:
            return StreamIdBase(id_, STREAM_SOURCE_UNKNOWN, 'unknown', 'unknown')

    def __repr__(self):
        return f'StreamId: {self.id_}>'

    def __str__(self):
        return self.__repr__()


class UserStreamId(StreamIdBase):
    """
    A user stream. For a user with ID 'abcd', some examples might be:
    user/abcd/category/gaming
    or
    user/abcd/tag/recipes
    """
    def __init__(self, id_:str=None, parts:List[str]=None):
        if id_ is None:
            id_ = '/'.join(parts)
        if parts is None:
            parts = id_.split('/')

        if not id_.startswith(STREAM_SOURCE_USER):
            raise ValueError('not a user stream: ' + id)

        super().__init__(id_, STREAM_SOURCE_USER, parts[1], parts[2], '/'.join(parts[3:]))

    def is_category(self):
        return self.type == 'category'

    def is_tag(self):
        return self.type == 'tag'


class EnterpriseStreamId(StreamIdBase):
    def __init__(self, id_:str=None, parts:List[str]=None):
        """
        An enterprise (team) stream. For a team named 'Acme', some examples might be:
        enterprise/acme/category/bbbbbbbb-3333-4444-1111-aaaaaaaaaaaa
        or
        enterprise/acme/tag/aaaaaaaa-0000-1111-2222-333333333333
        """

        if id_ is None:
            id_ = '/'.join(parts)
        if parts is None:
            parts = id_.split('/')

        if not id_.startswith(STREAM_SOURCE_ENTERPRISE):
            raise ValueError('not an enterprise stream: ' + id)

        super().__init__(id_, STREAM_SOURCE_ENTERPRISE, parts[1], parts[2], parts[3])

    def is_category(self):
        return self.type == 'category'

    def is_tag(self):
        return self.type == 'tag'


class StreamOptions:
    """
    Class of stream options...see https://developers.feedly.com/v3/streams/
    note camel casing...this is on purpose so we can just use the __dict__ of the object
    to produce url parameters
    """
    def __init__(self, max_count:int=100):
        self.count:int = 20
        self.ranked:str = 'newest'
        self.unreadOnly:bool = False
        self.newerThan:int = None
        self._max_count = max_count
        self.continuation:str = None


class StreamBase:
    """ base class of streams. for some logic to call the api"""
    def __init__(self, client:APIClient, id_:str, options:StreamOptions, stream_type:str, items_prop:str, item_factory):
        self._client = client
        self._items_prop = items_prop
        self._item_factory = item_factory
        self.id = id_
        self.options = options
        self.stream_type = stream_type
        self.continuation = ''
        self.buffer = []

    def reset(self):
        self.continuation = ''

    def __iter__(self):
        logging.debug('downloading at most %d articles in chunks of %d', self.options._max_count, self.options.count)

        url = f'/v3/streams/{self.stream_type}?streamId={quote_plus(self.id)}'
        n = 0
        for k,v in self.options.__dict__.items():
            if v is not None and k[0] != '_':
                url += f'&{k}={quote_plus(str(v))}'

        while n < self.options._max_count and (self.continuation is not None or self.buffer):
            while self.buffer:
                i = self.buffer.pop()
                yield self._item_factory(i)
                n += 1
                if n == self.options._max_count:
                    break

            if self.continuation is not None and n < self.options._max_count:
                curl = f'{url}&continuation={quote_plus(self.continuation)}' if self.continuation else url

                logging.debug('url: %s', curl)
                resp = self._client.do_api_request(curl)
                self.continuation = resp.get('continuation')
                if resp and self._items_prop in resp:
                    self.buffer = resp[self._items_prop]
                    logging.debug('%d items (continuation=%s)', len(self.buffer), self.continuation)
