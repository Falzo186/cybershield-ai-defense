"""Convierte un informe Markdown del proyecto en un PDF formal (negro, azul marino y rojo oscuro) con portada institucional.

  python experimentos/generar_informe_pdf.py docs/INFORME_EJECUTIVO_FINAL.md docs/INFORME_EJECUTIVO_FINAL.pdf

Solo usa reportlab (ya instalado). Soporta: títulos #/##/###, párrafos, listas con viñeta y numeradas, tablas con tuberías,
bloques de código, **negrita**, *cursiva*, `código` y líneas horizontales. Fuentes del sistema (Segoe UI/Consolas) para que
salgan →, ≥, ≤ y las tildes.
"""
import re
import sys
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageBreak, PageTemplate, Paragraph, Preformatted, Spacer, Table,
                                TableStyle, NextPageTemplate)

NEGRO, MARINA, ROJO, GRIS = colors.HexColor("#111111"), colors.HexColor("#1b2f5e"), colors.HexColor("#8f2a35"), colors.HexColor("#555555")
FUENTES = Path("C:/Windows/Fonts")
try:
    pdfmetrics.registerFont(TTFont("Texto", str(FUENTES / "segoeui.ttf")))
    pdfmetrics.registerFont(TTFont("Texto-B", str(FUENTES / "segoeuib.ttf")))
    pdfmetrics.registerFont(TTFont("Texto-I", str(FUENTES / "segoeuii.ttf")))
    pdfmetrics.registerFont(TTFont("Codigo", str(FUENTES / "consola.ttf")))
    pdfmetrics.registerFontFamily("Texto", normal="Texto", bold="Texto-B", italic="Texto-I", boldItalic="Texto-B")
    F, FB, FI, FC = "Texto", "Texto-B", "Texto-I", "Codigo"
except Exception:  # noqa: BLE001 - sin las fuentes del sistema se cae a las estándar (pueden faltar algunos símbolos)
    F, FB, FI, FC = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Courier"

ESTILO = {
    "cuerpo": ParagraphStyle("cuerpo", fontName=F, fontSize=9.6, leading=13.4, textColor=NEGRO, spaceAfter=5),
    "h1": ParagraphStyle("h1", fontName=FB, fontSize=17, leading=21, textColor=MARINA, spaceBefore=14, spaceAfter=8, keepWithNext=1),
    "h2": ParagraphStyle("h2", fontName=FB, fontSize=13, leading=17, textColor=MARINA, spaceBefore=11, spaceAfter=5, keepWithNext=1),
    "h3": ParagraphStyle("h3", fontName=FB, fontSize=10.8, leading=14, textColor=ROJO, spaceBefore=8, spaceAfter=3, keepWithNext=1),
    "lista": ParagraphStyle("lista", fontName=F, fontSize=9.6, leading=13.2, textColor=NEGRO, leftIndent=14, bulletIndent=3, spaceAfter=2),
    "celda": ParagraphStyle("celda", fontName=F, fontSize=7.9, leading=10, textColor=NEGRO),
    "celda_cab": ParagraphStyle("celda_cab", fontName=FB, fontSize=7.9, leading=10, textColor=colors.white),
    "cita": ParagraphStyle("cita", fontName=FI, fontSize=9.3, leading=13, textColor=GRIS, leftIndent=10, borderPadding=(2, 2, 2, 6), spaceAfter=5),
}


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(t):
    t = esc(t)
    t = re.sub(r"`([^`]+)`", lambda m: f'<font name="{FC}" size="8.4" color="#8f2a35">{m[1]}</font>', t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?![*\w])", r"<i>\1</i>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", t)     # enlaces: solo el texto
    return t


