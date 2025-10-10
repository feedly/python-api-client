import uuid
from abc import ABC, abstractmethod
from csv import DictReader
from datetime import datetime
from enum import Enum
from itertools import chain
from requests import Response
from typing import ClassVar, Dict, Generic, Iterable, List, Optional, TypeVar
from urllib.parse import parse_qs

from feedly.api_client.data import Streamable
from feedly.api_client.session import FeedlySession

T = TypeVar("T")


class IoCFormat(Enum):
    MISP = "misp"
    STIX = "stix2.1"
    CSV = "csv"


class IoCDownloaderABC(ABC, Generic[T]):
    RELATIVE_URL = "/v3/enterprise/ioc"
    FORMAT: ClassVar[str]

    def __init__(
        self,
        session: FeedlySession,
        newer_than: Optional[datetime],
        older_than: Optional[datetime],
        stream_id: str,
        max_batches: Optional[int] = None,
    ):
        """
        Use this class to export the contextualized IoCs from a stream.
        Enterprise/personals feeds/boards are supported (see dedicated methods below).
        The IoCs will be returned along with their context and relationships in a dictionary representing a valid
         STIX v2.1 Bundle object. https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html#_gms872kuzdmg
        Use the newer_than parameter to filter articles that are newer than your last call.
        Use the older_than parameter to filter articles that are older than your last call.
        Use the max_batches parameter to limit the number of batches/pages to retrieve.

        :param session: The authenticated session to use to make the api calls
        :param newer_than: Only articles newer than this parameter will be used. If None only one call will be make,
         and the continuation will be ignored
        :param older_than: Only articles older than this parameter will be used. If None only one call will be make,
         and the continuation will be ignored
        :param max_batches: Maximum number of batches to retrieve. If None, will continue until no more data is available
        """
        self.newer_than = newer_than
        self.older_than = older_than
        self.session = session
        self.stream_id = stream_id
        self.max_batches = max_batches

    def download_all(self) -> List[T]:
        return self._merge(self.stream_bundles())

    def stream_bundles(self) -> Iterable[T]:
        continuation = None
        batch_count = 0
        while True:
            params = {
                "continuation": continuation,
                "streamId": self.stream_id,
                "format": self.FORMAT,
            }
            if self.newer_than:
                params["newerThan"] = int(self.newer_than.timestamp())
            if self.older_than:
                params["olderThan"] = int(self.older_than.timestamp())

            resp = self.session.make_api_request(f"{self.RELATIVE_URL}", params=params)
            yield self._parse_response(resp)
            batch_count += 1

            # Check if we've reached max_batches limit
            if self.max_batches and batch_count >= self.max_batches:
                return

            if not self.newer_than or "link" not in resp.headers:
                return
            next_url = resp.headers["link"][1:].split(">")[0]
            continuation = parse_qs(next_url)["continuation"][0]

    def _parse_response(self, resp: Response) -> T:
        return resp.json()

    @abstractmethod
    def _merge(self, resp_jsons: Iterable[T]) -> T:
        ...


class IoCDownloaderBuilder:
    def __init__(
        self,
        session: FeedlySession,
        format: IoCFormat,
        newer_than: Optional[datetime] = None,
        older_than: Optional[datetime] = None,
        max_batches: Optional[int] = None,
    ):
        """
        Use this class to export the contextualized IoCs from a stream.
        Enterprise/personals feeds/boards are supported (see dedicated methods below).
        The IoCs will be returned along with their context and relationships in a dictionary representing a valid
         STIX v2.1 Bundle object. https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html#_gms872kuzdmg
        Use the newer_than parameter to filter articles that are newer than your last call.
        Use the older_than parameter to filter articles that are older than your last call.
        Use the max_batches parameter to limit the number of batches/pages to retrieve.

        :param session: The authenticated session to use to make the api calls
        :param newer_than: Only articles newer than this parameter will be used. If None only one call will be make,
         and the continuation will be ignored
        :param older_than: Only articles older than this parameter will be used. If None only one call will be make,
         and the continuation will be ignored
        :param max_batches: Maximum number of batches to retrieve. If None, will continue until no more data is available
        """
        self.session = session
        self.format = format
        self.newer_than = newer_than
        self.older_than = older_than
        self.max_batches = max_batches

        self.session.api_host = "https://cloud.feedly.com"
        self.user = self.session.user

    def from_all_enterprise_categories(self) -> IoCDownloaderABC:
        return self.from_stream(self.user.get_all_enterprise_categories_stream())

    def from_all_user_categories(self) -> IoCDownloaderABC:
        return self.from_stream(self.user.get_all_user_categories_stream())

    def from_enterprise_category(self, name_or_id: str) -> IoCDownloaderABC:
        return self.from_stream(self.user.enterprise_categories.get(name_or_id))

    def from_enterprise_tag(self, name_or_id: str) -> IoCDownloaderABC:
        return self.from_stream(self.user.enterprise_tags.get(name_or_id))

    def from_user_category(self, name_or_id: str) -> IoCDownloaderABC:
        return self.from_stream(self.user.user_categories.get(name_or_id))

    def from_stream(self, stream: Streamable) -> IoCDownloaderABC:
        return self.from_stream_id(stream.id)

    def from_stream_id(self, stream_id: str) -> IoCDownloaderABC:
        format2class = {
            IoCFormat.MISP: MispIoCDownloader,
            IoCFormat.STIX: StixIoCDownloader,
            IoCFormat.CSV: CsvIoCDownloader,
        }
        return format2class[self.format](
            session=self.session,
            newer_than=self.newer_than,
            older_than=self.older_than,
            stream_id=stream_id,
            max_batches=self.max_batches,
        )


class StixIoCDownloader(IoCDownloaderABC[Dict]):
    FORMAT = "stix2.1"

    def _merge(self, resp_jsons: List[Dict]) -> Dict:
        return {
            "objects": list(chain.from_iterable(resp_json["objects"] for resp_json in resp_jsons)),
            "id": f"bundle--{str(uuid.uuid4())}",
            "type": "bundle",
        }


class MispIoCDownloader(IoCDownloaderABC[Dict]):
    FORMAT = "misp"

    def _merge(self, resp_jsons: Iterable[Dict]) -> Dict:
        return {"response": list(chain.from_iterable(resp_json["response"] for resp_json in resp_jsons))}


class CsvIoCDownloader(IoCDownloaderABC[List[Dict]]):
    FORMAT = "csv"

    def _merge(self, resp_jsons: Iterable[List[Dict]]) -> List[Dict]:
        return list(chain.from_iterable(resp_jsons))

    def _parse_response(self, resp: Response) -> List[Dict]:
        return list(DictReader(resp.text.splitlines()))