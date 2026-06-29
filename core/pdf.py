"""
pdf.py — Printable "SCHEDA DISPOSIZIONI" sheet for a single Lavorazione.

generate_lavorazione_pdf(bagno, lav, disp_values) builds a one-page A4 PDF
combining batch/article master data, the disposition parameters for the
lavorazione's type, and the values recorded in that session, with a scannable
Code128 barcode of CODCLI+BAGNO at the top so it round-trips through the scan flow.

`disp_values` is a dict of already-resolved DISPLAY strings (built by the view);
this module renders them as-is. Empty values render as a blank fill-in line.
"""
import math
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Flowable,
)


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

# Page geometry — A4 with slim margins so the form fills the sheet.
_MARGIN     = 14 * mm
_CONTENT_W  = A4[0] - 2 * _MARGIN          # usable width (~182mm)

_STYLES   = getSampleStyleSheet()
_BODY      = ParagraphStyle("SchedaBody", parent=_STYLES["BodyText"],
                            fontSize=11.5, leading=13.5)
_LABEL     = ParagraphStyle("SchedaLabel", parent=_BODY, fontName="Helvetica-Bold")
_TITLE     = ParagraphStyle("SchedaTitle", parent=_STYLES["Title"],
                            fontSize=22, spaceAfter=2)
_CAPTION   = ParagraphStyle("BarcodeCap", parent=_BODY, fontSize=13,
                            alignment=1)  # centred
_SECTION   = ParagraphStyle("Section", parent=_STYLES["Heading3"], fontSize=14,
                            spaceBefore=8, spaceAfter=3,
                            textColor=colors.HexColor("#374151"))

# Larger, airier variants for the dipanatura sheet (which only fills ~half the page).
# Applied only from _dipanatura so the dense roccatura sheet stays one page.
_BODY_D    = ParagraphStyle("SchedaBodyD", parent=_BODY, fontSize=14, leading=18)
_LABEL_D   = ParagraphStyle("SchedaLabelD", parent=_BODY_D, fontName="Helvetica-Bold")
_SECTION_D = ParagraphStyle("SectionD", parent=_SECTION, fontSize=17,
                            spaceBefore=12, spaceAfter=5)

# Shared rule colour for fill-in lines/boxes.
_RULE = colors.HexColor("#9ca3af")


def _fmt(value):
    """Render a value for a fill-in cell; blank stays blank (underline shows)."""
    if value is None:
        return ""
    s = str(value).strip()
    return s


def _field_table(rows, *, label_style=_LABEL, body=_BODY, padding=5, label_ratio=0.42):
    """
    Build a 2-column-per-pair grid of (label, value) cells.

    `rows` is a list of (label, value) tuples; they are laid out two pairs per
    line. Value cells always carry a bottom border so empty fields render as a
    form-style fill-in line. `label_style`/`body`/`padding` let the dipanatura
    sheet render larger and airier than the (default) roccatura sheet;
    `label_ratio` widens the label column so larger labels don't wrap.
    """
    # Pack pairs two-per-row → 4 columns: label, value, label, value
    table_rows = []
    for i in range(0, len(rows), 2):
        left  = rows[i]
        right = rows[i + 1] if i + 1 < len(rows) else ("", "")
        table_rows.append([
            Paragraph(left[0], label_style)  if left[0]  else "",
            Paragraph(_fmt(left[1]), body),
            Paragraph(right[0], label_style) if right[0] else "",
            Paragraph(_fmt(right[1]), body),
        ])

    # Two label/value pairs across the full content width.
    pair = _CONTENT_W / 2
    lw, vw = pair * label_ratio, pair * (1 - label_ratio)
    col_widths = [lw, vw, lw, vw]
    t = Table(table_rows, colWidths=col_widths)

    style = [
        ("VALIGN",        (0, 0), (-1, -1), "BOTTOM"),
        ("TOPPADDING",    (0, 0), (-1, -1), padding),
        ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
        ("LEFTPADDING",   (0, 0), (-1, -1), 2),
    ]
    # Underline under the two value columns; skip the synthetic filler cell
    # added to pad an odd number of pairs (it isn't a real field).
    last = len(table_rows) - 1
    odd  = len(rows) % 2 == 1
    for r in range(len(table_rows)):
        style.append(("LINEBELOW", (1, r), (1, r), 0.6, _RULE))
        if not (odd and r == last):
            style.append(("LINEBELOW", (3, r), (3, r), 0.6, _RULE))
    t.setStyle(TableStyle(style))
    return t


