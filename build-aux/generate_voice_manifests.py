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

  <requires>
    <id>ai.piper.Speech.Provider</id>
  </requires>

  <description>
    <p>
      The {name} model for Piper
    </p>
  </description>

  <languages>
    <lang percentage="100">{lang}</lang>
  </languages>

</component>
'''

MANIFEST_TEMPLATE = """{
  "id": "",
  "branch": "1.0",
  "runtime": "ai.piper.Speech.Provider",
  "runtime-version": "master",
  "sdk": "org.freedesktop.Sdk//25.08",
  "build-extension": true,
  "modules": [
    {
      "name": "voice-model",
      "buildsystem": "simple",
      "build-commands": [
        "install -Dm644 *.metainfo.xml -t ${FLATPAK_DEST}/share/metainfo/",
        "install -D apply_extra -t ${FLATPAK_DEST}/bin"
      ],
      "sources": []
    }
  ]
}
"""

def create_manifest(name, escaped_name, onnx, onnx_size, onnx_sha256, onnx_json, onnx_json_size, onnx_json_sha256):
  lang = re.match(r"^(\w\w_\w\w)-", name).groups()[0]
  metainfo = METAINFO_TEMPLATE.format(name=name, escaped_name=escaped_name, lang=lang)
  manifest = json.loads(MANIFEST_TEMPLATE, object_pairs_hook=OrderedDict)
  manifest["app-id"] = f"ai.piper.Speech.Provider.Voice.{escaped_name}"
  model_module = manifest["modules"][0]

  model_module["sources"].append({
          "type": "script",
          "dest-filename": "apply_extra",
          "commands": [
              f"mkdir {escaped_name}",
              f"mv {escaped_name}.onnx.json {escaped_name}",
              f"mv {escaped_name}.onnx {escaped_name}"
          ]
        })

  model_module["sources"].append({
          "type": "extra-data",
          "filename": f"{escaped_name}.onnx.json",
          "url": f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{onnx_json}?download=true",
          "sha256": onnx_json_sha256,
          "size": onnx_json_size
        })

  model_module["sources"].append({
          "type": "extra-data",
          "filename": f"{escaped_name}.onnx",
          "url": f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{onnx}?download=true",
          "sha256": onnx_sha256,
          "size": onnx_size
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
  mf.write(json.dumps(manifest, indent=2))
  mf.close()
  print(fname)

def create_rt_manifest(name, escaped_name, tarball, tarball_size, tarball_sha256):
  lang = re.match(r"^(\w\w_\w\w)-", name).groups()[0]
  metainfo = METAINFO_TEMPLATE.format(name=name, escaped_name=escaped_name, lang=lang)
  manifest = json.loads(MANIFEST_TEMPLATE, object_pairs_hook=OrderedDict)
  manifest["app-id"] = f"ai.piper.Speech.Provider.Voice.{escaped_name}"
  model_module = manifest["modules"][0]

  model_module["sources"].append({
        "type": "script",
        "dest-filename": "apply_extra",
        "commands": [
            f"mkdir {escaped_name}",
            f"tar -xf {escaped_name}.tar -C {escaped_name}",
            f"rm {escaped_name}.tar"
        ]
      })

  model_module["sources"].append({
          "type": "extra-data",
          "filename": f"{escaped_name}.tar",
          "url": f"https://huggingface.co/datasets/mush42/piper-rt/resolve/main/{tarball}?download=true",
          "sha256": tarball_sha256,
          "size": tarball_size
        })
  
  model_module["sources"].append({
          "type": "inline",
          "contents": metainfo,
          "dest-filename": f"ai.piper.Speech.Provider.Voice.{escaped_name}.metainfo.xml"
        })

  fname = f"_voices/ai.piper.Speech.Provider.Voice.{escaped_name}.json"
  mf = open(fname, "w")
  mf.write(json.dumps(manifest, indent=2))
  mf.close()
  print(fname)

# GIT_LFS_SKIP_SMUDGE=1 git clone --depth=1 https://huggingface.co/rhasspy/piper-voices

p = pathlib.Path("_voices/")
p.mkdir(parents=True, exist_ok=True)

for onnx_json in pathlib.Path("piper-voices").glob("**/*.onnx.json"):
    with open(onnx_json, "rb") as f:
        data = f.read()
        onnx_json_size = len(data)
        onnx_json_sha256 = sha256(data).hexdigest()

    onnx = onnx_json.parent / pathlib.Path(onnx_json.stem)
    with open(onnx, "r") as f:
        onnx_data = f.read()
        onnx_sha256 = re.findall(SHA256_REGEX, onnx_data)[0]
        onnx_size = int(re.findall(SIZE_REGEX, onnx_data)[0])

    name = onnx.stem
    escaped_name = unidecode(name.replace(" ", "_"))
    onnx_json=urllib.parse.quote(str(onnx_json.relative_to("piper-voices")))
    onnx=urllib.parse.quote(str(onnx.relative_to("piper-voices")))
    create_manifest(name, escaped_name, onnx, onnx_size, onnx_sha256, onnx_json, onnx_json_size, onnx_json_sha256)

# GIT_LFS_SKIP_SMUDGE=1 git clone --depth=1 https://huggingface.co/datasets/mush42/piper-rt.git

for tarball in pathlib.Path("piper-rt").glob("*.tar.gz"):
  with open(tarball, "r") as f:
      tarball_data = f.read()
      tarball_sha256 = re.findall(SHA256_REGEX, tarball_data)[0]
      tarball_size = int(re.findall(SIZE_REGEX, tarball_data)[0])
  name = pathlib.Path(tarball.stem).stem
  escaped_name = unidecode(name.replace(" ", "_").replace("+", "_"))
  create_rt_manifest(name, escaped_name, urllib.parse.quote(tarball.name), tarball_size, tarball_sha256)
