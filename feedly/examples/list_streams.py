from pprint import pprint

from feedly.api_client.session import FeedlySession, FileAuthStore
from feedly.examples.utils import AUTH_DIR

if __name__ == "__main__":
    """
    You need to setup your auth directory as described in the README of the library.
    Alternatively, you can remove the `FileAuthStore` usage and replace it by the token directly, but you'll need to do
     it in every example .
     
    This example will display your personal categories and tags.
    Additionally, if you are part of an team, it will also display the enterprise ones.
    """
    # Create the session using the auth directory
    user = FeedlySession(auth=FileAuthStore(AUTH_DIR)).user

    # Display the personal categories and tags
    print("User categories:")
    pprint(user.user_categories.name2stream)
    print()
    print("User tags:")
    pprint(user.user_tags.name2stream)

    # Display the enterprise categories and tags, if part of a team
    if "enterpriseName" in user.json:
        print()
        print("Enterprise categories:")
        pprint(user.enterprise_categories.name2stream)
        print()
        print("Enterprise tags:")
        pprint(user.enterprise_tags.name2stream)
