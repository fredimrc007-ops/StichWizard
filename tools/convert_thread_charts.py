"""Wandelt die Ink/Stitch-Garnkarten (GIMP-.gpl) in stichwizard/threadcharts.json.gz um."""
import glob
import gzip
import json
import os
import re
import sys

src, dest = sys.argv[1], sys.argv[2]
charts = {}
for path in sorted(glob.glob(os.path.join(src, "*.gpl"))):
    name = os.path.basename(path)[:-4].replace("InkStitch ", "")
    rows = []
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*(\d+)\s+(\d+)\s+(\d+)\s+(.*)$", line)
        if not m:
            continue
        r, g, b, rest = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4).strip()
        parts = rest.rsplit(None, 1)
        if len(parts) == 2 and re.search(r"\d", parts[1]):
            cname, number = parts[0].strip(), parts[1]
        else:
            cname, number = rest, ""
        rows.append([cname, number, "#%02X%02X%02X" % (r, g, b)])
    if rows:
        charts[name] = rows
with gzip.open(dest, "wt", encoding="utf-8") as f:
    json.dump(charts, f, ensure_ascii=False, separators=(",", ":"))
print(len(charts), "Garnkarten,", sum(len(v) for v in charts.values()), "Farben")
