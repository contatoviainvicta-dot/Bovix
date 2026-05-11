# exports.py -- Exportacao de relatorios PDF e Excel
# Usa openpyxl para Excel e reportlab para PDF

import io
import csv
from datetime import datetime

import pandas as pd

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    _OPENPYXL = True
except ImportError:
    _OPENPYXL = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )
    _REPORTLAB = True
except ImportError:
    _REPORTLAB = False


# ── helpers Excel ────────────────────────────────────────────────────────────

def _cab(ws, row, cols, cor="1F5C2E"):
    fill = PatternFill("solid", fgColor=cor)
    bold = Font(bold=True, color="FFFFFF", size=11)
    alin = Alignment(horizontal="center", vertical="center")
    for col in range(1, cols+1):
        cell = ws.cell(row=row, column=col)
        cell.fill = fill
        cell.font = bold
        cell.alignment = alin

def _auto_w(ws):
    for col in ws.columns:
        ml = 0
        cl = get_column_letter(col[0].column)
        for cell in col:
            try: ml = max(ml, len(str(cell.value or "")))
            except: pass
        ws.column_dimensions[cl].width = min(ml+4, 40)

def _csv_fallback(tabelas):
    buf = io.StringIO()
    w = csv.writer(buf)
    for nome, linhas in tabelas.items():
        w.writerow([f"=== {nome} ==="])
        for linha in linhas: w.writerow(linha)
        w.writerow([])
    return buf.getvalue().encode("utf-8-sig")


# ── Excel lote ───────────────────────────────────────────────────────────────

def gerar_excel_lote(nome_lote, animais, pesagens_dict, ocorrencias_dict):
    if not _OPENPYXL:
        todos_p = [p for ps in pesagens_dict.values() for p in ps]
        todos_o = [o for os in ocorrencias_dict.values() for o in os]
        return _csv_fallback({
            "Animais":     [("ID","Identificacao","Idade","Lote ID")] + list(animais),
            "Pesagens":    [("ID","Animal ID","Peso","Data")] + todos_p,
            "Ocorrencias": [("ID","Animal ID","Data","Tipo","Desc","Grav","Custo","Dias","Status")] + todos_o,
        })

    wb = Workbook()

    # Resumo
    ws_r = wb.active
    ws_r.title = "Resumo"
    ws_r["A1"] = f"Relatorio -- {nome_lote}"
    ws_r["A1"].font = Font(bold=True, size=14)
    ws_r["A2"] = f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}"

    total_a   = len(animais)
    total_oc  = sum(len(v) for v in ocorrencias_dict.values())
    custo_san = sum(o[6] for ocs in ocorrencias_dict.values() for o in ocs if o[6])
    gmds = []
    for aid, pesos in pesagens_dict.items():
        if len(pesos) > 1:
            df = pd.DataFrame(pesos, columns=["id","aid","peso","data"])
            df["data"] = pd.to_datetime(df["data"])
            df = df.sort_values("data")
            dias = (df["data"].iloc[-1]-df["data"].iloc[0]).days
            if dias > 0:
                g = (df["peso"].iloc[-1]-df["peso"].iloc[0])/dias
                if 0 <= g <= 2: gmds.append(g)
    gmd_m = sum(gmds)/len(gmds) if gmds else 0

    resumo = [
        ["Indicador","Valor"],
        ["Total de animais", total_a],
        ["Total de ocorrencias", total_oc],
        ["Custo sanitario total (R$)", f"{custo_san:.2f}"],
        ["GMD medio (kg/dia)", f"{gmd_m:.3f}"],
    ]
    for i, linha in enumerate(resumo, start=4):
        for j, val in enumerate(linha, start=1):
            ws_r.cell(row=i, column=j, value=val)
    _cab(ws_r, 4, 2)
    _auto_w(ws_r)

    # Animais
    ws_a = wb.create_sheet("Animais")
    cab_a = ["ID","Identificacao","Idade (meses)","Lote ID"]
    for j, c in enumerate(cab_a, 1): ws_a.cell(row=1, column=j, value=c)
    _cab(ws_a, 1, len(cab_a))
    for i, animal in enumerate(animais, start=2):
        for j, val in enumerate(animal, start=1): ws_a.cell(row=i, column=j, value=val)
    _auto_w(ws_a)

    # Pesagens
    ws_p = wb.create_sheet("Pesagens")
    cab_p = ["ID","Animal ID","Peso (kg)","Data"]
    for j, c in enumerate(cab_p, 1): ws_p.cell(row=1, column=j, value=c)
    _cab(ws_p, 1, len(cab_p))
    row = 2
    for pesos in pesagens_dict.values():
        for p in pesos:
            for j, val in enumerate(p, start=1): ws_p.cell(row=row, column=j, value=val)
            row += 1
    _auto_w(ws_p)

    # Ocorrencias
    ws_o = wb.create_sheet("Ocorrencias")
    cab_o = ["ID","Animal ID","Data","Tipo","Descricao","Gravidade","Custo (R$)","Dias Rec","Status"]
    for j, c in enumerate(cab_o, 1): ws_o.cell(row=1, column=j, value=c)
    _cab(ws_o, 1, len(cab_o))
    row = 2
    for ocs in ocorrencias_dict.values():
        for o in ocs:
            for j, val in enumerate(o, start=1): ws_o.cell(row=row, column=j, value=val)
            row += 1
    _auto_w(ws_o)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── Excel sanitario ──────────────────────────────────────────────────────────

