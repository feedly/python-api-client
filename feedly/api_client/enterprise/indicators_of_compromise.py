import uuid
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import parse_qs

from feedly.api_client.data import Streamable
from feedly.api_client.session import FeedlySession


class IoCDownloader:
    RELATIVE_URL = "/v3/enterprise/ioc"

    def __init__(self, session: FeedlySession, newer_than: Optional[datetime] = None):
        """
        Use this class to export the contextualized IoCs from a stream.
        Enterprise/personals feeds/boards are supported (see dedicated methods below).
        The IoCs will be returned along with their context and relationships in a dictionary representing a valid
         STIX v2.1 Bundle object. https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html#_gms872kuzdmg
        Use the newer_than parameter to filter articles that are newer than your last call.

        :param session: The authenticated session to use to make the api calls
        :param newer_than: Only articles newer than this parameter will be used. If None only one call will be make,
         and the continuation will be ignored
        """
        self.newer_than = newer_than
        self.session = session
        self.session.api_host = "https://cloud.feedly.com"
        self.user = self.session.user

    def from_all_enterprise_categories(self) -> Dict:
        return self.from_stream(self.user.get_all_enterprise_categories_stream())

    def from_all_user_categories(self) -> Dict:
        return self.from_stream(self.user.get_all_user_categories_stream())

    def from_enterprise_category(self, name_or_id: str) -> Dict:
        return self.from_stream(self.user.enterprise_categories.get(name_or_id))

    def from_enterprise_tag(self, name_or_id: str) -> Dict:
        return self.from_stream(self.user.enterprise_tags.get(name_or_id))

    def from_user_category(self, name_or_id: str) -> Dict:
        return self.from_stream(self.user.user_categories.get(name_or_id))

    def from_stream(self, stream: Streamable) -> Dict:
        return self.from_stream_id(stream.id)

    def from_stream_id(self, stream_id: str) -> Dict:
        return {
            "objects": self._download_ioc_objects(stream_id=stream_id),
            "id": f"bundle--{str(uuid.uuid4())}",
            "type": "bundle",
        }

    def _download_ioc_objects(self, stream_id: str) -> List[Dict]:
        objects = []
        continuation = None
        while True:
            resp = self.session.make_api_request(
                f"{self.RELATIVE_URL}",
                params={
                    "newerThan": int(self.newer_than.timestamp()) if self.newer_than else None,
                    "continuation": continuation,
                    "streamId": stream_id,
                },
            )
            objects += resp.json()["objects"]
            if not self.newer_than:
                return objects
            if "link" not in resp.headers:
                return objects
            next_url = resp.headers["link"][1:].split(">")[0]
            continuation = parse_qs(next_url)["continuation"][0]
