from pythonosc.udp_client import SimpleUDPClient
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc.osc_bundle_builder import OscBundleBuilder, IMMEDIATELY
from pythonosc.osc_message_builder import OscMessageBuilder
from threading import Thread
from .Controller import Controller

class OSC(Controller):
    def __init__(self, ip, in_port = 8000, out_port = 9000, **kwargs):
        super().__init__(**kwargs)
        self._client = SimpleUDPClient(ip, out_port)
        self._dispatcher = Dispatcher()
        self._server = ThreadingOSCUDPServer(('0.0.0.0', in_port), self._dispatcher)
        self.register()

    def init(self):
        self._connected = True
        self._serverThread = Thread(target = self._server.serve_forever)
        self._serverThread.start()
    
    def deinit(self):
        self._connected = False
        self._server.shutdown()
    
    def register(self):
        for x in range(self.width):
            for y in range(self.height):
                self._dispatcher.map('/pad/' + str(x) + '/' + str(y), self.process)

    @property
    def dispatcher(self) -> Dispatcher:
        return self._dispatcher
    
    def process(self, addr: str, value):
        print(addr, value)
        path = addr.split('/')
        if path[1] == 'pad':
            x = int(path[2])
            y = int(path[3])
            self._callback(x, y, value)
    
    def updateOne(self, x, y, pixel):
        if self._connected:
            try:
                if pixel == self._pixels[x][y]:
                    pass
                else:
                    self._pixels[x][y] = pixel
                    intensity = (self._pixels[x][y][0] + self._pixels[x][y][1] + self._pixels[x][y][2]) / (255 * 3)
                    self._client.send_message('/led/' + str(x) + '/' + str(y), intensity)
            except:
                pass
    
    def updateRow(self, y, pixels):
        if self._connected:
            for x in range(self.width):
                try:
                    if pixels[x] == self._pixels[x][y]:
                        pass
                    else:
                        self._pixels[x][y] = pixels[x]
                        intensity = (self._pixels[x][y][0] + self._pixels[x][y][1] + self._pixels[x][y][2]) / (255 * 3)
                        self._client.send_message('/led/' + str(x) + '/' + str(y), intensity)
                except:
                    pass
    
    def updateColumn(self, x, pixels):
        if self._connected:
            for y in range(self.height):
                try:
                    if pixels[y] == self._pixels[x][y]:
                        pass
                    else:
                        self._pixels[x][y] = pixels[y]
                        intensity = (self._pixels[x][y][0] + self._pixels[x][y][1] + self._pixels[x][y][2]) / (255 * 3)
                        self._client.send_message('/led/' + str(x) + '/' + str(y), intensity)
                except:
                    pass
    
    def updateArea(self, x, y, width, height, pixels):
        if self._connected:
            for _x in range(width):
                for _y in range(height):
                    try:
                        if pixels[_x][_y] == self._pixels[x + _x][y + _y]:
                            pass
                        else:
                            self._pixels[x + _x][y + _y] = pixels[_x][_y]
                            intensity = (self._pixels[x + _x][y + _y][0] + self._pixels[x + _x][y + _y][1] + self._pixels[x + _x][y + _y][2]) / (255 * 3)
                            self._client.send_message('/led/' + str(_x) + '/' + str(_y), intensity)
                    except:
                        pass
    
    def update(self, pixels):
        if self._connected:
            for x in range(self.width):
                for y in range(self.height):
                    try:
                        if pixels[x][y] == self._pixels[x][y]:
                            pass
                        else:
                            self._pixels[x][y] = pixels[x][y]
                            intensity = (self._pixels[x][y][0] + self._pixels[x][y][1] + self._pixels[x][y][2]) / (255 * 3)
                            self._client.send_message('/led/' + str(x) + '/' + str(y), intensity)
                    except:
                        pass
    