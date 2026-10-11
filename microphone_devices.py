"""Choose the configured capture device without opening/reading OBS."""
import ctypes as C
from ctypes import wintypes as W

class Caps(C.Structure):
    _fields_ = [('mid', W.WORD), ('pid', W.WORD), ('version', W.DWORD),
                ('name', W.WCHAR * 32), ('formats', W.DWORD),
                ('channels', W.WORD), ('reserved', W.WORD), ('support', W.DWORD)]

def devices():
    api = C.WinDLL('winmm')
    api.waveInGetDevCapsW.argtypes = [C.c_size_t, C.POINTER(Caps), W.UINT]
    api.waveInMessage.argtypes = [C.c_void_p, W.UINT, C.c_size_t, C.c_size_t]
    result = []
    for index in range(api.waveInGetNumDevs()):
        caps, size = Caps(), W.DWORD()
        if api.waveInGetDevCapsW(index, C.byref(caps), C.sizeof(caps)):
            continue
        endpoint = ''
        if not api.waveInMessage(index, 0x812, C.addressof(size), 0) and 0 < size.value < 65536:
            buffer = C.create_unicode_buffer((size.value + 1) // 2)
            if not api.waveInMessage(index, 0x811, C.addressof(buffer), size.value):
                endpoint = buffer.value
        result.append({'index': index, 'name': caps.name, 'endpoint': endpoint})
    return result

def select(settings):
    wanted = settings.get('microphone_endpoint')
    for device in devices():
        if wanted and device['endpoint'].casefold() == wanted.casefold():
            return device['index'], device['name'] + ' · micrófono configurado', wanted
    return 0xFFFFFFFF, 'Micrófono predeterminado de Windows' + (' · revisa el dispositivo configurado' if wanted else ''), ''
