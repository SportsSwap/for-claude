"""Sawnx opens in its own app-style window: Chrome first, then Edge, otherwise the default browser."""

import ntpath

import pytest

from tra.web import server

URL = "http://127.0.0.1:8766/?key=sample-key"
CHROME_X86 = ntpath.join(r"C:\Program Files (x86)", r"Google\Chrome\Application\chrome.exe")
EDGE_X86 = ntpath.join(r"C:\Program Files (x86)", r"Microsoft\Edge\Application\msedge.exe")
ENV = {"ProgramFiles": r"C:\Program Files", "ProgramFiles(x86)": r"C:\Program Files (x86)",
       "LOCALAPPDATA": r"C:\Users\sample\AppData\Local"}


def _only(*paths):
    return lambda p: p in paths


def test_chrome_app_window_first():
    cmd = server.app_window_command(URL, env=ENV, exists=_only(CHROME_X86, EDGE_X86), join=ntpath.join)
    assert cmd == [CHROME_X86, f"--app={URL}"]


def test_chrome_for_one_user_found():
    chrome = ntpath.join(ENV["LOCALAPPDATA"], r"Google\Chrome\Application\chrome.exe")
    assert server.app_window_command(URL, env=ENV, exists=_only(chrome), join=ntpath.join)[0] == chrome


def test_edge_when_no_chrome():
    cmd = server.app_window_command(URL, env=ENV, exists=_only(EDGE_X86), join=ntpath.join)
    assert cmd == [EDGE_X86, f"--app={URL}"]


def test_neither_gives_none():
    assert server.app_window_command(URL, env=ENV, exists=_only(), join=ntpath.join) is None


def test_default_browser_when_no_app_browser(monkeypatch):
    opened = []
    monkeypatch.setattr(server.webbrowser, "open", opened.append)
    server.open_in_browser(URL, env=ENV, exists=_only(), launch=pytest.fail)
    assert opened == [URL]


def test_launch_failure_falls_back(monkeypatch):
    opened = []
    monkeypatch.setattr(server.webbrowser, "open", opened.append)

    def broken(cmd):
        raise OSError("blocked by policy")

    server.open_in_browser(URL, env=ENV, exists=_only(CHROME_X86), launch=broken, join=ntpath.join)
    assert opened == [URL]


def test_app_window_launched(monkeypatch):
    launched = []
    monkeypatch.setattr(server.webbrowser, "open", pytest.fail)
    server.open_in_browser(URL, env=ENV, exists=_only(CHROME_X86), launch=launched.append, join=ntpath.join)
    assert launched == [[CHROME_X86, f"--app={URL}"]]


def test_run_opens_the_app_window(tmp_path, monkeypatch):
    from tra.settings import Settings

    monkeypatch.setenv("TRA_HOME", str(tmp_path))
    opened = []

    class FakeServer:
        server_port = 8766

        def serve_forever(self):
            raise KeyboardInterrupt

        def server_close(self):
            pass

    monkeypatch.setattr(server, "bind", lambda app, port: FakeServer())
    monkeypatch.setattr(server, "open_in_browser", opened.append)
    server.run(Settings.from_env(), port=8766, echo=lambda line: None)
    [url] = opened
    assert url.startswith("http://127.0.0.1:8766/?key=")
