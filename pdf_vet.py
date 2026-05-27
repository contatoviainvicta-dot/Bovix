# pdf_vet.py -- Geracao de PDFs veterinarios (receituario e relatorio de visita)
import io
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY


# Paleta de cores Auroque
_VERDE       = colors.HexColor("#1B4332")
_VERDE_CLARO = colors.HexColor("#40916C")
_BEGE        = colors.HexColor("#F5F0E8")
_CINZA       = colors.HexColor("#6C757D")
_PRETO       = colors.HexColor("#212529")


def _estilos():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="TituloDoc",
        fontSize=16, fontName="Helvetica-Bold",
        textColor=_VERDE, spaceAfter=4,
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="SubtituloDoc",
        fontSize=10, fontName="Helvetica",
        textColor=_CINZA, spaceAfter=2,
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="SecaoTitulo",
        fontSize=11, fontName="Helvetica-Bold",
        textColor=_VERDE, spaceBefore=10, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="Campo",
        fontSize=9, fontName="Helvetica-Bold",
        textColor=_PRETO, spaceAfter=1,
    ))
    styles.add(ParagraphStyle(
        name="Valor",
        fontSize=9, fontName="Helvetica",
        textColor=_PRETO, spaceAfter=6, leading=13,
    ))
    styles.add(ParagraphStyle(
        name="Rodape",
        fontSize=7, fontName="Helvetica",
        textColor=_CINZA, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="Alerta",
        fontSize=9, fontName="Helvetica-Bold",
        textColor=colors.HexColor("#DC3545"), spaceAfter=6,
    ))
    return styles


def _cabecalho(story, styles, nome_vet, crmv, subtitulo=""):
    """Cabecalho padrao com logo Auroque + dados do vet."""
    # Logo texto Auroque
    story.append(Paragraph(
        "<font color='#1B4332'><b>🐄 Auroque</b></font> "
        "<font color='#40916C'>Sistema de Gestao Pecuaria</font>",
        styles["SubtituloDoc"]
    ))
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(
        width="100%", thickness=2,
        color=_VERDE_CLARO, spaceAfter=6
    ))

    # Dados do vet em tabela de 2 colunas
    dados_vet = [
        [
            Paragraph(f"<b>Veterinario(a):</b> {nome_vet}", styles["Valor"]),
            Paragraph(
                f"<b>CRMV:</b> {crmv or 'Nao cadastrado'} &nbsp;&nbsp; "
                f"<b>Data:</b> {date.today().strftime('%d/%m/%Y')}",
                styles["Valor"]
            ),
        ]
    ]
    t_vet = Table(dados_vet, colWidths=[9*cm, 9*cm])
    t_vet.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,-1), _BEGE),
        ("ROWPADDING",  (0,0), (-1,-1), 6),
        ("GRID",        (0,0), (-1,-1), 0.5, colors.white),
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(t_vet)
    story.append(Spacer(1, 0.3*cm))

    if subtitulo:
        story.append(Paragraph(subtitulo, styles["TituloDoc"]))
        story.append(HRFlowable(
            width="100%", thickness=1,
            color=_VERDE, spaceAfter=8
        ))


def _rodape(story, styles, doc_tipo, doc_id):
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(
        width="100%", thickness=0.5,
        color=_CINZA, spaceBefore=4
    ))
    story.append(Paragraph(
        f"Documento gerado pelo Auroque em {date.today().strftime('%d/%m/%Y')} | "
        f"{doc_tipo} #{doc_id} | "
        "Este documento tem validade informativa. "
        "Para fins legais, confirme com o veterinario responsavel.",
        styles["Rodape"]
    ))


