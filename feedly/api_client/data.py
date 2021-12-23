"""
   This fill will map to objects returned by the API. The idea is each class will provide
   handy getter methods, but otherwise you can just use a .json property to access the
   raw json passed back by the client.
"""
import re
import warnings
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union
from urllib.parse import quote_plus

from backports.cached_property import cached_property

from feedly.api_client.protocol import APIClient
from feedly.api_client.stream import (
    STREAM_SOURCE_ENTERPRISE,
    STREAM_SOURCE_USER,
    EnterpriseStreamId,
    StreamBase,
    StreamIdBase,
    StreamOptions,
    UserStreamId,
)


class FeedlyData:
    def __init__(self, json: Dict[str, Any], client: APIClient = None):
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

    def __init__(self, client: APIClient, id_: str, options: StreamOptions):
        super().__init__(client, id_, options, "ids", "ids", lambda x: x)


class ContentStream(StreamBase):
    """
    stream entries, e.g. https://developers.feedly.com/v3/streams/#get-the-content-of-a-stream
    """

    def __init__(self, client: APIClient, id_: str, options: StreamOptions):
        super().__init__(client, id_, options, "contents", "items", Entry)


class Streamable(FeedlyData, ABC):
    @property
    def id(self) -> str:
        return self._get_id()

    @property
    @abstractmethod
    def stream_id(self) -> StreamIdBase:
        ...

    def _get_id(self):
        return self["id"]

    def stream_contents(self, options: StreamOptions = None) -> ContentStream:
        if not options:
            options = StreamOptions()
        return ContentStream(self._client, self._get_id(), options)

    def stream_ids(self, options: StreamOptions = None):
        if not options:
            options = StreamOptions()
        return IdStream(self._client, self._get_id(), options)

    def __repr__(self):
        return f"<{type(self).__name__}: {self._get_id()}>"


class TagBase(Streamable):
    def tag_entry(self, entry_id: str):
        self._client.do_api_request(f'/v3/tags/{quote_plus(self["id"])}', method="put", data={"entryId": entry_id})

    def tag_entries(self, entry_ids: List[str]):
        self._client.do_api_request(
            f'/v3/tags/{quote_plus(self["id"])}', method="put", data={"entryIds": [entry_id for entry_id in entry_ids]}
        )

    def untag_entry(self, entry_id: str):
        self.untag_entries([entry_id])

    def untag_entries(self, entry_ids: List[str]):
        # limitation due to the url length: articles are untagged by batch of 50.
        for i in range(0, len(entry_ids), 50):
            self._client.do_api_request(
                f'/v3/tags/{quote_plus(self["id"])}/{",".join([quote_plus(d) for d in entry_ids[i: i+50]])}',
                method="DELETE",
            )

    def untag_all(self, options: StreamOptions = None):
        """
        *** WARNING *** Non-reversible operation
        Given a TagBase Streamable, remove tags corresponding to this tag stream, for all articles downloaded
        with options StreamOptions. If User is part of a Team, this will also delete the teammate tags that correspond
        to this board
        :param options: specify high max_count to empty the board.
        :return:
        """
        a_ids = [a["id"] for a in self.stream_contents(options)]
        self.untag_entries(a_ids)

    def delete_tags(self, options: StreamOptions = None):
        warnings.warn("The delete_tags function is deprecated. Use the untag_all function instead")
        return self.untag_all(options)


class UserCategory(Streamable):
    @property
    def stream_id(self):
        return UserStreamId(self["id"], self["id"].split("/"))


class UserTag(TagBase):
    @property
    def stream_id(self):
        return UserStreamId(self["id"], self["id"].split("/"))


class EnterpriseCategory(Streamable):
    @property
    def stream_id(self):
        return EnterpriseStreamId(self["id"], self["id"].split("/"))