def _full_row(label, value, *, label_style=_LABEL, body=_BODY, padding=5):
    """A single full-width (label, value) fill-in row."""
    label_w = _CONTENT_W * 0.21
    t = Table(
        [[Paragraph(label, label_style), Paragraph(_fmt(value), body)]],
        colWidths=[label_w, _CONTENT_W - label_w],
    )
    t.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "BOTTOM"),
        ("TOPPADDING",    (0, 0), (-1, -1), padding),
        ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
        ("LEFTPADDING",   (0, 0), (-1, -1), 2),
        ("LINEBELOW",     (1, 0), (1, -1), 0.6, _RULE),
    ]))
    return t


class _FillBox(Flowable):
    """
    A bordered fill-in area: `lines` evenly spaced rules with the value drawn
    across them, one text line per rule. Grows past `lines` if the value needs
    more room, so wrapped text always lands on its own rule (never crossing one).

    The value's paragraph leading is expected to equal `line_h`, which lets each
    wrapped line drop exactly one rule and sit just above it.
    """

    def __init__(self, value, style, width, line_h, lines):
        super().__init__()
        self.para   = Paragraph(_fmt(value), style)
        self.width  = width
        self.line_h = line_h
        self.lines  = lines
        self._rows  = lines
        self.height = line_h * lines

    def wrap(self, availWidth, availHeight):
        _, para_h = self.para.wrap(self.width - 4, 1_000_000)
        needed = max(1, math.ceil(para_h / self.line_h - 0.01))
        self._rows  = max(self.lines, needed)
        self.height = self.line_h * self._rows
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.setStrokeColor(_RULE)
        c.setLineWidth(0.6)
        c.rect(0, 0, self.width, self.height, stroke=1, fill=0)
        for i in range(1, self._rows):
            y = self.height - i * self.line_h
            c.line(0, y, self.width, y)
        # Top-aligned: with leading == line_h, each text line's baseline lands
        # just above its rule.
        self.para.drawOn(c, 2, self.height - self.para.height)


def _full_box(label, value, *, label_style=_LABEL, body=_BODY, padding=5, row_h=9 * mm, lines=3):
    """
    A full-width fill-in: the label sits at the top-left, with a bordered box of
    `lines` writable rules below it. The value prints across the rules, one text
    line per rule (the box grows if the value needs more than `lines` lines).
    """
    vstyle = ParagraphStyle("FillBoxValue", parent=body, leading=row_h)
    box = _FillBox(value, vstyle, _CONTENT_W, row_h, lines)
    t = Table(
        [[Paragraph(label, label_style)], [box]],
        colWidths=[_CONTENT_W],
    )
    t.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 2),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 1), (0, 1), 0),     # box flowable handles its own inset
        ("TOPPADDING",    (0, 0), (0, 0), padding),   # space above the label
        ("BOTTOMPADDING", (0, 0), (0, 0), 2),
        ("TOPPADDING",    (0, 1), (0, 1), 0),
        ("BOTTOMPADDING", (0, 1), (0, 1), 0),
    ]))
    return t


# ---------------------------------------------------------------------------
# Layout builders
# ---------------------------------------------------------------------------

def _dati_filato(bagno, lav):
    a = bagno.CODART
    composizione = " ".join(p for p in (a.COMPO1, a.COMPO2) if p)
    data = lav.DATORA.strftime("%d/%m/%Y %H:%M") if lav.DATORA else ""
    return _field_table([
        ("Articolo",       a.DESCRI or bagno.CODART_id),
        ("Partita/Bagno",  bagno.BAGNO),
        ("Composizione",   composizione),
        ("Colore",         bagno.COLORE),
        ("Titolo",         a.TITOLO),
        ("Data",           data),
    ])


def _roccatura(bagno, lav, dv):
    a = bagno.CODART
    elements = []

    elements.append(Paragraph("PARAMETRI", _SECTION))
    elements.append(_field_table([
        ("Tipo Supporto",     dv.get("CONI")),
        ("Colore Cono",       dv.get("COLCON")),
        ("Peso Rocca (gr)",   dv.get("PESROC")),
        ("Tolleranza",        dv.get("TOLLER")),
        ("Paraffina",         dv.get("PARAFF")),
        ("Tipo Paraffina",    dv.get("TIPPAR")),
        ("Colore Paraffina",  dv.get("COLPAR")),
        ("Velocità (m/min)",  dv.get("VELOCI")),
        ("Tensione (cN)",     dv.get("TENSIO")),
        ("Numero Rocche",     dv.get("NUMROC")),
        ("Metri per Rocca",   dv.get("METROC")),
        ("Giunzione",         dv.get("NODI")),
    ]))

    elements.append(Paragraph("CONTROLLO", _SECTION))
    elements.append(_field_table([
        ("Sensibilità Stribbia", dv.get("SENSTR")),
        ("Ottica",               dv.get("OTTICA")),
    ]))
    notroc = " ".join(p for p in (a.NOTROC, bagno.NOTROC) if p)
    note   = " ".join(p for p in (bagno.NOTE, bagno.NOTE1) if p)
    elements.append(_full_row("Note Rocca", notroc))
    elements.append(_full_row("Note", note))

    elements.append(Paragraph("OPERATORE & AVANZAMENTO", _SECTION))
    elements.append(_full_row("Collaboratore", lav.COLLABO.NOME if lav.COLLABO else ""))
    elements.append(_field_table([
        ("Macchina/Stato",     lav.get_STATO_display()),
        ("Turno",              lav.get_TURNO_display()),
        ("Quantità Prodotta",  lav.QUAPRO),
        ("Scarti (gr)",        lav.SCARTI),
    ]))
    # Note / Difetti as full-width ruled fill-ins (compact, to keep the dense
    # roccatura sheet on one page); each wrapped line sits on its own rule.
    elements.append(_full_box("Note",    lav.NOTDR,  row_h=7 * mm, lines=2))
    elements.append(Spacer(1, 3 * mm))
    elements.append(_full_box("Difetti", lav.DIFETT, row_h=7 * mm, lines=2))
    return elements