def gerar_pdf_receita(receita_dict):
    """
    Gera PDF do receituario.
    receita_dict: {id, nome_vet, crmv, nome_fazenda, nome_animal,
                   medicamento, dose, via, duracao, carencia_dias,
                   observacoes, data_emissao}
    Retorna bytes do PDF.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        leftMargin=2*cm, rightMargin=2*cm,
        title=f"Receituario #{receita_dict.get('id','')}",
        author=receita_dict.get("nome_vet",""),
    )
    styles = _estilos()
    story  = []

    _cabecalho(story, styles, receita_dict.get("nome_vet",""),
               receita_dict.get("crmv",""),
               subtitulo="RECEITUARIO VETERINARIO")

    # Identificacao
    story.append(Paragraph("Identificacao", styles["SecaoTitulo"]))
    id_data = [
        ["Fazenda",  receita_dict.get("nome_fazenda","")],
        ["Animal",   receita_dict.get("nome_animal","Lote inteiro")],
        ["Data",     receita_dict.get("data_emissao","")],
    ]
    t_id = Table(id_data, colWidths=[4*cm, 14*cm])
    t_id.setStyle(TableStyle([
        ("FONTNAME",   (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME",   (1,0), (1,-1), "Helvetica"),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("ROWPADDING", (0,0), (-1,-1), 5),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [_BEGE, colors.white]),
        ("GRID",       (0,0), (-1,-1), 0.3, _CINZA),
    ]))
    story.append(t_id)
    story.append(Spacer(1, 0.4*cm))

    # Prescricao
    story.append(Paragraph("Prescricao", styles["SecaoTitulo"]))
    presc_data = [
        ["Medicamento",  receita_dict.get("medicamento","")],
        ["Dose",         receita_dict.get("dose","")],
        ["Via",          receita_dict.get("via","")],
        ["Duracao",      receita_dict.get("duracao","")],
    ]
    carc = receita_dict.get("carencia_dias", 0)
    if carc:
        presc_data.append(["Carencia abate", f"{carc} dias"])

    t_presc = Table(presc_data, colWidths=[4*cm, 14*cm])
    t_presc.setStyle(TableStyle([
        ("FONTNAME",   (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME",   (1,0), (1,-1), "Helvetica"),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("ROWPADDING", (0,0), (-1,-1), 6),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [_BEGE, colors.white]),
        ("GRID",       (0,0), (-1,-1), 0.3, _CINZA),
        ("TEXTCOLOR",  (0,-1), (-1,-1),
         colors.HexColor("#DC3545") if carc else _PRETO),
    ]))
    story.append(t_presc)

    if carc:
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph(
            f"ATENCAO: Animal em periodo de carencia de {carc} dias. "
            "Nao destinar para abate antes do prazo.",
            styles["Alerta"]
        ))

    obs = receita_dict.get("observacoes","")
    if obs:
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph("Observacoes", styles["SecaoTitulo"]))
        story.append(Paragraph(obs, styles["Valor"]))

    # Assinatura
    story.append(Spacer(1, 2*cm))
    assin = Table(
        [[
            Paragraph("_" * 45, styles["Valor"]),
            Paragraph("", styles["Valor"]),
        ]],
        colWidths=[12*cm, 6*cm]
    )
    story.append(assin)
    story.append(Paragraph(
        f"{receita_dict.get('nome_vet','')} | "
        f"CRMV: {receita_dict.get('crmv','Nao cadastrado')}",
        styles["SubtituloDoc"]
    ))

    _rodape(story, styles, "Receituario", receita_dict.get("id",""))

    doc.build(story)
    buf.seek(0)
    return buf.read()


def gerar_pdf_relatorio_visita(relat_dict):
    """
    Gera PDF do relatorio de visita.
    relat_dict: {id, nome_vet, crmv, nome_fazenda, data_relatorio,
                 animais_inspecionados, achados, tratamentos,
                 recomendacoes, proxima_visita, observacoes}
    Retorna bytes do PDF.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        leftMargin=2*cm, rightMargin=2*cm,
        title=f"Relatorio de Visita #{relat_dict.get('id','')}",
        author=relat_dict.get("nome_vet",""),
    )
    styles  = _estilos()
    story   = []

    _cabecalho(story, styles, relat_dict.get("nome_vet",""),
               relat_dict.get("crmv",""),
               subtitulo="RELATORIO TECNICO DE VISITA")

    # Cabecalho do relatorio
    story.append(Paragraph("Informacoes da Visita", styles["SecaoTitulo"]))
    info_data = [
        ["Fazenda",              relat_dict.get("nome_fazenda","")],
        ["Data",                 relat_dict.get("data_relatorio","")],
        ["Animais inspecionados", str(relat_dict.get("animais_inspecionados", 0))],
    ]
    prox = relat_dict.get("proxima_visita")
    if prox and str(prox) not in ("None",""):
        info_data.append(["Proxima visita", str(prox)])

    t_info = Table(info_data, colWidths=[5*cm, 13*cm])
    t_info.setStyle(TableStyle([
        ("FONTNAME",   (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME",   (1,0), (1,-1), "Helvetica"),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("ROWPADDING", (0,0), (-1,-1), 5),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [_BEGE, colors.white]),
        ("GRID",       (0,0), (-1,-1), 0.3, _CINZA),
    ]))
    story.append(t_info)

    # Secoes de conteudo
    secoes = [
        ("Achados Clinicos", relat_dict.get("achados","")),
        ("Tratamentos Realizados", relat_dict.get("tratamentos","")),
        ("Recomendacoes", relat_dict.get("recomendacoes","")),
    ]
    for titulo_s, conteudo_s in secoes:
        if conteudo_s and conteudo_s.strip():
            story.append(Spacer(1, 0.4*cm))
            story.append(Paragraph(titulo_s, styles["SecaoTitulo"]))
            # Quebrar em paragrafos por linha
            for linha in str(conteudo_s).split("\n"):
                if linha.strip():
                    story.append(Paragraph(linha.strip(), styles["Valor"]))

    # Assinatura
    story.append(Spacer(1, 2*cm))
    story.append(Table(
        [[ Paragraph("_" * 45, styles["Valor"]) ]],
        colWidths=[14*cm]
    ))
    story.append(Paragraph(
        f"{relat_dict.get('nome_vet','')} | "
        f"CRMV: {relat_dict.get('crmv','Nao cadastrado')}",
        styles["SubtituloDoc"]
    ))

    _rodape(story, styles, "Relatorio", relat_dict.get("id",""))

    doc.build(story)
    buf.seek(0)
    return buf.read()


def gerar_pdf_historico_animal(dados, nome_vet="", crmv=""):
    """
    Gera PDF do historico clinico completo do animal.
    dados: resultado de historico_clinico_animal()
    """
    import io
    from datetime import date
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        leftMargin=2*cm, rightMargin=2*cm,
        title="Historico Clinico",
    )
    styles  = _estilos()
    story   = []
    animal  = dados.get("animal", {})

    _cabecalho(story, styles, nome_vet, crmv,
               subtitulo="HISTORICO CLINICO DO ANIMAL")

    # Identificacao do animal
    story.append(Paragraph("Identificacao", styles["SecaoTitulo"]))
    id_data = [
        ["Brinco/ID",     animal.get("brinco", "-")],
        ["Raca",          animal.get("raca", "-")],
        ["Sexo",          animal.get("sexo", "-")],
        ["Idade (meses)", str(animal.get("idade", "-"))],
        ["Peso entrada",  f"{animal.get('peso_entrada', 0):.1f} kg"],
        ["Peso alvo",     f"{animal.get('peso_alvo', 0):.1f} kg"],
        ["Lote",          animal.get("lote", "-")],
    ]
    t_id = Table(id_data, colWidths=[5*cm, 13*cm])
    t_id.setStyle(TableStyle([
        ("FONTNAME",   (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME",   (1,0), (1,-1), "Helvetica"),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("ROWPADDING", (0,0), (-1,-1), 5),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [_BEGE, colors.white]),
        ("GRID",       (0,0), (-1,-1), 0.3, _CINZA),
    ]))
    story.append(t_id)

    # Pesagens
    pesagens = dados.get("pesagens", [])
    if pesagens:
        story.append(Spacer(1, 0.4*cm))
        story.append(Paragraph(
            f"Pesagens ({len(pesagens)})", styles["SecaoTitulo"]
        ))
        pes_data = [["Data", "Peso (kg)", "GMD"]]
        prev_p = None
        prev_d = None
        for pes in pesagens[-10:]:  # ultimas 10
            dt_p = str(pes[2])[:10] if len(pes) > 2 else "-"
            wt   = float(pes[3]) if len(pes) > 3 else 0
            gmd  = "-"
            if prev_p and prev_d:
                try:
                    from datetime import datetime
                    d1 = datetime.strptime(prev_d, "%Y-%m-%d").date()
                    d2 = datetime.strptime(dt_p[:10], "%Y-%m-%d").date()
                    dias = (d2 - d1).days
                    if dias > 0:
                        gmd = f"{(wt - prev_p) / dias:.3f} kg/dia"
                except Exception:
                    pass
            dt_fmt = "/".join(reversed(dt_p.split("-"))) if "-" in dt_p else dt_p
            pes_data.append([dt_fmt, f"{wt:.1f}", gmd])
            prev_p, prev_d = wt, dt_p

        t_pes = Table(pes_data, colWidths=[5*cm, 5*cm, 8*cm])
        t_pes.setStyle(TableStyle([
            ("BACKGROUND",  (0,0), (-1,0), _VERDE),
            ("TEXTCOLOR",   (0,0), (-1,0), colors.white),
            ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTNAME",    (0,1), (-1,-1), "Helvetica"),
            ("FONTSIZE",    (0,0), (-1,-1), 8),
            ("ROWPADDING",  (0,0), (-1,-1), 4),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, _BEGE]),
            ("GRID",        (0,0), (-1,-1), 0.3, _CINZA),
        ]))
        story.append(t_pes)

    # Ocorrencias
    ocorrs = dados.get("ocorrencias", [])
    if ocorrs:
        story.append(Spacer(1, 0.4*cm))
        story.append(Paragraph(
            f"Ocorrencias Clinicas ({len(ocorrs)})", styles["SecaoTitulo"]
        ))
        for oc in ocorrs:
            dt_oc = "/".join(reversed(str(oc[2])[:10].split("-")))
            grav  = oc[5] if len(oc) > 5 else ""
            cor_str = "#DC3545" if grav=="Alta"                     else "#FFC107" if grav=="Media"                     else "#6C757D"
            story.append(Paragraph(
                f"<font color='#{cor_str}'>"
                f"[{dt_oc}] {oc[3]} — {grav}</font>",
                styles["Campo"]
            ))
            story.append(Paragraph(str(oc[4])[:200], styles["Valor"]))

    # Exames
    exames = dados.get("exames", [])
    if exames:
        story.append(Spacer(1, 0.4*cm))
        story.append(Paragraph(
            f"Exames Laboratoriais ({len(exames)})", styles["SecaoTitulo"]
        ))
        ex_data = [["Data","Tipo","Lab","Status","Resultado"]]
        for ex in exames:
            dt_ex = "/".join(reversed(str(ex[3])[:10].split("-")))
            ex_data.append([
                dt_ex, str(ex[4])[:20], str(ex[5] or "-")[:15],
                str(ex[8]), str(ex[6] or "-")[:40]
            ])
        t_ex = Table(ex_data, colWidths=[3*cm,4*cm,3*cm,2.5*cm,5.5*cm])
        t_ex.setStyle(TableStyle([
            ("BACKGROUND",  (0,0), (-1,0), _VERDE_CLARO),
            ("TEXTCOLOR",   (0,0), (-1,0), colors.white),
            ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTNAME",    (0,1), (-1,-1), "Helvetica"),
            ("FONTSIZE",    (0,0), (-1,-1), 7),
            ("ROWPADDING",  (0,0), (-1,-1), 3),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, _BEGE]),
            ("GRID",        (0,0), (-1,-1), 0.3, _CINZA),
        ]))
        story.append(t_ex)

    # Carencia
    carencias = dados.get("carencia", [])
    if carencias:
        story.append(Spacer(1, 0.4*cm))
        story.append(Paragraph("Carencias Ativas", styles["SecaoTitulo"]))
        for car in carencias:
            lib = "/".join(reversed(str(car[1])[:10].split("-")))
            story.append(Paragraph(
                f"ATENCAO: {car[0]} — liberacao em {lib}",
                styles["Alerta"]
            ))

    _rodape(story, styles, "Historico Clinico",
            animal.get("brinco", ""))

    doc.build(story)
    buf.seek(0)
    return buf.read()
