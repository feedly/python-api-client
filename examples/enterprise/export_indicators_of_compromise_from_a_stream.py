import json
from datetime import datetime, timedelta
from pathlib import Path
from pprint import pprint

from feedly.api_client.enterprise.indicators_of_compromise import IoCDownloader
from feedly.api_client.session import FeedlySession
from feedly.api_client.utils import run_example

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def example_export_indicators_of_compromise_from_all_enterprise_feeds():
    """
    This example will save a STIX 2.1 bundle containing the contextualized IoCs that Leo extracted during the past 12
     hours in all your enterprise feeds. 
    """
    # Authenticate using the default auth directory
    session = FeedlySession()

    # Create the IoC fetcher object, and limit it to 12 hours
    # Usually newer_than will be the datetime of the last fetch
    downloader = IoCDownloader(session=session, newer_than=datetime.now() - timedelta(hours=12))

    # Fetch the IoC from all the enterprise categories, and create a bundle containing them
    # You can use a different method to get the iocs from you personal categories, personal or enterprise boards,
    #  or from specific categories/boards using their names or ids
    iocs_bundle = downloader.from_all_enterprise_categories()

    # Save the bundle in a file
    with (RESULTS_DIR / "ioc_example.json").open("w") as f:
        json.dump(iocs_bundle, f, indent=2)

    # Console display
    pprint(iocs_bundle)


if __name__ == "__main__":
    # Will prompt for the token if missing, and launch the example above
    # If a token expired error is raised, will prompt for a new token and restart the example
    run_example(example_export_indicators_of_compromise_from_all_enterprise_feeds)
