# FUNCTIONS

class FakeChrome:
    def __init__(self, options):
        self.options = options
        self._connection_port = None
        self._connection_handler = None
        self.setup_user_dir_called = False

    def _setup_user_dir(self):
        self.setup_user_dir_called = True

    def _get_default_binary_location(self):
        return "/fake/Google Chrome"

    async def stop(self):
        pass


def _reset_state(monkeypatch, browser):
    monkeypatch.setattr(browser, "_browser", None)
    monkeypatch.setattr(browser, "_lock_handle", None)
    monkeypatch.setattr(browser, "_owned_pids", [])
    monkeypatch.setattr(browser, "_session_dir", None)
    monkeypatch.setattr(browser, "_focus_watchdog_task", None)
