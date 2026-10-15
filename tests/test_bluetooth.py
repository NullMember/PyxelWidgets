"""Bluetooth MIDI devices (pyxelwidgets.devices.bluetooth) with a stand-in backend."""

import json
import threading
import urllib.request

from pyxelwidgets.devices.bluetooth import Bluetooth, Unavailable

class FakeCentral:
    def __init__(self):
        self.near = {'AA:01': 'PyMIDI', 'AA:02': 'Keys'}
        self.open = {}
        self.refuse = None

    def problem(self, ask = False):
        return self.refuse

    def scan(self, seconds):
        return [{'address': address, 'name': name, 'rssi': -60 - index} for index, (address, name) in enumerate(self.near.items())][::-1]

    def connect(self, address):
        if address not in self.near:
            raise OSError(f'Connecting to {address} timed out')
        self.open[address] = self.near[address]
        return self.near[address]

    def disconnect(self, address):
        self.open.pop(address, None)

    def pair(self, address):
        if address not in self.near:
            raise OSError('Pairing was refused or failed')
        self.paired = address

    def connected(self):
        return [{'address': address, 'name': name} for address, name in self.open.items()]

def test_scan_connect_remember_forget(tmp_path):
    central = FakeCentral()
    bluetooth = Bluetooth(central, tmp_path / 'bt.json')
    assert [device['name'] for device in bluetooth.scan()] == ['PyMIDI', 'Keys']
    assert bluetooth.connect('AA:01') == 'PyMIDI'
    assert json.loads((tmp_path / 'bt.json').read_text()) == [{'address': 'AA:01', 'name': 'PyMIDI'}]
    status = bluetooth.status()
    assert status['connected'] == [{'address': 'AA:01', 'name': 'PyMIDI'}] and status['remembered'] == []
    # Out of range: remembered, connected again by reconnect
    central.open.clear()
    assert bluetooth.status()['remembered'] == [{'address': 'AA:01', 'name': 'PyMIDI', 'error': None}]
    assert bluetooth.reconnect() == ['PyMIDI']
    # Disconnect forgets
    bluetooth.disconnect('AA:01')
    assert bluetooth.remembered() == [] and central.open == {}

def test_reconnect_keeps_errors_and_asks_nothing(tmp_path):
    central = FakeCentral()
    bluetooth = Bluetooth(central, tmp_path / 'bt.json')
    bluetooth.connect('AA:02')
    central.open.clear()
    del central.near['AA:02']
    assert bluetooth.reconnect() == []
    assert 'timed out' in bluetooth.status()['remembered'][0]['error']
    central.refuse = 'Bluetooth is off'
    try:
        bluetooth.scan()
    except Unavailable as error:
        assert str(error) == 'Bluetooth is off'
    else:
        raise AssertionError('scan went ahead')
    assert bluetooth.reconnect() == []

def test_no_backend(tmp_path):
    bluetooth = Bluetooth(None, tmp_path / 'bt.json')
    bluetooth.backend = None
    status = bluetooth.status()
    assert not status['available'] and status['problem']

def test_designer_api_without_bluetooth(tmp_path, monkeypatch):
    import pyxelwidgets.designer as designer
    import pyxelwidgets.devices.bluetooth as module
    monkeypatch.setattr(module, '_manager', Bluetooth(FakeCentral(), tmp_path / 'bt.json'))
    server = designer.serve(None, 0, connect = False, dialogs = False)
    threading.Thread(target = server.serve_forever, daemon = True).start()
    url = server.RequestHandlerClass.designer.local_url()
    try:
        def post(body):
            request = urllib.request.Request(url + 'api/bluetooth', data = json.dumps(body).encode(), method = 'POST',
                                             headers = {'Content-Type': 'application/json'})
            return json.load(urllib.request.urlopen(request))
        assert [device['address'] for device in post({'action': 'scan', 'seconds': 0.1})['found']] == ['AA:01', 'AA:02']
        reply = post({'action': 'connect', 'address': 'AA:01'})
        assert reply['ok'] and reply['name'] == 'PyMIDI' and reply['connected'][0]['address'] == 'AA:01'
        reply = post({'action': 'connect', 'address': 'BB:00'})
        assert not reply['ok'] and 'timed out' in reply['error']
        assert post({'action': 'pair', 'address': 'AA:02'})['ok'] and module._manager.backend.paired == 'AA:02'
        reply = post({'action': 'pair', 'address': 'BB:00'})
        assert not reply['ok'] and 'refused' in reply['error']
        assert post({'action': 'disconnect', 'address': 'AA:01'})['connected'] == []
        with urllib.request.urlopen(url + 'api/bluetooth') as status:
            assert json.load(status)['available']
    finally:
        server.RequestHandlerClass.designer.close()
        server.shutdown()
        server.server_close()

def test_reconnect_by_name_after_a_new_address(tmp_path):
    central = FakeCentral()
    bluetooth = Bluetooth(central, tmp_path / 'bt.json')
    bluetooth.connect('AA:01')
    central.open.clear()
    # The phone advertises from a new address now
    del central.near['AA:01']
    central.near['CC:09'] = 'PyMIDI'
    assert bluetooth.reconnect() == ['PyMIDI']
    assert bluetooth.remembered() == [{'address': 'CC:09', 'name': 'PyMIDI'}]
    # Two of the same name: neither is taken
    central.open.clear()
    del central.near['CC:09']
    central.near['DD:01'] = central.near['DD:02'] = 'PyMIDI'
    assert bluetooth.reconnect() == []
