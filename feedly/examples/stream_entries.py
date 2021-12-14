from feedly.api_client.session import FeedlySession, FileAuthStore
from feedly.api_client.stream import StreamOptions
from feedly.examples.utils import AUTH_DIR

if __name__ == "__main__":
    """
    You need to setup your auth directory as described in the README of the library.
    Alternatively, you can remove the `FileAuthStore` usage and replace it by the token directly, but you'll need to do
     it in every example .
     
    This example will prompt you to enter a category name, download the 10 latest articles from it, and display their
     titles.
    """
    # Prompt for the category name/id to use
    user_category_name_or_id = input("> User category name or id: ")

    # Create the session using the auth directory
    session = FeedlySession(auth=FileAuthStore(AUTH_DIR))

    # Fetch the category by its name/id
    # To use an enterprise category, change to `session.user.enterprise_categories`. Tags are also supported.
    category = session.user.user_categories.get(user_category_name_or_id)

    # Stream 10 articles with their contents from the category
    for article in category.stream_contents(options=StreamOptions(max_count=10)):
        # Print the title of each article
        print(article["title"])