class EnterpriseTag(TagBase):
    @property
    def stream_id(self):
        return EnterpriseStreamId(self["id"], self["id"].split("/"))

    def archive(self):
        """
        Once archived, a tag will not be returned in the list of enterprise tags.
        It will not be returned in the list of tag subscriptions.
        """
        self._client.do_api_request("v3/enterprise/tags/" + quote_plus(self.stream_id.id), method="delete")

    def delete(self):
        """
        *** WARNING *** Non-reversible operation
        The tag will be permanently deleted:
        All tagged articles will be untagged, and the tag subscription will be removed from all members subscriptions.
        """
        self._client.do_api_request(
            "v3/enterprise/tags/" + quote_plus(self.stream_id.id) + "?deleteContent=true", method="delete"
        )


class Entry(FeedlyData):
    pass


StreamableT = TypeVar("StreamableT", bound=Streamable)

UUID_REGEX = re.compile(r"[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}", re.IGNORECASE)


class LazyStreams(Generic[StreamableT]):
    def __init__(
        self, parts: List[str], endpoint: str, factory: Callable[[Dict, APIClient], StreamableT], client: APIClient
    ):
        self.parts = parts
        self.client = client
        self.endpoint = endpoint
        self.factory = factory

        self.populated = False

    @cached_property
    def streams(self) -> List[StreamableT]:
        self.populated = True
        return [self.factory(item, self.client) for item in self.client.do_api_request(self.endpoint)]

    @cached_property
    def id2stream(self) -> Dict[str, StreamableT]:
        return {stream.stream_id.content_id: stream for stream in self.streams}

    @cached_property
    def name2stream(self) -> Dict[str, StreamableT]:
        return {stream["label"]: stream for stream in self.streams}

    def get(self, name_or_id: Union[str, StreamIdBase]) -> StreamableT:
        if isinstance(name_or_id, StreamIdBase):
            assert name_or_id.id.startswith(
                "/".join(self.parts)
            ), f"stream id {name_or_id} must start with streams parts {self.parts}"
            return self.make_stream_from_id(name_or_id.content_id)

        try:
            return self.get_from_id(name_or_id)
        except ValueError:
            return self.get_from_name(name_or_id)

    def get_from_name(self, name: str) -> StreamableT:
        try:
            return self.name2stream[name]
        except KeyError:
            raise ValueError(f"Stream `{name}` not found. Available streams: {list(self.name2stream)}") from None

    def get_from_id(self, id: str) -> StreamableT:
        if UUID_REGEX.match(id):
            return self.make_stream_from_id(id)

        try:
            return self.id2stream[id]
        except KeyError:
            raise ValueError(f"Stream `{id}` not found. Available streams: {list(self.id2stream)}") from None

    def make_stream_from_id(self, uuid: str) -> StreamableT:
        return self.factory({"id": "/".join(self.parts + [uuid])}, self.client)


