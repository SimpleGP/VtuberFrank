"""Foreground Overwatch client and physical scan key, copied from the reference method."""
from pathlib import Path

class GameWindow:
    """Capture only the foreground Overwatch client's rectangle, in memory."""
    def __init__(self):
        import ctypes as c
        from ctypes import wintypes as w
        self.c, self.w = c,w
        self.user = c.WinDLL('user32', use_last_error=True)
        self.kernel = c.WinDLL('kernel32', use_last_error=True)
        try:
            self.user.SetProcessDpiAwarenessContext(c.c_void_p(-4))
        except (AttributeError, OSError):
            pass
        self.user.GetForegroundWindow.restype = w.HWND
        self.user.GetWindowThreadProcessId.argtypes = [w.HWND,c.POINTER(w.DWORD)]
        self.user.GetClientRect.argtypes = [w.HWND,c.POINTER(w.RECT)]
        self.user.ClientToScreen.argtypes = [w.HWND,c.POINTER(w.POINT)]
        self.user.IsIconic.argtypes = [w.HWND]
        self.user.GetKeyboardLayout.argtypes = [w.DWORD]
        self.user.GetKeyboardLayout.restype = w.HANDLE
        self.user.MapVirtualKeyExW.argtypes = [w.UINT,w.UINT,w.HANDLE]
        self.user.MapVirtualKeyExW.restype = w.UINT
        self.user.GetAsyncKeyState.argtypes = [c.c_int]
        self.user.GetAsyncKeyState.restype = c.c_short
        self.kernel.OpenProcess.argtypes = [w.DWORD,w.BOOL,w.DWORD]
        self.kernel.OpenProcess.restype = w.HANDLE
        self.kernel.QueryFullProcessImageNameW.argtypes = [w.HANDLE,w.DWORD,w.LPWSTR,c.POINTER(w.DWORD)]
        self.kernel.CloseHandle.argtypes = [w.HANDLE]
        self.cached_hwnd = None
        self.cached_path = ''

    def scan_key_down(self):
        # Scan code 0x29: physical key immediately left of 1, above Tab.
        # Translate using the foreground app's layout, regardless of its printed symbol.
        hwnd = self.user.GetForegroundWindow()
        thread = self.user.GetWindowThreadProcessId(hwnd, None)
        layout = self.user.GetKeyboardLayout(thread)
        key = self.user.MapVirtualKeyExW(0x29, 3, layout)
        return bool(key and self.user.GetAsyncKeyState(key) & 0x8000)

    def rectangle(self):
        c,w = self.c,self.w
        hwnd = self.user.GetForegroundWindow()
        if not hwnd or self.user.IsIconic(hwnd):
            return None
        if hwnd != self.cached_hwnd:
            pid = w.DWORD()
            self.user.GetWindowThreadProcessId(hwnd,c.byref(pid))
            handle = self.kernel.OpenProcess(0x1000,False,pid.value)
            path = c.create_unicode_buffer(32768)
            length = w.DWORD(len(path))
            self.cached_path = ''
            if handle:
                try:
                    if self.kernel.QueryFullProcessImageNameW(handle,0,path,c.byref(length)):
                        self.cached_path = path.value
                finally:
                    self.kernel.CloseHandle(handle)
            self.cached_hwnd = hwnd
        if Path(self.cached_path).name.lower() != 'overwatch.exe':
            return None
        rect, origin = w.RECT(),w.POINT(0,0)
        if not self.user.GetClientRect(hwnd,c.byref(rect)) or not self.user.ClientToScreen(hwnd,c.byref(origin)):
            return None
        width,height = rect.right-rect.left, rect.bottom-rect.top
        if width<640 or height<400:
            return None
        return {'left':origin.x,'top':origin.y,'width':width,'height':height}
