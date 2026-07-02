#!/usr/bin/env bash
# Quick manual test of the CompreFace recognition engine (Slice 2).
# Usage:  ./scripts/recognize.sh <path-to-image.jpg>
# Hits the built-in Demo service (pre-loaded with celebrity faces + any subjects
# we enrolled) and prints the top matches per detected face.
set -euo pipefail

IMG="${1:-}"
KEY="${COMPREFACE_KEY:-00000000-0000-0000-0000-000000000002}"
URL="${COMPREFACE_URL:-http://localhost:8900}/api/v1/recognition/recognize"

if [[ -z "$IMG" || ! -f "$IMG" ]]; then
  echo "usage: $0 <path-to-image.(jpg|png)>" >&2
  exit 1
fi

curl -sS -X POST "$URL?limit=10&prediction_count=5&face_plugins=age,gender" \
  -H "x-api-key: $KEY" -F "file=@$IMG" -o /tmp/cf_recognize.json

python3 - "$IMG" <<'PY'
import json, sys
img = sys.argv[1]
d = json.load(open("/tmp/cf_recognize.json"))
res = d.get("result")
if res is None:
    print("Error / no result:", json.dumps(d, indent=2)); sys.exit(1)
if not res:
    print("No face detected in", img); sys.exit(0)
print(f"\n{len(res)} face(s) detected in {img}\n" + "-"*44)
for i, face in enumerate(res):
    box = face.get("box", {})
    prob = box.get("probability")
    hdr = f"Face #{i}"
    if prob is not None: hdr += f"  (detection conf {prob:.2f})"
    print(hdr)
    for s in face.get("subjects", [])[:5]:
        print(f"    {s['similarity']*100:5.1f}%  {s['subject']}")
    print()
PY
