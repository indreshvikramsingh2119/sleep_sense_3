"""Runtime application version helpers."""

import ctypes
import os
import sys


APP_VERSION = "3.1.1"


def _windows_executable_version(executable_path):
    """Read ProductVersion from the running EXE's Windows version resource."""
    if os.name != "nt" or not executable_path:
        return None
    try:
        version_api = ctypes.WinDLL("version", use_last_error=True)
        dword = ctypes.c_uint32
        size_fn = version_api.GetFileVersionInfoSizeW
        size_fn.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(dword)]
        size_fn.restype = dword
        read_fn = version_api.GetFileVersionInfoW
        read_fn.argtypes = [ctypes.c_wchar_p, dword, dword, ctypes.c_void_p]
        read_fn.restype = ctypes.c_int
        query_fn = version_api.VerQueryValueW
        query_fn.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p,
                             ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(dword)]
        query_fn.restype = ctypes.c_int

        ignored = dword(0)
        size = size_fn(executable_path, ctypes.byref(ignored))
        if not size:
            return None
        resource = ctypes.create_string_buffer(size)
        resource_ptr = ctypes.cast(resource, ctypes.c_void_p)
        if not read_fn(executable_path, 0, size, resource_ptr):
            return None

        translations_ptr = ctypes.c_void_p()
        translations_len = dword(0)
        if query_fn(resource_ptr, "\\VarFileInfo\\Translation",
                    ctypes.byref(translations_ptr), ctypes.byref(translations_len)):
            translations = ctypes.cast(
                translations_ptr, ctypes.POINTER(ctypes.c_uint16)
            )
            language, codepage = translations[0], translations[1]
            for field in ("ProductVersion", "FileVersion"):
                query = f"\\StringFileInfo\\{language:04x}{codepage:04x}\\{field}"
                value_ptr = ctypes.c_void_p()
                value_len = dword(0)
                if query_fn(resource_ptr, query, ctypes.byref(value_ptr), ctypes.byref(value_len)):
                    value = ctypes.cast(value_ptr, ctypes.c_wchar_p).value
                    if value and value.strip():
                        return value.strip()
    except Exception:
        return None
    return None


def get_software_version():
    """Return this build's EXE version, with a source-build fallback."""
    if getattr(sys, "frozen", False):
        version = _windows_executable_version(sys.executable)
        if version:
            return version
    return APP_VERSION
