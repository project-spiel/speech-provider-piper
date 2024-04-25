import pathlib
from hashlib import sha256
import re
from unidecode import unidecode
import urllib.parse
from collections import OrderedDict
import json

SHA256_REGEX = r"oid sha256:(\S+)"
SIZE_REGEX = r"size (\d+)"

METAINFO_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<component type="addon">
  <id>ai.piper.Speech.Provider.Voice.{escaped_name}</id>

  <name>{name}</name>
  <summary>The {name} model for Piper</summary>

  <metadata_license>MIT</metadata_license>
  <project_license>LGPL-3.0-or-later</project_license>

  <extends>
    <id>ai.piper.Speech.Provider</id>
  </extends>

  <description>
    <p>
      The {name} model for Piper
    </p>
  </description>

</component>
'''

MANIFEST_TEMPLATE = """{
  "app-id": "",
  "runtime": "ai.piper.Speech.Provider",
  "runtime-version": "master",
  "sdk": "org.gnome.Sdk//45",
  "build-extension": true,
  "modules": [
    {
      "name": "voice-model",
      "buildsystem": "simple",
      "build-commands": [
        "install -d \\"${FLATPAK_DEST}/voices\\"",
        "install -m644 *.onnx.json \\"${FLATPAK_DEST}/voices\\"",
        "install -Dm644 *.metainfo.xml -t ${FLATPAK_DEST}/share/metainfo/"
      ],
      "sources": []
    }
  ]
}
"""

def create_manifest(name, escaped_name, onnx, onnx_size, onnx_sha256, onnx_json, onnx_json_sha256):
  metainfo = METAINFO_TEMPLATE.format(name=name, escaped_name=escaped_name)
  manifest = json.loads(MANIFEST_TEMPLATE, object_pairs_hook=OrderedDict)
  manifest["app-id"] = f"ai.piper.Speech.Provider.Voice.{escaped_name}"
  model_module = manifest["modules"][0]
  model_module["sources"].append({
          "type": "file",
          "url": f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{onnx_json}?download=true",
          "sha256": onnx_json_sha256,
          "dest-filename": f"{escaped_name}.onnx.json"
        })

  model_module["sources"].append({
          "type": "extra-data",
          "filename": f"{escaped_name}.onnx",
          "url": f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{onnx}?download=true",
          "sha256": onnx_sha256,
          "size": int(onnx_size)
        })
  
  model_module["sources"].append(
        {
          "type": "inline",
          "contents": metainfo,
          "dest-filename": f"ai.piper.Speech.Provider.Voice.{escaped_name}.metainfo.xml"
        }
  )

  fname = f"_voices/ai.piper.Speech.Provider.Voice.{escaped_name}.json"
  mf = open(fname, "w")
  mf.write(json.dumps(manifest, indent=2).replace("\\!", "!"))
  mf.close()
  print(fname)


# GIT_LFS_SKIP_SMUDGE=1 git clone --depth=1 https://huggingface.co/rhasspy/piper-voices

p = pathlib.Path("_voices/")
p.mkdir(parents=True, exist_ok=True)

for onnx_json in pathlib.Path("piper-voices").glob("**/*.onnx.json"):
    with open(onnx_json, "rb") as f:
        onnx_json_sha256 = sha256(f.read()).hexdigest()

    onnx = onnx_json.parent / pathlib.Path(onnx_json.stem)
    with open(onnx, "r") as f:
        onnx_data = f.read()
        onnx_sha256 = re.findall(SHA256_REGEX, onnx_data)[0]
        onnx_size = re.findall(SIZE_REGEX, onnx_data)[0]

    name = onnx.stem
    escaped_name = unidecode(name.replace(" ", "_"))
    onnx_json=urllib.parse.quote(str(onnx_json.relative_to("piper-voices")))
    onnx=urllib.parse.quote(str(onnx.relative_to("piper-voices")))
    create_manifest(name, escaped_name, onnx, onnx_size, onnx_sha256, onnx_json, onnx_json_sha256)

