"""Sharing the designer on the network: the key, the second listener, --host."""

import json
import sys
import threading
import urllib.error
import urllib.request

import pytest

import pyxelwidgets.designer as designer_module
from pyxelwidgets.designer import network_address, serve, share_key

@pytest.fixture
def server():
    server = serve(None, 0, connect = False, dialogs = False, key = 'sesame')
    threading.Thread(target = server.serve_forever, daemon = True).start()
    yield server
    server.RequestHandlerClass.designer.close()
    server.shutdown()
    server.server_close()

def status(url, cookie = None, data = None):
    request = urllib.request.Request(url, data = data, method = 'POST' if data else 'GET',
                                     headers = {'Cookie': cookie} if cookie else {})
    try:
        with urllib.request.urlopen(request, timeout = 5) as reply:
            return reply.status, reply.headers.get('Set-Cookie')
    except urllib.error.HTTPError as error:
        return error.code, None

def test_share_key_is_made_once(tmp_path):
    path = tmp_path / 'sub' / 'key'
    key = share_key(path)
    assert len(key) >= 16 and share_key(path) == key
    # Windows has no such modes (the file is in the user's profile)
    assert sys.platform == 'win32' or path.stat().st_mode & 0o077 == 0

def test_not_shared_at_first(server):
    designer = server.RequestHandlerClass.designer
    assert designer.sharing() == {'shared': False, 'fixed': False, 'urls': []}
    assert designer.local_url().startswith('http://127.0.0.1:')
    with urllib.request.urlopen(designer.local_url() + 'api/share') as reply:
        assert json.load(reply)['local'] is True

def test_share_and_stop(server):
    designer = server.RequestHandlerClass.designer
    request = urllib.request.Request(designer.local_url() + 'api/share', data = b'{"shared": true}', method = 'POST')
    with urllib.request.urlopen(request) as reply:
        shared = json.load(reply)
    assert shared['shared'] and not shared['fixed']
    assert shared['urls'][0].endswith('/?key=sesame')
    assert designer.share(False)['shared'] is False
    assert designer._shared is None

@pytest.mark.skipif(network_address() == '127.0.0.1', reason = 'no network address')
def test_other_computers_need_the_key(server):
    designer = server.RequestHandlerClass.designer
    url = designer.share(True)['urls'][0]
    bare = url.split('?')[0]
    assert status(bare)[0] == 403
    assert status(bare + 'api/layout')[0] == 403
    assert status(bare + '?key=wrong')[0] == 403
    code, cookie = status(url)
    assert code == 200 and cookie.startswith('pyxelwidgets_key=sesame;') and 'HttpOnly' in cookie
    assert status(bare + 'api/layout', cookie = 'pyxelwidgets_key=sesame')[0] == 200
    # Only this computer changes sharing
    assert status(bare + 'api/share', cookie = 'pyxelwidgets_key=sesame', data = b'{"shared": false}')[0] == 403
    assert designer.sharing()['shared']

@pytest.mark.skipif(network_address() == '127.0.0.1', reason = 'no network address')
def test_host_everywhere_is_fixed():
    server = serve(None, 0, '0.0.0.0', connect = False, dialogs = False, key = 'k')
    threading.Thread(target = server.serve_forever, daemon = True).start()
    try:
        designer = server.RequestHandlerClass.designer
        assert designer.fixed()
        assert designer.local_url().startswith('http://127.0.0.1:')
        assert designer.share(False)['shared'] is True
        port = server.server_address[1]
        assert designer.network_urls()[0] == f'http://{network_address()}:{port}/?key=k'
        assert status(f'http://{network_address()}:{port}/api/layout')[0] == 403
        assert status(designer.network_urls()[0])[0] == 200
    finally:
        server.RequestHandlerClass.designer.close()
        server.shutdown()
        server.server_close()

def test_taken_port_makes_no_designer(server, monkeypatch):
    made = []
    monkeypatch.setattr(designer_module, 'Designer', lambda *args, **options: made.append(1))
    with pytest.raises(OSError):
        serve(None, server.server_address[1], connect = False)
    assert not made
