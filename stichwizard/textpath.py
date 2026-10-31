"""Schriftzug entlang eines Pfads (wie Ink/Stitch »Text entlang Pfad«).

Der Pfad ist ein Polygonzug in Objektkoordinaten (mm). Jede Glyphe steht mit ihrer Grundlinie
auf dem Pfad und ist in Pfadrichtung gedreht – die Buchstaben stehen links der Laufrichtung,
bei einem Pfad von links nach rechts also oben drauf. Über das Pfadende hinaus wird gerade
weitergeschrieben.
"""
import bisect
import math

ALIGNS = ("start", "center", "end")


class PathPlacer:
    def __init__(self, pts, flip=False):
        out = []
        for p in pts:
            p = (float(p[0]), float(p[1]))
            if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-6:
                out.append(p)
        if flip:
            out.reverse()
        if len(out) < 2:
            out = [(0.0, 0.0), (1.0, 0.0)] if not out else [out[0], (out[0][0] + 1, out[0][1])]
        self.pts = out
        self.cum = [0.0]
        for a, b in zip(out, out[1:]):
            self.cum.append(self.cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        self.length = self.cum[-1]

    def point(self, s):
        """Punkt bei Bogenlänge s (außerhalb des Pfads geradlinig verlängert)."""
        i = min(max(bisect.bisect_right(self.cum, s) - 1, 0), len(self.pts) - 2)
        a, b = self.pts[i], self.pts[i + 1]
        seg = (self.cum[i + 1] - self.cum[i]) or 1e-9
        t = (s - self.cum[i]) / seg
        return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t

    def start(self, width, align="center"):
        """Bogenlänge, an der ein Schriftzug der Breite `width` beginnt."""
        if align == "end":
            return self.length - width
        if align == "start":
            return 0.0
        return (self.length - width) / 2

    def place(self, s0, s1):
        """Glyphe zwischen den Bogenlängen s0 und s1: (Mitte x, Mitte y, Winkel im Bogenmaß).
        Die Richtung ist die Sehne über die Glyphenbreite – so knicken Buchstaben an Ecken
        nicht weg."""
        ax, ay = self.point(s0)
        bx, by = self.point(s1)
        if math.hypot(bx - ax, by - ay) < 1e-6:
            ax, ay = self.point(s0 - 0.5)
            bx, by = self.point(s1 + 0.5)
        mx, my = self.point((s0 + s1) / 2)
        return mx, my, math.atan2(by - ay, bx - ax)
