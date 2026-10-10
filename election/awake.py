"""election/awake.py - asks the computer not to go to sleep while Election Night's updater runs.

The request belongs to the running program and ends with it, however it ends (Stop, Ctrl+C, closing the window, a
crash): nothing is written to the computer's settings and nothing needs undoing. The screen may still turn off; only
sleep is held off. Closing a laptop's lid or pressing its power button still puts it to sleep, so on the night the
computer stays plugged in with the lid open.

  Windows   a power request ("system required", with the reason shown by `powercfg /requests` in an administrator's
            window) and the older thread request beside it (SetThreadExecutionState), both released on exit
  macOS     `caffeinate -i -w <this program's id>`, which ends when the program does
  others    nothing is asked; the updater says so

    from election.awake import Awake
    with Awake("Election Night is reading and publishing results") as a:
        print(a.how)          # what was asked, in plain words
"""

import ctypes
import os
import subprocess
import sys

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
POWER_REQUEST_CONTEXT_VERSION = 0
POWER_REQUEST_CONTEXT_SIMPLE_STRING = 0x1
POWER_REQUEST_SYSTEM_REQUIRED = 1


class _Reason(ctypes.Structure):
    _fields_ = [("Version", ctypes.c_ulong), ("Flags", ctypes.c_ulong), ("SimpleReasonString", ctypes.c_wchar_p)]


class Awake:
    def __init__(self, reason="Election Night is reading and publishing results"):
        self.reason = reason
        self.ok = False
        self.how = "not asked yet"
        self._handle = None
        self._thread_flags = False
        self._proc = None
        self._reason_buf = None

    # ------------------------------------------------------------------ asking
    def start(self):
        if os.name == "nt":
            self._start_windows()
        elif sys.platform == "darwin":
            self._start_mac()
        else:
            self.how = "this computer offers no way to ask (only Windows and macOS are set up): keep it from sleeping by hand"
        return self

    def _start_windows(self):
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        got = []
        try:
            k32.PowerCreateRequest.restype = ctypes.c_void_p
            k32.PowerCreateRequest.argtypes = [ctypes.POINTER(_Reason)]
            k32.PowerSetRequest.argtypes = [ctypes.c_void_p, ctypes.c_int]
            k32.PowerSetRequest.restype = ctypes.c_int
            self._reason_buf = _Reason(POWER_REQUEST_CONTEXT_VERSION, POWER_REQUEST_CONTEXT_SIMPLE_STRING, self.reason)
            h = k32.PowerCreateRequest(ctypes.byref(self._reason_buf))
            if h and h != ctypes.c_void_p(-1).value and k32.PowerSetRequest(h, POWER_REQUEST_SYSTEM_REQUIRED):
                self._handle = h
                got.append("a power request")
        except (AttributeError, OSError):
            pass
        try:
            k32.SetThreadExecutionState.restype = ctypes.c_uint32
            k32.SetThreadExecutionState.argtypes = [ctypes.c_uint32]
            if k32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED):
                self._thread_flags = True
                got.append("the program's own request")
        except (AttributeError, OSError):
            pass
        self.ok = bool(got)
        self.how = ("Windows was asked not to sleep while this runs (" + " and ".join(got) + "); the request ends with the program"
                    if got else "Windows did not accept the request; set the computer not to sleep by hand")

    def _start_mac(self):
        try:
            self._proc = subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.ok = True
            self.how = "macOS was asked not to sleep while this runs (caffeinate); the request ends with the program"
        except OSError:
            self.how = "caffeinate is not available; keep the computer from sleeping by hand"

    # ------------------------------------------------------------------ checking
    def check(self):
        """(held, detail): whether this program's request is still in place, read back without changing it."""
        if os.name != "nt":
            if self._proc is not None:
                return self._proc.poll() is None, "caffeinate is running" if self._proc.poll() is None else "caffeinate has ended"
            return False, self.how
        k32 = ctypes.WinDLL("kernel32")
        k32.SetThreadExecutionState.restype = ctypes.c_uint32
        k32.SetThreadExecutionState.argtypes = [ctypes.c_uint32]
        held = []
        if self._thread_flags:
            # SetThreadExecutionState answers with the flags it replaces: asking again for the same flags reads them back
            prev = k32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
            if prev & ES_SYSTEM_REQUIRED and prev & ES_CONTINUOUS:
                held.append("the program's own request reads back as held")
        if self._handle:
            held.append("the power request is open")
        return bool(held), "; ".join(held) or "no request in place"

    # ------------------------------------------------------------------ letting go
    def stop(self):
        if os.name == "nt":
            k32 = ctypes.WinDLL("kernel32")
            if self._handle:
                try:
                    k32.PowerClearRequest.argtypes = [ctypes.c_void_p, ctypes.c_int]
                    k32.PowerClearRequest(self._handle, POWER_REQUEST_SYSTEM_REQUIRED)
                    k32.CloseHandle.argtypes = [ctypes.c_void_p]
                    k32.CloseHandle(self._handle)
                except (AttributeError, OSError):
                    pass
                self._handle = None
            if self._thread_flags:
                try:
                    k32.SetThreadExecutionState.argtypes = [ctypes.c_uint32]
                    k32.SetThreadExecutionState(ES_CONTINUOUS)
                except (AttributeError, OSError):
                    pass
                self._thread_flags = False
        if self._proc is not None:
            try:
                self._proc.terminate()
            except OSError:
                pass
            self._proc = None
        self.ok = False

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()
        return False


def selftest(say=print):
    """Asks, reads the request back, lets go and reads it back again. Changes no setting."""
    a = Awake("Election Night self-test").start()
    held, detail = a.check()
    a.stop()
    after, _d = a.check()
    ok = (held and not after) if os.name == "nt" else True
    say(f"    stay awake: {a.how.split(';')[0]}; read back: {detail}; after letting go: {'released' if not after else 'still held'}")
    return ok


if __name__ == "__main__":
    sys.exit(0 if selftest() else 1)
