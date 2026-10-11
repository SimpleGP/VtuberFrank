"""Same WinMM volume sampling and six-control tracker as the supplied local project."""
import array
import ctypes as C
from ctypes import wintypes as W
import math
import time
from microphone_devices import select as select_microphone

class WaveFormat(C.Structure):
    _fields_ = [("tag", W.WORD), ("channels", W.WORD), ("rate", W.DWORD),
                ("bytes_sec", W.DWORD), ("block", W.WORD), ("bits", W.WORD), ("extra", W.WORD)]

class WaveHeader(C.Structure):
    _fields_ = [("data", C.c_void_p), ("length", W.DWORD), ("recorded", W.DWORD),
                ("user", C.c_size_t), ("flags", W.DWORD), ("loops", W.DWORD),
                ("next", C.c_void_p), ("reserved", C.c_size_t)]


def microphone(shared, stop, settings):
    state = shared.data
    api = C.WinDLL("winmm")
    api.waveInOpen.argtypes = [C.POINTER(C.c_void_p), W.UINT, C.POINTER(WaveFormat), C.c_size_t, C.c_size_t, W.DWORD]
    for name in ("waveInPrepareHeader", "waveInUnprepareHeader", "waveInAddBuffer"):
        getattr(api, name).argtypes = [C.c_void_p, C.POINTER(WaveHeader), W.UINT]
    for name in ("waveInStart", "waveInReset", "waveInClose"):
        getattr(api, name).argtypes = [C.c_void_p]
    handle = C.c_void_p()
    fmt = WaveFormat(1, 1, 44100, 88200, 2, 16, 0)
    device, label, endpoint = select_microphone(settings)
    result = api.waveInOpen(C.byref(handle), device, C.byref(fmt), 0, 0, 0)
    if result:
        state["microphone"] = f"No disponible (WinMM {result})"
        return
    buffers = [C.create_string_buffer(4410) for _ in range(4)]
    headers = [WaveHeader(C.cast(buf, C.c_void_p), len(buf), 0, 0, 0, 0, None, 0) for buf in buffers]
    prepared = []
    try:
        for header in headers:
            if api.waveInPrepareHeader(handle, C.byref(header), C.sizeof(header)):
                raise RuntimeError("No se pudo preparar el micrófono")
            prepared.append(header)
            if api.waveInAddBuffer(handle, C.byref(header), C.sizeof(header)):
                raise RuntimeError("No se pudo iniciar el búfer de audio")
        if api.waveInStart(handle):
            raise RuntimeError("No se pudo iniciar el micrófono")
        state["microphone"] = label
        if endpoint:
            settings['microphone_endpoint'] = endpoint
            pass  # Endpoint remains in local settings only.
        hold_until = 0
        while not stop.wait(0.015):
            for header in headers:
                if not header.flags & 1:
                    continue
                samples = array.array("h", C.string_at(header.data, header.recorded))
                rms = math.sqrt(sum(x * x for x in samples) / max(1, len(samples))) / 32768
                state["db"] = round(20 * math.log10(max(rms, 0.00001)), 1)
                if state["db"] >= state["threshold"]:
                    hold_until = time.monotonic() + 0.15
                state["speaking"] = time.monotonic() < hold_until
                header.recorded = 0
                if api.waveInAddBuffer(handle, C.byref(header), C.sizeof(header)):
                    raise RuntimeError("Se desconectó el micrófono")
    except Exception as exc:
        state["microphone"] = str(exc)
        state["speaking"] = False
    finally:
        api.waveInReset(handle)
        for header in prepared:
            api.waveInUnprepareHeader(handle, C.byref(header), C.sizeof(header))
        api.waveInClose(handle)
