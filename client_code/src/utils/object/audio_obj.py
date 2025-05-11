# Audio init
import pyaudio

class AudioIn:
    def __init__(self, chunk=2048):
        self.chunk = chunk
        self.__sample_format = pyaudio.paInt16
        self.channels = 1
        self.fs = 44100
        self.__pyaudio = pyaudio.PyAudio()

    def __enter__(self):
        self.__audio = self.__pyaudio.open(format=self.__sample_format, channels=self.channels, rate=self.fs, frames_per_buffer=self.chunk, input=True)
        return self

    def get(self) -> bytes | None:
        try:
            sound = self.__audio.read(self.chunk)
            return sound
        except IOError:
            sound = b''
            return sound

    def __exit__(self, type, value, traceback):
        if not self.__audio.is_stopped():
            self.__audio.stop_stream()
            self.__audio.close()
            self.__pyaudio.terminate()

class AudioOut:
    def __init__(self, chunk=2048):
        self.chunk = chunk
        self.__sample_format = pyaudio.paInt16
        self.channels = 1
        self.fs = 44100
        self.__pyaudio = pyaudio.PyAudio()

    def __enter__(self):
        self.__audio = self.__pyaudio.open(format=self.__sample_format, channels=self.channels, rate=self.fs, frames_per_buffer=self.chunk, output=True)
        return self

    def play(self, sound):
        self.__audio.write(sound)

    def __exit__(self, type, value, traceback):
        if not self.__audio.is_stopped():
            self.__audio.stop_stream()
            self.__audio.close()
            self.__pyaudio.terminate()
