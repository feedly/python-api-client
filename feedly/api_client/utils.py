import logging
from pathlib import Path
from typing import Callable

from feedly.api_client.protocol import UnauthorizedAPIError


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


def setup_auth(directory: Path = Path.home() / ".config/feedly", overwrite: bool = False):
    directory.mkdir(exist_ok=True, parents=True)

    auth_file = directory / "access.token"

    if not auth_file.exists() or overwrite:
        auth = input("Enter your token: ")
        auth_file.write_text(auth.strip())
