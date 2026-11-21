"""Windows build step: put ARM's astcenc (Apache-2.0, https://github.com/ARM-software/astc-encoder) at bin/astcenc.exe."""
import hashlib
import io
import os
import time
import urllib.request
import zipfile

VERSION = "5.7.0"
URL = f"https://github.com/ARM-software/astc-encoder/releases/download/{VERSION}/astcenc-{VERSION}-windows-x64.zip"
SHA256 = "cbde7c78adcc90d0d90ecf10f32d03f3340fbe1720cb6d6c892147d625e74d2d"  # from the release's release-sha256.txt

for attempt in range(1, 6):  # GitHub's download servers now and then answer 504
    try:
        data = urllib.request.urlopen(URL, timeout=120).read()
        break
    except OSError as error:
        print(f"download failed ({error}), try {attempt}/5")
        if attempt == 5:
            raise
        time.sleep(15 * attempt)
if hashlib.sha256(data).hexdigest() != SHA256:
    raise SystemExit("astcenc download does not match its checksum")
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bin", "astcenc.exe")
with zipfile.ZipFile(io.BytesIO(data)) as z, open(out, "wb") as f:
    f.write(z.read("bin/astcenc-avx2.exe"))
print("bin/astcenc.exe ready")
