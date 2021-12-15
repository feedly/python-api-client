import logging
from pathlib import Path
from typing import Callable

from feedly.api_client.protocol import UnauthorizedAPIError
from feedly.examples.setup_auth import setup_auth

EXAMPLES_DIR = Path(__file__).parent
RESULTS_DIR = EXAMPLES_DIR / "results"

RESULTS_DIR.mkdir(exist_ok=True)


def run_example(f: Callable) -> None:
    setup_auth()
    try:
        f()
        return
    except UnauthorizedAPIError as e:
        if "token expired" not in e.response.text:
            raise e

        logging.warning("Expired token. Please enter a new valid token.")
        setup_auth(overwrite=True)

        f()
