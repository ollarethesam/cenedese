"""
pdf.py — Printable "SCHEDA DISPOSIZIONI" sheet for a single Lavorazione.

generate_lavorazione_pdf(bagno, lav, disp_values) builds a one-page A4 PDF
combining batch/article master data, the disposition parameters for the
lavorazione's type, and the values recorded in that session, with a scannable
Code128 barcode of CODCLI+BAGNO at the top so it round-trips through the scan flow.

`disp_values` is a dict of already-resolved DISPLAY strings (built by the view);
this module renders them as-is. Empty values render as a blank fill-in line.
"""
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer,
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


def _fmt(value):
    """Render a value for a fill-in cell; blank stays blank (underline shows)."""
    if value is None:
        return ""
    s = str(value).strip()
    return s


def _field_table(rows):
    """
    Build a 2-column-per-pair grid of (label, value) cells.

    `rows` is a list of (label, value) tuples; they are laid out two pairs per
    line. Value cells always carry a bottom border so empty fields render as a
    form-style fill-in line.
    """
    # Pack pairs two-per-row → 4 columns: label, value, label, value
    table_rows = []
    for i in range(0, len(rows), 2):
        left  = rows[i]
        right = rows[i + 1] if i + 1 < len(rows) else ("", "")
        table_rows.append([
            Paragraph(left[0], _LABEL)  if left[0]  else "",
            Paragraph(_fmt(left[1]), _BODY),
            Paragraph(right[0], _LABEL) if right[0] else "",
            Paragraph(_fmt(right[1]), _BODY),
        ])

    # Two label/value pairs across the full content width.
    pair = _CONTENT_W / 2
    col_widths = [pair * 0.42, pair * 0.58, pair * 0.42, pair * 0.58]
    t = Table(table_rows, colWidths=col_widths)

    style = [
        ("VALIGN",        (0, 0), (-1, -1), "BOTTOM"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 2),
        # Underline under the two value columns
        ("LINEBELOW", (1, 0), (1, -1), 0.6, colors.HexColor("#9ca3af")),
        ("LINEBELOW", (3, 0), (3, -1), 0.6, colors.HexColor("#9ca3af")),
    ]
    t.setStyle(TableStyle(style))
    return t


def _full_row(label, value):
    """A single full-width (label, value) fill-in row."""
    label_w = _CONTENT_W * 0.21
    t = Table(
        [[Paragraph(label, _LABEL), Paragraph(_fmt(value), _BODY)]],
        colWidths=[label_w, _CONTENT_W - label_w],
    )
    t.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "BOTTOM"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 2),
        ("LINEBELOW",     (1, 0), (1, -1), 0.6, colors.HexColor("#9ca3af")),
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
    elements.append(_field_table([
        ("Collaboratrice",     lav.COLLABO.NOME if lav.COLLABO else ""),
        ("Macchina/Stato",     lav.get_STATO_display()),
        ("Turno",              lav.get_TURNO_display()),
        ("Quantità Prodotta",  lav.QUAPRO),
        ("Scarti (gr)",        lav.SCARTI),
        ("Difetti",            lav.DIFETT),
    ]))
    elements.append(_full_row("Nota 1", lav.NOTDR1))
    elements.append(_full_row("Nota 2", lav.NOTDR2))
    elements.append(_full_row("Nota 3", lav.NOTDR3))
    return elements


def _dipanatura(bagno, lav, dv):
    elements = []

    elements.append(Paragraph("PARAMETRI", _SECTION))
    elements.append(_field_table([
        ("Peso Rocca Finita", dv.get("PEROFI")),
        ("Paraffina",         dv.get("PARAFF")),
        ("Cono",              dv.get("CONI")),
        ("Camera",            dv.get("CAMERA")),
        ("Matasse per Rocca", dv.get("MATROC")),
        ("Nodi",              dv.get("NODI")),
        ("Stribbia",          dv.get("STRIBB")),
    ]))

    # Macchine 4/5 record two front weights instead of the single "Pesi" value
    if lav.STATO in ("4", "5"):
        pesi_rows = [("Pesi fronte 1", lav.PESFR1), ("Pesi fronte 2", lav.PESFR2)]
    else:
        pesi_rows = [("Pesi", lav.PESI)]

    elements.append(Paragraph("OPERATORE & AVANZAMENTO", _SECTION))
    elements.append(_field_table([
        ("Codice",          lav.CODLAV),
        ("Cod. Fadis",      lav.COLAFA),
        ("Velocità",        lav.VELDIP),
        ("Passaggio",       lav.PASSAG),
        *pesi_rows,
        ("Collaboratrice",  lav.COLLABO.NOME if lav.COLLABO else ""),
        ("Macchina/Stato",  lav.get_STATO_display()),
        ("Turno",           lav.get_TURNO_display()),
        ("Difetti",         lav.DIFETT),
    ]))
    elements.append(_full_row("Nota 1", lav.NOTDR1))
    elements.append(_full_row("Nota 2", lav.NOTDR2))
    elements.append(_full_row("Nota 3", lav.NOTDR3))
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
        "SCHEDA DISPOSIZIONI DI ROCCATURA"
        if lav.TIPO == "R"
        else "SCHEDA DISPOSIZIONI DI DIPANATURA"
    )

    story = [
        barcode,
        Spacer(1, 2 * mm),
        Paragraph(f"{bagno.CODCLI_id} / {bagno.BAGNO}", _CAPTION),
        Spacer(1, 8 * mm),
        Paragraph(title_text, _TITLE),
        Spacer(1, 4 * mm),
        Paragraph("DATI FILATO", _SECTION),
        _dati_filato(bagno, lav),
    ]

    if lav.TIPO == "R":
        story += _roccatura(bagno, lav, disp_values)
    else:
        story += _dipanatura(bagno, lav, disp_values)

    doc.build(story)
    return buffer.getvalue()
