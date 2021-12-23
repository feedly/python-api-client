from pprint import pprint

from feedly.api_client.session import FeedlySession
from feedly.api_client.utils import run_example


def example_display_feeds_and_boards():
    """
    This example will display your personal feeds and boards.
    Additionally, if you are part of a team, it will also display the team ones.
    """
    # Create the session using the default auth directory
    user = FeedlySession().user

    # Display the personal categories and tags
    print("User feeds:")
    pprint(user.user_categories.name2stream)
    print()
    print("User boards:")
    pprint(user.user_tags.name2stream)
    # Display the enterprise categories and tags, if part of a team
    if "enterpriseName" in user.json:
        print()
        print("Team feeds:")
        pprint(user.enterprise_categories.name2stream)
        print()
        print("Team boards:")
        pprint(user.enterprise_tags.name2stream)


if __name__ == "__main__":
    # Will prompt for the token if missing, and launch the example above
    # If a token expired error is raised, will prompt for a new token and restart the example
    run_example(example_display_feeds_and_boards)
