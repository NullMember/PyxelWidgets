__all__ = ['REAPER']

import pythonosc.udp_client
import pythonosc.dispatcher
import pythonosc.osc_server
import pythonosc.osc_bundle_builder
import pythonosc.osc_message_builder
import threading
import PyxelWidgets.Controllers

class OSC(PyxelWidgets.Controllers.Controller):
    def __init__(self, ip, in_port = 8000, out_port = 9000, **kwargs):
        super().__init__(**kwargs)
        self.client = pythonosc.udp_client.SimpleUDPClient(ip, out_port)
        self.dispatcher = pythonosc.dispatcher.Dispatcher()
        self.server = pythonosc.osc_server.ThreadingOSCUDPServer(('0.0.0.0', in_port), self.dispatcher)
        self.messages = {}
        self.handlers = {}
        self.responses = {}

    def connect(self):
        super().connect()
        self.register()
        self._serverThread = threading.Thread(target = self.server.serve_forever)
        self._serverThread.start()
    
    def disconnect(self):
        self.server.shutdown()
        self.unregister()
        super().disconnect()
    
    def send(self, name, value):
        self.client.send_message(self.messages[name], value)
    
    def register(self):
        for message in self.messages:
            self.handlers[message] = self.dispatcher.map(self.messages[message], self.process, message)
    
    def unregister(self):
        for message in self.messages:
            self.dispatcher.unmap(self.messages[message], self.handlers[message])
    
    def process(self, addr: str, args, value):
        print(args[0], addr, value)