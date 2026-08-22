import platform
import subprocess

class OsaScriptSingleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OsaScriptSingleton, cls).__new__(cls)
            # Initialize the subprocess when the singleton is first created
            cls._instance.process = subprocess.Popen(['osascript', '-i'], stdin=subprocess.PIPE)
        return cls._instance

    def output(self, message):
        # Format the message command as in the Rust code
        message_cmd = f'tell application "VoiceOver" to output "{message}"\n'.encode('utf-8')
        
        # Write the message command to the subprocess and flush
        self.process.stdin.write(message_cmd)
        self.process.stdin.flush()


# if we are not on darwin, we should import auto from accessible output
if platform.system() != 'Darwin':
    from accessible_output3.outputs import auto
    output = auto.Auto()
else:
    output = OsaScriptSingleton()

