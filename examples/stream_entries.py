from feedly.api_client.session import FeedlySession
from feedly.api_client.stream import StreamOptions
from feedly.api_client.utils import run_example


def example_stream_entries():
    """
    This example will prompt you to enter a category name, download the 10 latest articles from it, and display their
     titles.
    """
    # Prompt for the category name/id to use
    user_category_name_or_id = input("> User category name or id: ")

    # Create the session using the default auth directory
    session = FeedlySession()

    # Fetch the category by its name/id
    # To use an enterprise category, change to `session.user.enterprise_categories`. Tags are also supported.
    category = session.user.user_categories.get(user_category_name_or_id)

    # Stream 10 articles with their contents from the category
    for article in category.stream_contents(options=StreamOptions(max_count=10)):
        # Print the title of each article
        print(article["title"])


if __name__ == "__main__":
    # Will prompt for the token if missing, and launch the example above
    # If a token expired error is raised, will prompt for a new token and restart the example
    run_example(example_stream_entries)
