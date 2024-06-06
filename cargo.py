#!/usr/bin/env python3

import sys
import subprocess
import os
import shutil

env = os.environ

(MESON_BUILD_ROOT, MESON_SOURCE_ROOT, OUTPUT, APP_BIN, VOICES_DIR, OFFLINE) = sys.argv[1:]

CARGO_TARGET_DIR = os.path.join (MESON_BUILD_ROOT, "target")
env["CARGO_TARGET_DIR"] = CARGO_TARGET_DIR
env["VOICES_DIR"] = VOICES_DIR

CMD = ['cargo', 'build', '--release', '--manifest-path', os.path.join(MESON_SOURCE_ROOT, 'Cargo.toml')]
if len(OFFLINE) > 0:
    CMD += [OFFLINE]

subprocess.run(CMD, env=env)
shutil.copy2(os.path.join(CARGO_TARGET_DIR, 'release', APP_BIN), OUTPUT)