def _dipanatura(bagno, lav, dv):
    elements = []

    elements.append(Paragraph("PARAMETRI", _SECTION_D))
    elements.append(_field_table([
        ("Peso Rocca Finita", dv.get("PEROFI")),
        ("Paraffina",         dv.get("PARAFF")),
        ("Peso Matasse",      lav.PESMAT),
        ("Stribbia",          dv.get("STRIBB")),
        ("Matasse per Rocca", dv.get("MATROC")),
        ("Nodi",              dv.get("NODI")),
    ], label_style=_LABEL_D, body=_BODY_D, padding=9, label_ratio=0.5))

    # Macchine 4/5 record two front weights instead of the single "Pesi" value
    if lav.STATO in ("4", "5"):
        pesi_rows = [("Pesi fronte 1", lav.PESFR1), ("Pesi fronte 2", lav.PESFR2)]
    else:
        pesi_rows = [("Pesi", lav.PESI)]

    elements.append(Paragraph("OPERATORE & AVANZAMENTO", _SECTION_D))
    elements.append(_full_row("Collaboratore", lav.COLLABO.NOME if lav.COLLABO else "",
                              label_style=_LABEL_D, body=_BODY_D, padding=9))
    elements.append(_field_table([
        ("Macchina/Stato",  lav.get_STATO_display()),
        ("Codice",          lav.CODLAV),
        ("Cod. Fadis",      lav.COLAFA),
        ("Velocità",        lav.VELDIP),
        ("Passaggio",       lav.PASSAG),
        *pesi_rows,
    ], label_style=_LABEL_D, body=_BODY_D, padding=9, label_ratio=0.5))
    elements.append(_full_box("Note",    lav.NOTDR,  label_style=_LABEL_D, body=_BODY_D, padding=9))
    elements.append(Spacer(1, 5 * mm))
    elements.append(_full_box("Difetti", lav.DIFETT, label_style=_LABEL_D, body=_BODY_D, padding=9))
    return elements


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def generate_lavorazione_pdf(bagno, lav, disp_values) -> bytes:
    """Build the PDF and return its bytes."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=_MARGIN, rightMargin=_MARGIN,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title=f"{bagno.CODCLI_id} / {bagno.BAGNO}",
    )

    payload = f"{bagno.CODCLI_id}{bagno.BAGNO}"
    # Build the barcode, then stretch it to fill the content width so the bars
    # are wide enough to scan from a phone.
    barcode = createBarcodeDrawing(
        "Code128", value=payload, barHeight=24 * mm, humanReadable=False, quiet=False,
    )
    bar_w = 55 * mm
    sx = bar_w / barcode.width
    barcode.scale(sx, 1)
    barcode.width = bar_w
    barcode.hAlign = "CENTER"

    title_text = (
        "DISPOSIZIONE ROCCATURA"
        if lav.TIPO == "R"
        else "DISPOSIZIONE DIPANATURA"
    )

    story = [
        barcode,
        Spacer(1, 2 * mm),
        Paragraph(f"{bagno.CODCLI_id} / {bagno.BAGNO}", _CAPTION),
        Spacer(1, 8 * mm),
        Paragraph(title_text, _TITLE),
        Spacer(1, 4 * mm),
    ]

    if lav.TIPO == "R":
        story += [
            Paragraph("DATI FILATO", _SECTION),
            _dati_filato(bagno, lav),
        ]
        story += _roccatura(bagno, lav, disp_values)
    else:
        story += _dipanatura(bagno, lav, disp_values)

    doc.build(story)
    return buffer.getvalue()
