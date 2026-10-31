"""Test (1.31): Simulationsvideo (MP4 über ffmpeg, Einzelbilder ohne ffmpeg, Abbrechen) und
An Maschine senden (Format aus dem Maschinenprofil, Zielordner, Arbeitsblatt, Dateinamen,
USB-Erkennung)."""
import os
import subprocess
import sys
sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
OUT = sys.argv[1]
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
app = QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("StickStudio")
QMessageBox.information = staticmethod(lambda *a, **k: None)
import pyembroidery as pe
from stichwizard import machinesend, templates, video
from stichwizard.mainwindow import MainWindow
from stichwizard.model import Document
ok = []
def check(n, c): ok.append(bool(c)); print("✓" if c else "✗", n)
w = MainWindow(); w.resize(1440, 900); w.show(); QTest.qWait(100)
w.doc.objects = templates.build("emblem"); w.sync_items(); w.commit()

# ---- Video
opts = {"seconds": 3.0, "size": "640x360", "fps": 25, "hoop": True, "info": True}
mp4 = os.path.join(OUT, "sim.mp4")
if video.ffmpeg():
    p = w.export_sim_video(mp4, opts)
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
                            "-show_entries", "stream=width,height,nb_read_frames", "-of", "csv=p=0",
                            mp4], capture_output=True, text=True).stdout.strip()
    check(f"MP4 geschrieben: 640×360, 3 s + 2 s Standbild = 125 Bilder ({probe})",
          p == mp4 and probe == "640,360,125")
else:
    print("(ffmpeg fehlt – MP4-Test übersprungen)")
d = Document(); d.objects = w.doc.objects
first = video._Frames(d, (640, 360))
first.advance(1)
img0 = first.frame()
last = video.final_image(d, (640, 360))
diff = sum(1 for x in range(0, 640, 8) for y in range(0, 300, 8)
           if img0.pixelColor(x, y) != last.pixelColor(x, y))
check(f"Design entsteht im Video (Anfang ≠ Ende, {diff} Punkte verschieden)", diff > 100)
fr = video._Frames(d, (640, 360))
fr.advance(fr.total)
check("Am Ende alle Stiche gezeichnet", fr.stitched == fr.stitches and fr.done == fr.total)
calls = []
def cancel(f):
    calls.append(f)
    return len(calls) < 5
try:
    video.export_video(d, os.path.join(OUT, "abbruch.mp4"), 3, (320, 180), 25, progress=cancel)
    aborted = False
except InterruptedError:
    aborted = True
check("Abbrechen löscht die halbe Datei", not video.ffmpeg() or
      (aborted and not os.path.exists(os.path.join(OUT, "abbruch.mp4"))))
orig = video.ffmpeg
video.ffmpeg = lambda: None
frames = os.path.join(OUT, "bilder")
p = w.export_sim_video(frames, dict(opts, seconds=1.0))
video.ffmpeg = orig
pngs = sorted(f for f in os.listdir(frames) if f.endswith(".png"))
check(f"Ohne ffmpeg: Einzelbilder ({len(pngs)})", p == frames and len(pngs) == 10)

# ---- Senden
check("Dateinamen ohne Umlaute/Leerzeichen", machinesend.safe_name("Mein Ärmel-Design!") ==
      "Mein_Aermel-Design" and machinesend.safe_name("Mein Ärmel", True) == "MEIN_AER")
drives = machinesend.removable_drives()
check(f"USB-Erkennung läuft ({len(drives)} gefunden)", isinstance(drives, list))
# nachgebautes /sys: sdb = USB-Stick, sda = interne Platte
fake = os.path.join(OUT, "sys")
for disk, rem, bus in (("sdb", "1", "usb1/1-2"), ("sda", "0", "ata2/host1")):
    real = os.path.join(fake, "devices", bus, disk)
    os.makedirs(os.path.join(real, disk + "1"))
    open(os.path.join(real, "removable"), "w").write(rem + "\n")
    open(os.path.join(real, disk + "1", "partition"), "w").write("1\n")
    os.makedirs(os.path.join(fake, "block"), exist_ok=True)
    os.makedirs(os.path.join(fake, "class", "block"), exist_ok=True)
    os.symlink(real, os.path.join(fake, "block", disk))
    os.symlink(os.path.join(real, disk + "1"), os.path.join(fake, "class", "block", disk + "1"))
check("USB-Stick wird als Wechseldatenträger erkannt", machinesend.is_removable("/dev/sdb1", fake))
check("Interne Platte nie (kein Auswerfen, nicht in der Liste)",
      not machinesend.is_removable("/dev/sda1", fake))
usb = os.path.join(OUT, "usb")
os.makedirs(usb)
def choose(dlg):
    dlg.add_path(usb)
    dlg.name.setText("Emblem")
    dlg.sheet.setChecked(True)
    return True
check("Ohne Maschine: Senden mit dem letzten Exportformat", w.machine() is None and
      w.send_to_machine(lambda dlg: (dlg.add_path(usb), True)[1]).endswith(".pes"))
w.set_machine("texi_iris10")
path = w.send_to_machine(choose)
fmt = w.machine()["format"]
check(f"Gesendet im Format der Maschine (TEXI IRIS 10: .{fmt})",
      fmt == "dst" and path == os.path.join(usb, f"Emblem.{fmt}") and os.path.getsize(path) > 500)
pat = pe.read(path)
check("Datei lesbar, Stiche vollständig", sum(1 for s in pat.stitches if s[2] == pe.STITCH) >=
      w.doc.stats()["stitches"] * 0.95)
check("Arbeitsblatt mitkopiert", os.path.exists(os.path.join(usb, "Emblem.pdf")))
check("Zielordner wird gemerkt", usb in (w.settings.value("sendFolders", []) or []))
def choose2(dlg):
    i = next(i for i in range(dlg.list.count()) if dlg.list.item(i).data(0x0100)[0] == usb)
    dlg.list.setCurrentRow(i)
    dlg.fmt.setCurrentIndex(dlg.fmt.findData("jef"))
    dlg.short.setChecked(True)
    return True
path2 = w.send_to_machine(choose2)
check(f"Gemerkter Ordner, anderes Format, kurzer Name ({os.path.basename(path2)})",
      os.path.basename(path2) == "DESIGN.jef" and os.path.exists(path2))
check("Abbrechen sendet nichts", w.send_to_machine(lambda dlg: False) is None)
QTest.qWait(50)      # Qt meldet nach dem ersten Bild im PDF einmal »LanguageChange«
dlg = machinesend.SendDialog(w, w.machine(), "Test", [])
dlg.show(); QTest.qWait(100)
check("Knopf heißt »Senden« und ist ohne Ziel gesperrt",
      dlg.ok_btn.text() == "Senden" and (dlg.list.count() > 0 or not dlg.ok_btn.isEnabled()))
dlg.grab().save(os.path.join(OUT, "senden.png")); dlg.close()
print(f"\n{sum(ok)}/{len(ok)} bestanden")
sys.exit(0 if all(ok) else 1)
