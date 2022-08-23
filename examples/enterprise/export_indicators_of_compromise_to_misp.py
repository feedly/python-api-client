import logging
from datetime import datetime, timedelta
from warnings import filterwarnings

from feedly.api_client.enterprise.indicators_of_compromise import IoCDownloaderBuilder, IoCFormat
from feedly.api_client.enterprise.misp_exporter import MispExporter
from feedly.api_client.session import FeedlySession
from feedly.api_client.utils import run_example

# Enter your MISP key and URL below
MISP_KEY = ""
MISP_URL = ""

assert MISP_KEY, "Please enter your MISP key"
assert MISP_URL, "Please enter MISP url"


def export_indicators_of_compromise_to_misp():
    """
    This example will export to your MISP instance the contextualized IoCs that Leo extracted during the past 6 hours
     in all your enterprise feeds.
    """
    # Authenticate using the default auth directory
    session = FeedlySession()

    # Create the MISP IoC downloader builder object, and limit it to 6 hours
    # Usually newer_than will be the datetime of the last fetch
    downloader_builder = IoCDownloaderBuilder(
        session=session, newer_than=datetime.now() - timedelta(hours=6), format=IoCFormat.MISP
    )

    # Fetch the IoC from all the enterprise categories, and feed them to the exporter
    # You can use a different method to get the iocs from you personal categories, personal or enterprise boards,
    #  or from specific categories/boards using their names or ids
    downloader = downloader_builder.from_all_enterprise_categories()
    exporter = MispExporter(MISP_URL, MISP_KEY, ignore_errors=True, verify_certificate=False)
    exporter.send_bundles(downloader.stream_bundles())


if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    filterwarnings("ignore")

    # Will prompt for the token if missing, and launch the example above
    # If a token expired error is raised, will prompt for a new token and restart the example
    run_example(export_indicators_of_compromise_to_misp)