class FeedlyUser(FeedlyData):
    def __init__(self, profile_json: Dict[str, Any], client: APIClient):
        super().__init__(profile_json, client)
        self._populated = len(profile_json) > 1

    def __getitem__(self, item):
        if item != "id":
            self._populate()

        return super().__getitem__(item)

    def _populate(self) -> None:
        if not self._populated:
            self.json = self._client.do_api_request("/v3/profile")
            self._populated = True

    @property
    def id(self) -> str:
        if "id" not in self.json:
            self._populate()
        return self["id"]

    @property
    def email(self) -> Optional[str]:
        self._populate()
        return self["email"]

    @property
    def name(self):
        self._populate()
        return self["fullName"]

    @property
    def enterprise_name(self):
        self._populate()
        return self["enterpriseName"]

    @cached_property
    def enterprise_categories(self) -> LazyStreams[EnterpriseCategory]:
        return LazyStreams(
            [STREAM_SOURCE_ENTERPRISE, self.enterprise_name, "category"],
            endpoint="/v3/enterprise/collections",
            factory=EnterpriseCategory,
            client=self._client,
        )

    @cached_property
    def enterprise_tags(self) -> LazyStreams[EnterpriseTag]:
        return LazyStreams(
            [STREAM_SOURCE_ENTERPRISE, self.enterprise_name, "tag"],
            endpoint="/v3/enterprise/tags",
            factory=EnterpriseTag,
            client=self._client,
        )

    @cached_property
    def user_categories(self) -> LazyStreams[UserCategory]:
        return LazyStreams(
            [STREAM_SOURCE_USER, self.id, "category"],
            endpoint="/v3/categories",
            factory=UserCategory,
            client=self._client,
        )

    @cached_property
    def user_tags(self) -> LazyStreams[UserTag]:
        return LazyStreams(
            [STREAM_SOURCE_USER, self.id, "tag"], endpoint="/v3/tags", factory=UserTag, client=self._client,
        )

    def get_category(self, key: Union[str, UserStreamId]) -> UserCategory:
        """
        :param key: the name or UUID of the tag (dash separated hex numbers), or a stream ID object
        :return: the category
        """
        return self.user_categories.get(key)

    def get_tag(self, key: Union[str, UserStreamId]) -> UserTag:
        """
        :param key: the name or UUID of the tag (dash separated hex numbers), or a stream ID object
        :return: the tag
        """
        return self.user_tags.get(key)

    def get_enterprise_category(self, key: Union[str, EnterpriseStreamId]) -> EnterpriseCategory:
        """
        :param key: the name or UUID of the tag (dash separated hex numbers), or a stream ID object
        :return: the enterprise category
        """
        return self.enterprise_categories.get(key)

    def get_enterprise_tag(self, key: Union[str, EnterpriseStreamId]) -> EnterpriseTag:
        """
        :param key: the name or UUID of the tag (dash separated hex numbers), or a stream ID object
        :return: the enterprise tag
        """
        return self.enterprise_tags.get(key)

    def get_all_user_categories_stream(self) -> UserCategory:
        """
        :return: the stream containing all the categories followed by the user
        """
        return self.user_categories.make_stream_from_id("global.all")

    def get_all_enterprise_categories_stream(self) -> EnterpriseCategory:
        """
        :return: the stream containing all the categories followed by the enterprise
        """
        return self.enterprise_categories.make_stream_from_id("global.all")

    def get_all_enterprise_tags_stream(self) -> UserTag:
        """
        :return: the stream containing all the tags of the enterprise
        """
        return self.user_tags.make_stream_from_id("global.enterprise")

    def create_enterprise_tag(self, data: Dict[str, Any]) -> EnterpriseTag:
        """
        :param data: The dictionary with the info for the new tag creation.
        :return: the newly created enterprise tag
        """
        assert "emailSettings" not in data or data["emailSettings"].get("includeFollowers")
        items = self._client.do_api_request("v3/enterprise/tags", method="post", data=data)
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
            if "annotations" in a.json:
                for annotation in a.json["annotations"]:
                    if self["id"] == annotation["author"]:
                        self._client.do_api_request(f"v3/annotations/{quote_plus(annotation['id'])}", method="DELETE")

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
            if "tags" in a.json:
                for t in a["tags"]:
                    if t["label"] == "":
                        continue
                    tag_id = t["id"]
                    if tag_id.startswith("enterprise"):
                        tagged_by_user = t.get("addedBy")
                    else:
                        tagged_by_user = tag_id[5 : tag_id.find("/", 5)]
                    if tagged_by_user == self["id"]:
                        a_ids += [a["id"]]
        while len(a_ids) > 0:
            batch_size = 50  # limitation due to the url length: articles are "de-tagged" by batch of 50.
            to_delete = a_ids[:batch_size]
            a_ids = a_ids[batch_size:]
            self._client.do_api_request(
                f'/v3/tags/{quote_plus(tag_id)}/{",".join([quote_plus(d) for d in to_delete])}', method="DELETE"
            )

    def annotate_entry(self, entry_id: str, comment: str, slackMentions=[], emailMentions=[]):
        self._client.do_api_request(
            f"/v3/annotations",
            method="post",
            data={
                "comment": comment,
                "entryId": entry_id,
                "emailMentions": emailMentions,
                "slackMentions": slackMentions,
            },
        )