def tabla(filas, ancho):
    filas = [f for f in filas if not re.fullmatch(r"\|?[\s:|-]+\|?", f)]
    celdas = [[c.strip() for c in f.strip().strip("|").split("|")] for f in filas]
    n = max(len(c) for c in celdas)
    celdas = [c + [""] * (n - len(c)) for c in celdas]
    data = [[Paragraph(inline(x), ESTILO["celda_cab" if i == 0 else "celda"]) for x in fila] for i, fila in enumerate(celdas)]
    peso = [max(len(c[j]) for c in celdas) for j in range(n)]
    peso = [min(max(p, 6), 48) for p in peso]
    tot = sum(peso)
    t = Table(data, colWidths=[ancho * p / tot for p in peso], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), MARINA), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f3f8")]),
                           ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#b8bfd0")), ("LEFTPADDING", (0, 0), (-1, -1), 4),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


def convertir(md, ancho):
    out, lineas, i = [], md.splitlines(), 0
    while i < len(lineas):
        l = lineas[i]
        if l.startswith("```"):
            j = i + 1
            while j < len(lineas) and not lineas[j].startswith("```"):
                j += 1
            bloque = "\n".join(lineas[i + 1:j])
            out.append(Preformatted(bloque, ParagraphStyle("cod", fontName=FC, fontSize=7.4, leading=9.4, textColor=NEGRO, backColor=colors.HexColor("#f1f3f8"),
                                                           borderPadding=5, leftIndent=4, spaceAfter=6, spaceBefore=2)))
            i = j + 1
            continue
        if l.startswith("|"):
            j = i
            while j < len(lineas) and lineas[j].startswith("|"):
                j += 1
            out += [tabla(lineas[i:j], ancho), Spacer(1, 6)]
            i = j
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", l)
        if m:
            nivel = min(len(m[1]), 3)
            out.append(Paragraph(inline(m[2]), ESTILO[f"h{nivel}"]))
        elif re.match(r"^\s*[-*]\s+", l):
            out.append(Paragraph(inline(re.sub(r"^\s*[-*]\s+", "", l)), ESTILO["lista"], bulletText="•"))
        elif re.match(r"^\s*\d+[.)]\s+", l):
            n = re.match(r"^\s*(\d+)[.)]\s+", l)[1]
            out.append(Paragraph(inline(re.sub(r"^\s*\d+[.)]\s+", "", l)), ESTILO["lista"], bulletText=n + "."))
        elif l.startswith(">"):
            out.append(Paragraph(inline(l.lstrip("> ")), ESTILO["cita"]))
        elif re.fullmatch(r"-{3,}", l.strip()):
            out.append(Spacer(1, 6))
        elif l.strip():
            par = [l.strip()]
            while i + 1 < len(lineas) and lineas[i + 1].strip() and not re.match(r"^(#|\||```|\s*[-*]\s|\s*\d+[.)]\s|>)", lineas[i + 1]):
                i += 1
                par.append(lineas[i].strip())
            out.append(Paragraph(inline(" ".join(par)), ESTILO["cuerpo"]))
        i += 1
    return out


