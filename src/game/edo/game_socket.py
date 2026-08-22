import socket
import struct
import io

class GameSocket:
    """Class to handle the game socket and sending/receiving messages."""

    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.buf = io.BytesIO()

    def connect(self, host, port, timeout=2):
        self.socket.settimeout(timeout)  # Set timeout for connection attempt
        try:
            self.socket.connect((host, port))
        except socket.timeout:
            raise Exception("Connection timed out after {} seconds".format(timeout))
        except Exception as e:
            raise Exception("Failed to connect due to: {}".format(e))
        self.socket.settimeout(None)  # Disable timeout for subsequent operations
    
    def disconnect(self):
        return self.socket.close()
        
    def send(self, id, msg=b''):
        header = struct.pack('hB', len(msg)+1, id)
        self.socket.sendall(header+msg)

    def recv(self):
        """Receive one message and return the id, the length and the data."""
        def message_in_buffer():
            t = self.buf.tell()
            return t > 2 and t > struct.unpack('h', self.buf.getvalue()[:2])[0] + 1
        while not message_in_buffer():
            data = self.socket.recv(8192)
            if not data:
                return None, None, None
            self.buf.write(data)
        # We have at least one complete packet
        length = struct.unpack('h', self.buf.getvalue()[:2])[0]
        data = self.buf.getvalue()
        # length is in data 0 and 1 (2 bytes)
        length = struct.unpack('h', data[:2])[0]
        id = data[2]
        packet_data = data[3:length+2]
        extra = data[length+2:]
        length = length -1 # subtract 1 for the id byte
        self.buf.truncate(0)
        self.buf.seek(0)
        self.buf.write(extra)
        return id, length, packet_data
