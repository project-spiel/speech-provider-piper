import pathlib
from hashlib import sha256
import re
from unidecode import unidecode

SHA256_REGEX = r"oid sha256:(\S+)"
SIZE_REGEX = r"size (\d+)"

MANIFEST_TEMPLATE = """{{
  "app-id": "ai.piper.Speech.Provider.Voice.{escaped_name}",
  "runtime": "ai.piper.Speech.Provider",
  "runtime-version": "master",
  "sdk": "org.gnome.Sdk//45",
  "build-extension": true,
  "modules": [
    {{
      "name": "espeak-ng",
      "buildsystem": "simple",
      "build-commands": [
        "install -d \\"${{FLATPAK_DEST}}/voices\\"",
        "install -m644 *.onnx.json \\"${{FLATPAK_DEST}}/voices\\""
      ],
      "sources": [
        {{
          "type": "file",
          "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/{onnx_json}?download=true",
          "sha256": "{onnx_json_sha256}",
          "dest-filename": "{escaped_name}.onnx.json"
        }},
        {{
          "type": "extra-data",
          "filename": "{escaped_name}.onnx",
          "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/{onnx}?download=true",
          "sha256": "{onnx_sha256}",
          "size": {onnx_size}
        }}
      ]
    }}
  ]
}}
"""

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
    manifest = f"_voices/ai.piper.Speech.Provider.Voice.{escaped_name}.json"
    mf = open(manifest, "w")
    mf.write(
        MANIFEST_TEMPLATE.format(
            name=name,
            escaped_name=escaped_name,
            onnx_json=onnx_json.relative_to("piper-voices"),
            onnx=onnx.relative_to("piper-voices"),
            onnx_json_sha256=onnx_json_sha256,
            onnx_sha256=onnx_sha256,
            onnx_size=onnx_size,
        )
    )
    mf.close()
    print(manifest)