class Doc(BaseDocTemplate):
    def __init__(self, destino, titulo):
        super().__init__(str(destino), pagesize=A4, leftMargin=2.0 * cm, rightMargin=2.0 * cm, topMargin=2.2 * cm, bottomMargin=2.0 * cm,
                         title=titulo, author="Jesús Alejandro Murillo Zavala", subject="CyberShield AI Defense")
        w, h = A4
        marco = Frame(self.leftMargin, self.bottomMargin, w - self.leftMargin - self.rightMargin, h - self.topMargin - self.bottomMargin, id="n")
        portada = Frame(2.2 * cm, 2.2 * cm, w - 4.4 * cm, h - 4.4 * cm, id="p")
        self.addPageTemplates([PageTemplate("portada", [portada], onPage=self._portada), PageTemplate("normal", [marco], onPage=self._pagina)])
        self.titulo = titulo

    def _portada(self, c, d):
        w, h = A4
        c.saveState()
        c.setFillColor(MARINA)
        c.rect(0, h - 4.6 * cm, w, 4.6 * cm, stroke=0, fill=1)
        c.setFillColor(ROJO)
        c.rect(0, h - 4.85 * cm, w, 0.25 * cm, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont(FB, 17)
        c.drawCentredString(w / 2, h - 2.2 * cm, "Universidad Autónoma de Tamaulipas")
        c.setFont(F, 13)
        c.drawCentredString(w / 2, h - 3.1 * cm, "Facultad de Ingeniería")
        c.setFillColor(NEGRO)
        c.rect(0, 0, w, 1.2 * cm, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont(F, 8)
        c.drawCentredString(w / 2, 0.45 * cm, "Proyecto académico · laboratorio local con datos ficticios · Wazuh SIMULADO")
        c.restoreState()

    def _pagina(self, c, d):
        w, h = A4
        c.saveState()
        c.setStrokeColor(MARINA)
        c.setLineWidth(1.2)
        c.line(2 * cm, h - 1.55 * cm, w - 2 * cm, h - 1.55 * cm)
        c.setFont(F, 8)
        c.setFillColor(MARINA)
        c.drawString(2 * cm, h - 1.3 * cm, "CyberShield AI Defense · " + self.titulo)
        c.setFillColor(ROJO)
        c.drawRightString(w - 2 * cm, h - 1.3 * cm, "Universidad Autónoma de Tamaulipas · Facultad de Ingeniería")
        c.setStrokeColor(colors.HexColor("#b8bfd0"))
        c.setLineWidth(0.5)
        c.line(2 * cm, 1.5 * cm, w - 2 * cm, 1.5 * cm)
        c.setFillColor(GRIS)
        c.drawString(2 * cm, 1.0 * cm, f"Generado el {date.today().isoformat()}")
        c.drawRightString(w - 2 * cm, 1.0 * cm, f"Página {d.page}")
        c.restoreState()


def main(origen, destino, titulo=None):
    md = Path(origen).read_text(encoding="utf-8")
    m = re.match(r"#\s+(.*)", md)
    titulo = titulo or (m[1] if m else Path(origen).stem)
    doc = Doc(destino, titulo)
    ancho = A4[0] - 4 * cm
    hist = []
    portada = ParagraphStyle("pt", fontName=FB, fontSize=24, leading=29, textColor=MARINA, alignment=TA_CENTER)
    sub = ParagraphStyle("ps", fontName=F, fontSize=12, leading=17, textColor=NEGRO, alignment=TA_CENTER)
    rojo = ParagraphStyle("pr", fontName=FB, fontSize=11, leading=16, textColor=ROJO, alignment=TA_CENTER)
    hist += [Spacer(1, 5.6 * cm), Paragraph("CyberShield AI Defense", rojo), Spacer(1, 10), Paragraph(esc(titulo), portada), Spacer(1, 14),
             Paragraph("Combate IA vs IA con modelos de 8B, victoria y derrota verificables por el motor, Wazuh simulado y evaluación honesta", sub),
             Spacer(1, 3.6 * cm), Paragraph("<b>Autor:</b> Jesús Alejandro Murillo Zavala", sub), Spacer(1, 4),
             Paragraph("<b>Carrera:</b> Ingeniería en Sistemas Computacionales", sub), Spacer(1, 4),
             Paragraph("<b>Proyecto:</b> CyberShield AI Defense (laboratorio académico, 100 % local y ficticio)", sub), Spacer(1, 4),
             Paragraph(f"<b>Fecha:</b> {date.today().strftime('%d/%m/%Y')}", sub), NextPageTemplate("normal"), PageBreak()]
    cuerpo = convertir(md, ancho)
    if cuerpo and isinstance(cuerpo[0], Paragraph) and cuerpo[0].style.name == "h1":
        cuerpo = cuerpo[1:]      # el título ya está en la portada
    doc.build(hist + cuerpo)
    return doc.page


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    print("páginas:", main(sys.argv[1], sys.argv[2]))
