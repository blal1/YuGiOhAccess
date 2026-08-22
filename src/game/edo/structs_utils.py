import ctypes
import struct

PASS_NAME_MAX_LENGTH = 20
NOTES_MAX_LENGTH = 200
CHAT_MSG_MAX_LENGTH = 256

def string_to_u16(s, len):
    data = struct.pack(f"{len*2}s", s.encode('utf-16-le'))
    obj = (ctypes.c_uint16 * len).from_buffer_copy(data)
    return obj

def u16_to_string(a):
    s = bytes(a).decode('utf-16-le')
    if (i := s.find('\0')) > -1:
        s = s[:i]
    return s



