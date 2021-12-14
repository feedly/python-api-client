import json
from datetime import datetime, timedelta
from pprint import pprint

from feedly.api_client.enterprise.indicators_of_compromise import FeedlyIoCFetcher
from feedly.api_client.session import FeedlySession, FileAuthStore
from feedly.examples.utils import AUTH_DIR, RESULTS_DIR

if __name__ == "__main__":
    """
    You need to setup your auth directory as described in the README of the library.
    Alternatively, you can remove the `FileAuthStore` usage and replace it by the token directly, but you'll need to do
     it in every example.
    
    This example will save a STIX 2.1 bundle containing the contextualized IoCs that Leo extracted during the past 12
     hours in all your enterprise feeds. 
    """
    # Authenticate using the auth directory
    session = FeedlySession(auth=FileAuthStore(AUTH_DIR))

    # Create the IoC fetcher object, and limit it to 12 hours
    # Usually newer_than will be the datetime of the last fetch
    fetcher = FeedlyIoCFetcher(session=session, newer_than=datetime.now() - timedelta(hours=12))

    # Fetch the IoC from all the enterprise categories, and create a bundle containing them
    # You can use a different method to get the iocs from you personal categories, personal or enterprise boards,
    #  or from specific categories/boards using their names or ids
    iocs_bundle = fetcher.from_all_enterprise_categories()

    # Save the bundle in a file
    with (RESULTS_DIR / "ioc_example.json").open("w") as f:
        json.dump(iocs_bundle, f, indent=2)

    # Console display
    pprint(iocs_bundle)
