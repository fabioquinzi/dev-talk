"""Entry point for `python -m dev_talk`."""

from dev_talk.app import DevTalkApp


def main() -> None:
    app = DevTalkApp()
    app.run()


if __name__ == "__main__":
    main()
