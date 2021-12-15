from pathlib import Path


def setup_auth(directory: Path = Path.home() / ".config/feedly", overwrite: bool = False):
    directory.mkdir(exist_ok=True, parents=True)

    auth_file = directory / "access.token"

    if not auth_file.exists() or overwrite:
        auth = input("Enter your token: ")
        auth_file.write_text(auth.strip())


if __name__ == "__main__":
    setup_auth(overwrite=True)
