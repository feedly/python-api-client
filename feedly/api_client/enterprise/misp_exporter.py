import json
import logging
from typing import Iterable

import requests


class MispExporter:
    def __init__(self, url: str, key: str, ignore_errors: bool = False, verify_certificate: bool = True):
        self.url = url.rstrip("/")
        self.key = key
        self.ignore_errors = ignore_errors
        self.verify_certificate = verify_certificate

    def send_bundles(self, bundles: Iterable[dict]) -> None:
        self.send_events(event["Event"] for bundle in bundles for event in bundle["response"])

    def send_events(self, events: Iterable[dict]) -> None:
        for event in events:
            self.send_event(event)

    def send_event(self, event: dict) -> None:
        try:
            resp = requests.post(
                f"{self.url}/events/add",
                headers={"Authorization": self.key, "Accept": f"application/json", "content-type": f"application/json"},
                data=json.dumps(event),
                verify=self.verify_certificate,
            )
            resp.raise_for_status()
            logging.info(f"{self.url}/events/view/{resp.json()['Event']['id']}")
        except:
            if self.ignore_errors:
                logging.exception(f"Failed to send event {event}")
                return
            raise
