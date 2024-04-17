# SPDX-License-Identifer: GPL-3.0-or-later

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst, GObject, GLib
from piper import PiperVoice
from pathlib import Path
from dasbus.connection import SessionMessageBus
from dasbus.unix import GLibServerUnix
from dasbus.server.interface import dbus_interface
from dasbus.typing import Variant, UnixFD, Str, Double, Bool, List, Tuple, UInt64
import os
import json
import threading
from time import time

AUTO_EXIT_SECONDS = 120  # Two minute timeout for service

Gst.init(None)


class PiperSynthWorker(GObject.Object):
    _tts_lock = threading.Lock()
    _cached_voice = ("", None)

    def __init__(self, voices_dir):
        super().__init__()
        self.voices_dir = voices_dir
        self._cached_voice = ("", None)

        # create empty pipeline
        self.pipeline = Gst.Pipeline.new("test-pipeline")

        # create the elements
        self.source = None
        self.parse = Gst.ElementFactory.make("rawaudioparse", "parse")
        self.convert = Gst.ElementFactory.make("audioconvert", "convert")
        self.pitch = Gst.ElementFactory.make("pitch", "pitch")
        self.convert2 = Gst.ElementFactory.make("audioconvert", "convert2")
        self.caps_filter = Gst.ElementFactory.make("capsfilter", "audioconvert_filter")
        self.sink = Gst.ElementFactory.make("fdsink", "sink")
        self.sink.set_property("sync", False)

        elements = [
            self.parse,
            self.convert,
            self.pitch,
            self.convert2,
            self.caps_filter,
            self.sink,
        ]

        for el in elements:
            self.pipeline.add(el)

        for index in range(1, len(elements)):
            elements[index - 1].link(elements[index])

        self.parse.set_property("num-channels", 1)
        self.pitch.set_property("pitch", 1)

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::error", self.on_eos_or_end)
        bus.connect("message::eos", self.on_eos_or_end)

    def on_eos_or_end(self, bus, msg):
        if msg.type == Gst.MessageType.ERROR:
            err, dbg = msg.parse_error()
            print("ERROR:", msg.src.get_name(), ":", err.message)
            if dbg:
                print("Debug info:", dbg)

        self._reset_pipeline()

    def _reset_pipeline(self):
        if not self.source:
            return
        rr = os.fdopen(self.source.get_property("fd"), "rb")
        rr.flush()
        rr.close()
        os.close(self.sink.get_property("fd"))

        self.source.set_state(Gst.State.NULL)
        self.source.unlink(self.parse)
        self.pipeline.remove(self.source)
        self.source = None
        self.pitch.set_property("pitch", 1)
        self.pipeline.set_state(Gst.State.READY)
        self.emit("done")

    @GObject.Signal
    def done(self):
        pass

    def _load_voice(self, voice_id):
        with PiperSynthWorker._tts_lock:
            start_time = time()
            _voice_id, voice = PiperSynthWorker._cached_voice
            if not _voice_id or _voice_id != voice_id:
                voice = PiperVoice.load(
                    (self.voices_dir / voice_id).with_suffix(".onnx")
                )
                PiperSynthWorker._cached_voice = (voice_id, voice)

            return voice

    def _synth(self, fd, text, voice_id, rate):
        voice = self._load_voice(voice_id)
        self.parse.set_property("sample-rate", voice.config.sample_rate)
        self.caps_filter.set_property(
            "caps",
            Gst.caps_from_string(
                f"audio/x-raw,format=S16LE,channels=1,rate={voice.config.sample_rate}"
            ),
        )

        length_scale = voice.config.length_scale / rate
        ww = os.fdopen(fd, "wb", buffering=0)
        with PiperSynthWorker._tts_lock:
            audio_stream = voice.synthesize_stream_raw(text, length_scale=length_scale)
            for audio_bytes in audio_stream:
                ww.write(audio_bytes)
        ww.close()

    def synthesize(self, fd, text, voice_id=None, pitch=None, rate=None):
        self.sink.set_property("fd", fd)
        self.source = Gst.ElementFactory.make("fdsrc", "source")
        self.pipeline.add(self.source)
        self.source.link(self.parse)
        self.pitch.set_property("pitch", pitch if pitch is not None else 1)

        r, w = os.pipe()
        self.source.set_property("fd", r)

        x = threading.Thread(target=self._synth, args=(w, text, voice_id, rate))
        x.start()

        self.pipeline.set_state(Gst.State.PLAYING)


@dbus_interface("org.freedesktop.Speech.Provider")
class PiperProvider(object):
    def __init__(self, loop, default_voices_dir):
        self._last_speak_args = [0, "", "", 0, 0, 0]
        self._loop = loop
        if not os.environ.get("KEEP_ALIVE"):
            GLib.timeout_add_seconds(AUTO_EXIT_SECONDS, self._timeout)
        self.voices_dir = Path(os.environ.get("PIPER_VOICES_DIR", default_voices_dir))
        if not self.voices_dir.is_absolute():
            self.voices_dir = Path.cwd() / self.voices_dir
        self._worker_pool = []
        for i in range(5):
            worker = PiperSynthWorker(self.voices_dir)
            worker.connect("done", self._on_done)
            self._worker_pool.append(worker)

    def _timeout(self):
        if len(self._worker_pool) < 5:
            return True
        self._loop.quit()
        return False

    def _on_done(self, worker):
        self._worker_pool.append(worker)

    def Synthesize(
        self,
        fd: UnixFD,
        utterance: Str,
        voice_id: Str,
        pitch: Double,
        rate: Double,
        is_ssml: Bool,
        language: Str,
    ):
        if len(self._worker_pool) > 0:
            worker = self._worker_pool.pop(0)
        else:
            worker = PiperSynthWorker(self.voices_dir)
            worker.connect("done", self._on_done)

        worker.synthesize(fd, utterance, voice_id, pitch, rate)

    @property
    def Name(self) -> Str:
        return "Piper"

    @property
    def Voices(self) -> List[Tuple[Str, Str, Str, UInt64, List[Str]]]:
        voices = []
        for voice_config in self.voices_dir.glob("*.onnx.json"):
            config = json.loads(voice_config.read_text())
            dataset = config["dataset"]
            name_native = config["language"]["name_native"]
            identifier = voice_config.stem[:-5]
            languages = [config["language"]["code"].replace("_", "-")]
            sample_rate = config["audio"]["sample_rate"]
            voices.append(
                (
                    f"{dataset} ({name_native})",
                    identifier,
                    f"audio/x-raw,format=S16LE,channels=1,rate={sample_rate}",
                    0,
                    languages,
                )
            )
        return voices


def main(default_voices_dir):
    mainloop = GLib.MainLoop()
    bus = SessionMessageBus()
    bus.publish_object(
        "/ai/piper/Speech/Provider",
        PiperProvider(mainloop, default_voices_dir),
        server=GLibServerUnix,
    )
    bus.register_service("ai.piper.Speech.Provider")

    mainloop.run()
    return 0
