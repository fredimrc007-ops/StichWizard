"""Maschinenprofile: ein Klick stellt Rahmen, Exportformat, Stickgeschwindigkeit, Stopps und
Nadelempfehlung passend zur Stickmaschine ein.

Angaben laut Hersteller/Händler – was nicht sicher bekannt ist, steht als »laut Handbuch« da.
Eigene Maschinen speichert StichWizard in den Einstellungen (»custom_machines«).
"""

NEUTRAL = "none"

# id, Name, Nadeln, max. Stickfeld (B × H mm), Rahmen [(Name, B, H)], Standardrahmen (B, H),
# Format, max. Tempo, Tempo für die Zeitschätzung, Nadelsystem, automatischer Farbwechsel,
# Fadenschneider, Hinweise
MACHINES = [
    dict(id="texi_iris10", name="TEXI IRIS 10", needles=10, field=(310, 210),
         hoops=[("Texi oval", 70, 50), ("Texi", 110, 110), ("Texi", 190, 140), ("Texi", 310, 210)],
         default_hoop=(190, 140), format="dst", speed_max=1200, speed=800,
         needle_system="DBxK5", auto_color=True, trimmer=True,
         note="10 Nadeln, Stickfeld bis 310 × 210 mm, Tajima-Formate (DST). Kappenrahmen: "
              "Maß des Stickfelds im Handbuch nachsehen und als eigenen Rahmen mit »Kappe« im "
              "Namen anlegen."),
    dict(id="brother_pr1055x", name="Brother PR1055X", needles=10, field=(360, 200),
         hoops=[("Brother", 100, 100), ("Brother", 180, 130), ("Brother", 300, 200),
                ("Brother", 360, 200)],
         default_hoop=(180, 130), format="pes", speed_max=1000, speed=750,
         needle_system="laut Handbuch", auto_color=True, trimmer=True,
         note="10 Nadeln, Stickfeld bis 360 × 200 mm, PES (auch DST)."),
    dict(id="brother_pr680w", name="Brother PR680W", needles=6, field=(300, 200),
         hoops=[("Brother", 100, 100), ("Brother", 180, 130), ("Brother", 300, 200)],
         default_hoop=(180, 130), format="pes", speed_max=1000, speed=750,
         needle_system="laut Handbuch", auto_color=True, trimmer=True,
         note="6 Nadeln, Stickfeld bis 300 × 200 mm, PES (auch DST)."),
    dict(id="brother_800e", name="Brother Innov-is 800E", needles=1, field=(260, 160),
         hoops=[("Brother", 100, 100), ("Brother", 260, 160)],
         default_hoop=(260, 160), format="pes", speed_max=850, speed=650,
         needle_system="130/705 H-E (Sticknadel)", auto_color=False, trimmer=True,
         note="Einnadel-Stickmaschine, Stickfeld bis 260 × 160 mm, PES. Hält bei jedem "
              "Farbwechsel an."),
    dict(id="janome_mb7", name="Janome MB-7", needles=7, field=(240, 200),
         hoops=[("Janome", 126, 110), ("Janome", 240, 200)],
         default_hoop=(126, 110), format="jef", speed_max=800, speed=650,
         needle_system="laut Handbuch", auto_color=True, trimmer=True,
         note="7 Nadeln, Stickfeld bis 240 × 200 mm, JEF."),
    dict(id="generic_multi", name="Mehrnadel-Maschine (Tajima-kompatibel)", needles=12,
         field=(400, 300), hoops=[], default_hoop=None, format="dst", speed_max=1200, speed=800,
         needle_system="DBxK5", auto_color=True, trimmer=True,
         note="Allgemeines Profil für Mehrnadel-Maschinen mit DST (Tajima, Ricoma, SWF, Happy, "
              "ZSK …). Nadelzahl und Stickfeld bei Bedarf als eigene Maschine anpassen."),
    dict(id="generic_home", name="Einnadel-Haushaltsmaschine", needles=1, field=(260, 160),
         hoops=[], default_hoop=None, format="pes", speed_max=850, speed=600,
         needle_system="130/705 H-E (Sticknadel)", auto_color=False, trimmer=False,
         note="Allgemeines Profil für Haushalts-Stickmaschinen mit einer Nadel. Format bei Bedarf "
              "ändern (Janome JEF, Pfaff/Husqvarna VP3, Bernina EXP, Singer XXX)."),
]

# Nadelgröße und Spitze je Stoffart (gilt für alle Nadelsysteme)
FABRIC_NEEDLES = {
    "standard": ("75/11", "Rundspitze (R)"),
    "jersey": ("75/11", "Kugelspitze (SES) – zerschneidet keine Maschen"),
    "pique": ("75/11", "Kugelspitze (SES)"),
    "towel": ("80/12", "Rundspitze (R)"),
    "fleece": ("75/11", "Kugelspitze (SES)"),
    "denim": ("90/14", "Rundspitze, verstärkt (Titan)"),
    "cap": ("80/12", "Rundspitze, Titan – für Steifeinlage und Schaum"),
    "leather": ("80/12", "Leder-Schneidspitze (LR) – wenige Einstiche!"),
    "silk": ("65/9", "feine Rundspitze (SPI)"),
}


def all_machines(custom=None):
    """Feste Profile + eigene Maschinen aus den Einstellungen."""
    out = list(MACHINES)
    for m in custom or []:
        if isinstance(m, dict) and m.get("id") and m.get("name"):
            out.append(dict(_CUSTOM_DEFAULTS, **m))
    return out


_CUSTOM_DEFAULTS = dict(needles=1, field=(260, 160), hoops=[], default_hoop=None, format="dst",
                        speed_max=1000, speed=700, needle_system="laut Handbuch", auto_color=False,
                        trimmer=True, note="Eigene Maschine.")


def get(machine_id, custom=None):
    if not machine_id or machine_id == NEUTRAL:
        return None
    return next((m for m in all_machines(custom) if m["id"] == machine_id), None)


def needle_for(machine, fabric_type):
    """Empfohlene Nadel als Text, z. B. »DBxK5 75/11, Kugelspitze (SES)«."""
    size, point = FABRIC_NEEDLES.get(fabric_type, FABRIC_NEEDLES["standard"])
    system = (machine or {}).get("needle_system", "")
    prefix = f"{system} " if system and not system.startswith("laut") else ""
    return f"{prefix}{size}, {point}"


def needle_plan(blocks, machine, stops=None):
    """Nadelbelegung für Mehrnadel-Maschinen.

    blocks: [(farbe, stiche)] wie doc.machine_blocks(); stops: Menge der Blocknummern, nach
    denen die Maschine anhalten soll. Gleiche Farben bekommen dieselbe Nadel.
    Liefert (schritte, nadeln, zu_viele): schritte = [(nr, nadel, farbe, stopp_danach)],
    nadeln = {farbe: nadel}, zu_viele = True, wenn mehr Farben als Nadeln.
    """
    n = max(1, int((machine or {}).get("needles", 1)))
    needles, steps = {}, []
    for i, (color, _) in enumerate(blocks):
        key = color.upper()
        if key not in needles:
            needles[key] = (len(needles) % n) + 1
        steps.append((i + 1, needles[key], color, bool(stops and i in stops)))
    return steps, needles, len(needles) > n