def gerar_excel_sanitario(vacinas, medicamentos):
    if not _OPENPYXL:
        return _csv_fallback({
            "Vacinas":      [("ID","Lote ID","Vacina","Previsto","Realizado","Status","Obs")] + list(vacinas),
            "Medicamentos": [("ID","Nome","Unidade","Estoque","Minimo","Validade","Custo")] + list(medicamentos),
        })

    wb = Workbook()

    ws_v = wb.active
    ws_v.title = "Agenda Vacinas"
    cab_v = ["ID","Lote ID","Vacina","Previsto","Realizado","Status","Observacao"]
    for j, c in enumerate(cab_v, 1): ws_v.cell(row=1, column=j, value=c)
    _cab(ws_v, 1, len(cab_v), "0F6E56")
    for i, v in enumerate(vacinas, start=2):
        for j, val in enumerate(v, start=1): ws_v.cell(row=i, column=j, value=val)
    _auto_w(ws_v)

    ws_m = wb.create_sheet("Estoque Medicamentos")
    cab_m = ["ID","Nome","Unidade","Estoque Atual","Estoque Minimo","Validade","Custo Unit. (R$)"]
    for j, c in enumerate(cab_m, 1): ws_m.cell(row=1, column=j, value=c)
    _cab(ws_m, 1, len(cab_m), "0F6E56")
    for i, m in enumerate(medicamentos, start=2):
        for j, val in enumerate(m, start=1): ws_m.cell(row=i, column=j, value=val)
    _auto_w(ws_m)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── PDF ──────────────────────────────────────────────────────────────────────

def _sanitizar(val):
    texto = str(val) if val is not None else ""
    return texto.replace("\x00", "").strip()

def _pdf_fallback(titulo, secoes):
    linhas = [f"# {titulo}", f"# {datetime.now().strftime('%d/%m/%Y %H:%M')}", ""]
    for sec in secoes:
        linhas.append(f"## {sec['titulo']}")
        df = sec.get("df")
        if df is not None and not df.empty:
            linhas.append(df.to_string(index=False))
        linhas.append("")
    return "\n".join(linhas).encode()

def gerar_pdf_relatorio(titulo, secoes):
    if not _REPORTLAB:
        return _pdf_fallback(titulo, secoes)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )
    styles = getSampleStyleSheet()
    story  = []

    st_titulo = ParagraphStyle(
        "tit_pec", parent=styles["Title"],
        fontSize=15, spaceAfter=4,
        textColor=colors.HexColor("#1F5C2E"),
    )
    story.append(Paragraph(_sanitizar(titulo), st_titulo))
    story.append(Paragraph(
        f"Gerado em {datetime.now().strftime('%d/%m/%Y as %H:%M')}",
        styles["Normal"],
    ))
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1F5C2E")))
    story.append(Spacer(1, 0.3*cm))

    st_sec = ParagraphStyle(
        "sec_pec", parent=styles["Heading2"],
        fontSize=11, textColor=colors.HexColor("#1F5C2E"), spaceAfter=4,
    )

    for sec in secoes:
        story.append(Paragraph(_sanitizar(sec["titulo"]), st_sec))
        df = sec.get("df")
        if df is None or (hasattr(df, "empty") and df.empty):
            story.append(Paragraph("Sem dados.", styles["Normal"]))
            story.append(Spacer(1, 0.3*cm))
            continue
        try:
            colunas = [_sanitizar(c) for c in df.columns]
            linhas  = [[_sanitizar(v) for v in row] for row in df.values.tolist()]
            data    = [colunas] + linhas
            n_cols  = len(colunas)
            col_w   = doc.width / n_cols
            t = Table(data, colWidths=[col_w]*n_cols, repeatRows=1, splitByRow=True)
            t.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),(-1,0), colors.HexColor("#1F5C2E")),
                ("TEXTCOLOR",     (0,0),(-1,0), colors.white),
                ("FONTNAME",      (0,0),(-1,0), "Helvetica-Bold"),
                ("FONTNAME",      (0,1),(-1,-1),"Helvetica"),
                ("FONTSIZE",      (0,0),(-1,0), 8),
                ("FONTSIZE",      (0,1),(-1,-1),7),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, colors.HexColor("#F1F8F3")]),
                ("GRID",          (0,0),(-1,-1),0.3, colors.HexColor("#CCCCCC")),
                ("VALIGN",        (0,0),(-1,-1),"MIDDLE"),
                ("ALIGN",         (0,0),(-1,-1),"LEFT"),
                ("TOPPADDING",    (0,0),(-1,-1),3),
                ("BOTTOMPADDING", (0,0),(-1,-1),3),
            ]))
            story.append(t)
        except Exception as e:
            story.append(Paragraph(f"Erro ao renderizar tabela: {e}", styles["Normal"]))
        story.append(Spacer(1, 0.4*cm))

    try:
        doc.build(story)
        pdf_bytes = buf.getvalue()
        if not pdf_bytes.startswith(b"%PDF-"):
            return _pdf_fallback(titulo, secoes)
        return pdf_bytes
    except Exception:
        return _pdf_fallback(titulo, secoes)
