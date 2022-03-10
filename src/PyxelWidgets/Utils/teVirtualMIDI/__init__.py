import ctypes
import ctypes.util
import os
import platform
import time

class teVirtualMIDI:

    class WrongArchitectureError(Exception):
        pass

    class WrongOSError(Exception):
        pass

    class NotFoundError(Exception):
        pass

    def __init__(self, buffer_size = 65536) -> None:
        if platform.system() != 'Windows':
            raise teVirtualMIDI.WrongOSError("OS must be Windows")
        if platform.machine() == 'AMD64':
            _filename = 'teVirtualMIDI64'
        elif platform.machine() == 'i386':
            _filename = 'teVirtualMIDI32'
        else:
            raise teVirtualMIDI.WrongArchitectureError("Architecture must be i386 or AMD64")
        self._vmd = None
        _extension = '.dll'

        # This will search teVirtualMIDI{architecture}.dll in your PATH or
        # directory of your script.
        DLLPATH = ctypes.util.find_library(_filename + _extension)
        if DLLPATH != None:
            self._vmd = ctypes.windll.LoadLibrary(os.path.abspath(DLLPATH))
        else:
            DLLPATH = f'./{_filename}{_extension}'
            if os.path.exists(DLLPATH):
                try:
                    self._vmd = ctypes.windll.LoadLibrary(DLLPATH)
                except:
                    raise teVirtualMIDI.NotFoundError(f'{_filename}{_extension} not found')
        
        self._create_midi_port = self._vmd.virtualMIDICreatePortEx2
        self._create_midi_port.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong]
        self._create_midi_port.restype = ctypes.c_void_p

        self._close_midi_port = self._vmd.virtualMIDIClosePort
        self._close_midi_port.argtypes = [ctypes.c_void_p]
        self._close_midi_port.restype = None

        self._send_message = self._vmd.virtualMIDISendData
        self._send_message.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_ulong]
        self._send_message.restype = ctypes.c_bool

        self._get_message = self._vmd.virtualMIDIGetData
        self._get_message.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(ctypes.c_ulong)]
        self._get_message.restype = ctypes.c_bool
        
        self._midi_callback = ctypes.WINFUNCTYPE(None, ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_ulong, ctypes.c_void_p)
        self._vm_callback = self._midi_callback(self._callback)

        self._midi_port = None
        self._buffer_size: int = buffer_size
        self._buffer = (ctypes.c_ubyte * self._buffer_size)()

        self._message_time = time.time()
        self._user_data = None

        self._user_callback = lambda *args, **kwargs : None

    def __del__(self):
        self.close_port()

    def _callback(self, midi_port, buffer, length, instance):
        oldTime = self._message_time
        self._message_time = time.time()
        self._user_callback((list(buffer[:length]), self._message_time - oldTime), self._user_data)

    def open_port(self, name: str): 
        if self._midi_port is not None:
            return False
        self._midi_port = self._create_midi_port(name, self._vm_callback, None, self._buffer_size, 13)
        if self._midi_port is not None:
            return True
        return False
    
    def close_port(self):
        if self._midi_port is None:
            return False
        self._close_midi_port(self._midi_port)
        self._midi_port = None
        return True
    
    def send_message(self, data):
        if self._midi_port is None:
            return False
        buffer = (ctypes.c_ubyte * len(data))()
        for i, d in enumerate(data):
            buffer[i] = d
        return self._send_message(self._midi_port, buffer, len(buffer))
    
    def get_message(self):
        if self._midi_port is None:
            return False
        length = ctypes.c_ulong()
        self._get_message(self._midi_port, ctypes.cast(self._buffer, ctypes.POINTER(ctypes.c_ubyte)), length)
        if length:
            old_time = self._message_time
            self._message_time = time.time()
            return (list(self._buffer[:length.value]), self._message_time - old_time)
        else:
            return None
    
    def set_callback(self, callback, data = None):
        self._user_data = data
        self._user_callback = callback