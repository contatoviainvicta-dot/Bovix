"""
_pages/dashboard_exec.py
Dashboard Executivo do Fazendeiro — KPIs + DRE + Ranking + Projeção de Abate
"""
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import date, datetime

from database import (
    dashboard_financeiro_fazendeiro,
    calendario_abate,
    adicionar_custo_lote,
    listar_custos_lote,
    listar_lotes,
    margem_bruta_lote,
)
from rules import owner_id as get_oid


def _brl(v):
    """Formata valor em BRL."""
    try:
        v = float(v)
        neg = v < 0
        s = f"R$ {abs(v):,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"-{s}" if neg else s
    except Exception:
        return "R$ 0"


def _cor_margem(pct):
    if pct >= 20:   return "#1D9E75"
    if pct >= 10:   return "#BA7517"
    if pct >= 0:    return "#E24B4A"
    return "#991B1B"


def page_dashboard_executivo(u):
    oid = u.get("owner_id") or u["id"]

    st.title("Dashboard Executivo")
    st.caption("Visão financeira completa da sua operação")

    with st.spinner("Calculando indicadores..."):
        dados = dashboard_financeiro_fazendeiro(oid)

    if not dados["lotes"]:
        st.info(
            "Nenhum lote encontrado. Cadastre lotes e animais para ver "
            "os indicadores financeiros."
        )
        return

    kpis    = dados["kpis"]
    dre     = dados["dre"]
    alertas = dados["alertas"]
    ranking = dados["ranking"]

    # ── ALERTAS FINANCEIROS ──────────────────────────────────────────────
    if alertas:
        alts_alta  = [a for a in alertas if a["prioridade"] == "alta"]
        alts_media = [a for a in alertas if a["prioridade"] == "media"]
        if alts_alta:
            for a in alts_alta:
                st.error(f"🔴 **{a['lote']}** — {a['msg']}")
        if alts_media:
            for a in alts_media:
                st.warning(f"⚠ **{a['lote']}** — {a['msg']}")
        st.divider()

    # ── KPIs PRINCIPAIS ──────────────────────────────────────────────────
    st.subheader("Visão Geral")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Lotes ativos",      kpis["total_lotes"],
              delta=f"{kpis['total_animais']} animais")
    k2.metric("Total investido",   _brl(kpis["total_investido"]))
    k3.metric("Receita realizada", _brl(kpis["receita_realizada"]),
              delta=f"{kpis['lotes_vendidos']} lote(s) vendido(s)")
    k4.metric("Margem bruta",      _brl(kpis["total_margem"]),
              delta=f"{kpis['margem_pct']}%",
              delta_color="normal" if kpis["margem_pct"] >= 0 else "inverse")

    k5, k6, k7, k8 = st.columns(4)
    k5.metric("Receita projetada", _brl(kpis["receita_projetada"]),
              help="Receita esperada dos lotes ainda não vendidos")
    k6.metric("Lotes no positivo", kpis["lotes_positivos"],
              delta_color="normal")
    k7.metric("Lotes no negativo", kpis["lotes_negativos"],
              delta_color="inverse" if kpis["lotes_negativos"] > 0 else "off")
    k8.metric("Resultado total",
              _brl(kpis["receita_realizada"] + kpis["receita_projetada"] - kpis["total_investido"]))

    st.divider()

    # ── ABAS PRINCIPAIS ──────────────────────────────────────────────────
    t1, t2, t3, t4, t5 = st.tabs([
        "DRE", "Ranking Lotes", "Projeção de Abate",
        "Lançar Custo", "Detalhes por Lote"
    ])

    # ── ABA 1: DRE ───────────────────────────────────────────────────────
    with t1:
        st.subheader("DRE Simplificado")

        # Montar HTML do DRE
        linhas_dre = [
            ("(+) Receita bruta",        dre["receita_bruta"],     False, True),
            ("(-) Custo de compra",       dre["custo_compra"],      False, False),
            ("(-) Custos variáveis",      dre["custos_var"],        False, False),
            ("(=) Margem bruta",          dre["margem_bruta"],      True,  True),
        ]
        html_dre = """
        <table style='width:100%;border-collapse:collapse;font-size:14px'>
        <tr style='background:#f8f8f8'>
            <th style='text-align:left;padding:10px 12px;
                border-bottom:2px solid #1D9E75;color:#1a1a1a'>Item</th>
            <th style='text-align:right;padding:10px 12px;
                border-bottom:2px solid #1D9E75;color:#1a1a1a'>Valor</th>
            <th style='text-align:right;padding:10px 12px;
                border-bottom:2px solid #1D9E75;color:#1a1a1a'>%</th>
        </tr>"""
        receita_ref = max(dre["receita_bruta"], 1)
        for desc, val, negrito, destaque in linhas_dre:
            pct     = round(100 * val / receita_ref, 1)
            cor_val = "#1D9E75" if val >= 0 else "#E24B4A"
            fw      = "700" if negrito else "400"
            bg      = "#E1F5EE" if destaque and val >= 0 \
                      else "#FCEBEB" if destaque else "white"
            bdr     = "2px solid #1D9E75" if destaque else \
                      "0.5px solid #f0f0f0"
            sinal   = "-" if desc.startswith("(-)") else ""
            val_str = f"{sinal}R$ {abs(val):,.0f}"
            html_dre += f"""
            <tr style='background:{bg};border-bottom:{bdr}'>
                <td style='padding:10px 12px;font-weight:{fw};
                    color:#1a1a1a'>{desc}</td>
                <td style='padding:10px 12px;text-align:right;
                    font-weight:{fw};color:{cor_val}'>{val_str}</td>
                <td style='padding:10px 12px;text-align:right;
                    color:#666;font-size:12px'>{pct}%</td>
            </tr>"""
        html_dre += "</table>"
        components.html(html_dre, height=220)

        # Gráfico de pizza custos vs margem
        st.divider()
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.caption("Composição do investimento")
            df_comp = pd.DataFrame({
                "Categoria": ["Compra de animais", "Custos variáveis"],
                "Valor":     [dre["custo_compra"], max(dre["custos_var"], 0)]
            })
            st.bar_chart(df_comp.set_index("Categoria"))
        with col_g2:
            st.caption("Receita × Custo × Margem")
            df_res = pd.DataFrame({
                "Item":  ["Receita", "Custo total", "Margem"],
                "Valor": [dre["receita_bruta"],
                         dre["custo_total"],
                         max(dre["margem_bruta"], 0)]
            })
            st.bar_chart(df_res.set_index("Item"))

    # ── ABA 2: RANKING DE LOTES ──────────────────────────────────────────
    with t2:
        st.subheader("Ranking por Margem")
        if not ranking:
            st.info("Nenhum dado de lote disponível.")
        else:
            # Tabela de ranking
            df_rank = pd.DataFrame([{
                "Pos":      f"#{i+1}",
                "Lote":     m["nome"],
                "Animais":  m["n_animais"],
                "Investido":_brl(m["custo_total"]),
                "Receita":  _brl(m["receita"]),
                "Margem R$":_brl(m["margem_r"]),
                "Margem %": f"{m['margem_pct']}%",
                "Status":   "Vendido" if m["vendido"] else "Ativo",
                "Dias":     m["dias_confinamento"],
            } for i, m in enumerate(ranking)])

            st.dataframe(
                df_rank,
                hide_index=True,
                width="stretch",
            )

            # Top 3 e bottom 1
            st.divider()
            col_t, col_b = st.columns(2)
            with col_t:
                st.caption("Melhor lote")
                melhor = ranking[0]
                st.metric(melhor["nome"],
                         _brl(melhor["margem_r"]),
                         delta=f"{melhor['margem_pct']}%")
            with col_b:
                if len(ranking) > 1:
                    st.caption("Pior lote")
                    pior = ranking[-1]
                    st.metric(pior["nome"],
                             _brl(pior["margem_r"]),
                             delta=f"{pior['margem_pct']}%",
                             delta_color="inverse" if pior["margem_pct"] < 0 else "normal")

    # ── ABA 3: PROJEÇÃO DE ABATE ─────────────────────────────────────────
    with t3:
        st.subheader("Calendário de Abate Projetado")
        st.caption(
            "Previsão calculada com base no GMD (ganho médio diário) "
            "de cada animal e o peso alvo do lote."
        )

        with st.spinner("Calculando projeções..."):
            cal = calendario_abate(oid)

        if not cal:
            st.info(
                "Sem dados suficientes para projeção. "
                "São necessárias ao menos 2 pesagens por animal."
            )
        else:
            # Timeline visual
            hoje_str = str(date.today())
            for c in cal:
                dias = c["dias_restantes"]
                cor  = "#1D9E75" if dias > 60 else \
                       "#BA7517" if dias > 30 else "#E24B4A"
                dt_f = "/".join(reversed(c["data_abate"].split("-")))

                with st.expander(
                    f"🗓 {c['nome']} — abate previsto: {dt_f} "
                    f"({'em ' + str(dias) + ' dias' if dias > 0 else 'passou do prazo'})"
                ):
                    ca1, ca2, ca3, ca4 = st.columns(4)
                    ca1.metric("Animais",      c["n_animais"])
                    ca2.metric("Peso atual",   f"{c['peso_atual']} kg")
                    ca3.metric("Peso alvo",    f"{c['peso_alvo']} kg")
                    ca4.metric("Receita proj.",_brl(c["receita_proj"]),
                              help=f"Cotação: R$ {c['cotacao']:.2f}/@ ")

                    # Barra de progresso peso
                    if c["peso_alvo"] > 0:
                        pct_peso = min(
                            int(100 * c["peso_atual"] / c["peso_alvo"]), 100
                        )
                        st.caption(
                            f"Progresso de peso: {c['peso_atual']}/"
                            f"{c['peso_alvo']} kg ({pct_peso}%)"
                        )
                        st.progress(pct_peso / 100)

            # Tabela resumo
            st.divider()
            df_cal = pd.DataFrame([{
                "Lote":          c["nome"],
                "Animais":       c["n_animais"],
                "Abate previsto":"/".join(reversed(c["data_abate"].split("-"))),
                "Dias restantes":c["dias_restantes"],
                "Peso atual":    f"{c['peso_atual']} kg",
                "Receita proj.": _brl(c["receita_proj"]),
            } for c in cal])
            st.dataframe(df_cal, hide_index=True, width="stretch")

            total_proj = sum(c["receita_proj"] for c in cal)
            st.metric("Receita total projetada (todos os lotes)",
                     _brl(total_proj))

    # ── ABA 4: LANÇAR CUSTO ──────────────────────────────────────────────
    with t4:
        st.subheader("Lançar Custo Variável")
        st.caption(
            "Registre custos de ração, medicamentos, mão de obra, "
            "frete e outros para calcular a margem real."
        )

        lotes_ativos = [l for l in listar_lotes(owner_id=oid)]
        if not lotes_ativos:
            st.warning("Nenhum lote disponível.")
        else:
            dict_lotes = {l[1]: l[0] for l in lotes_ativos}
            with st.form("form_custo"):
                c1, c2 = st.columns(2)
                with c1:
                    lote_sel  = st.selectbox("Lote *", list(dict_lotes.keys()))
                    categoria = st.selectbox("Categoria *", [
                        "racao", "medicamento", "mao_de_obra",
                        "frete", "veterinario", "manutencao", "outros"
                    ])
                with c2:
                    valor     = st.number_input("Valor (R$) *",
                                               min_value=0.0, step=10.0,
                                               format="%.2f")
                    data_lanc = st.date_input("Data", value=date.today())
                descricao = st.text_input(
                    "Descrição *",
                    placeholder="Ex: Ração concentrada 500kg"
                )
                obs = st.text_input("Observações")

                if st.form_submit_button("Lançar custo", type="primary"):
                    if not descricao or valor <= 0:
                        st.error("Informe descrição e valor.")
                    else:
                        adicionar_custo_lote(
                            lote_id=dict_lotes[lote_sel],
                            categoria=categoria,
                            descricao=descricao,
                            valor=valor,
                            data_lancamento=str(data_lanc),
                            observacoes=obs or ""
                        )
                        st.success(
                            f"Custo de {_brl(valor)} lançado em {lote_sel}!"
                        )
                        st.rerun()

            # Histórico de custos
            st.divider()
            st.subheader("Histórico de Custos")
            lote_hist = st.selectbox(
                "Ver custos do lote",
                list(dict_lotes.keys()),
                key="hist_custo_lote"
            )
            custos = listar_custos_lote(dict_lotes[lote_hist])
            if custos:
                df_cust = pd.DataFrame(custos, columns=[
                    "ID","LoteID","Categoria","Descrição",
                    "Valor","Data","Obs"
                ])
                df_cust["Valor"] = df_cust["Valor"].apply(_brl)
                st.dataframe(
                    df_cust[["Data","Categoria","Descrição","Valor","Obs"]],
                    hide_index=True,
                    width="stretch"
                )
                total_c = sum(float(c[4]) for c in custos)
                st.metric("Total de custos variáveis", _brl(total_c))
            else:
                st.info("Nenhum custo lançado neste lote ainda.")

    # ── ABA 5: DETALHES POR LOTE ─────────────────────────────────────────
    with t5:
        st.subheader("Análise Detalhada por Lote")
        lotes_disp = [l for l in lotes_ativos]
        dict_l2    = {l[1]: l[0] for l in lotes_disp}
        lote_sel2  = st.selectbox("Lote", list(dict_l2.keys()), key="det_lote")

        with st.spinner("Calculando..."):
            det = margem_bruta_lote(dict_l2[lote_sel2])

        if not det:
            st.warning("Sem dados para este lote.")
        else:
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Custo de compra",  _brl(det["custo_compra"]))
            d2.metric("Custos variáveis", _brl(det["total_custos_var"]))
            d3.metric("Custo por animal", _brl(det["custo_ua"]))
            d4.metric("Dias confinado",   det["dias_confinamento"])

            d5, d6, d7, d8 = st.columns(4)
            d5.metric("Peso médio atual",
                     f"{det['peso_medio_atual']} kg")
            d6.metric("Peso médio alvo",
                     f"{det['peso_medio_alvo']} kg")
            d7.metric("Receita projetada",
                     _brl(det["receita_projetada"]))
            d8.metric("Margem bruta",
                     _brl(det["margem_r"]),
                     delta=f"{det['margem_pct']}%",
                     delta_color="normal" if det["margem_pct"] >= 0 else "inverse")

            if det["custos_var"]:
                st.divider()
                st.caption("Composição dos custos variáveis")
                df_cv = pd.DataFrame(
                    list(det["custos_var"].items()),
                    columns=["Categoria", "Total"]
                )
                df_cv["Total"] = df_cv["Total"].apply(_brl)
                st.dataframe(df_cv, hide_index=True, width="stretch")
