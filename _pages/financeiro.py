# pages/financeiro.py -- Telas: Painel de Decisao, Dashboard Executivo, Margem Real, Cotacao Cepea, Rastreabilidade GTA

import streamlit as st
import pandas as pd
from database import *
from ui import (
    card_kpi, card_kpi_row, alerta, badge,
    badge_status_animal, badge_status_lote, badge_gravidade,
    card_animal, insight_card,
)
from rules import (
    is_admin, is_vet, is_fazendeiro, owner_id,
    listar_lotes_usuario, listar_medicamentos_usuario,
    sel_lote, sel_animal, limpar_cache,
    requer_admin, requer_nao_vet, owner_id_lote_novo,
    _listar_lotes_cache, _listar_animais_cache,
)

def hdr(titulo, sub="", desc=""):
    st.title(titulo)
    if sub: st.caption(f"{sub} - {desc}" if desc else sub)
    st.divider()

def page_painel_de_decisao(u):
    hdr("Painel de Decisao", "Decisao Financeira", "Resultado financeiro por lote")
    if is_vet():
        st.error("Acesso restrito. Dados financeiros nao disponiveis para veterinarios.")
        st.stop()
    pk = st.number_input("Preco kg (R$)", 0.0, 50.0, 10.0)
    cd = st.number_input("Custo diario/animal (R$)", 0.0, 100.0, 10.0)
    lotes = listar_lotes_usuario()
    if not lotes: st.warning("Nenhum lote."); st.stop()
    dados = []
    for l in lotes:
        anim = listar_animais_por_lote(l[0])
        ganho = custo_s = dias_t = 0
        for a in anim:
            ps = listar_pesagens(a[0])
            if len(ps) > 1:
                df = pd.DataFrame(ps, columns=["id","aid","peso","data"])
                df["data"] = pd.to_datetime(df["data"])
                df = df.sort_values("data")
                g = df["peso"].iloc[-1]-df["peso"].iloc[0]
                d = (df["data"].iloc[-1]-df["data"].iloc[0]).days
                if g > 0 and d > 0: ganho += g; dias_t += d
            for oc in listar_ocorrencias(a[0]):
                if oc[6]: custo_s += oc[6]
        custo_op = cd * len(anim) * dias_t
        receita  = ganho * pk
        lucro    = receita - custo_op - custo_s
        dados.append((l[1], lucro, receita, custo_op, custo_s))
    df_d = pd.DataFrame(dados, columns=["Lote","Lucro","Receita","Custo Op","Custo San"]).sort_values("Lucro", ascending=False)
    st.metric("Lucro total", f"R$ {df_d['Lucro'].sum():,.2f}")
    st.dataframe(df_d, width='stretch')
    st.bar_chart(df_d.set_index("Lote")["Lucro"])
    st.subheader("Alertas")
    for _, row in df_d.iterrows():
        if row["Lucro"] < 0:                            st.error(f"{row['Lote']}: prejuizo")
        elif row["Custo San"] > row["Receita"] * 0.2:  st.warning(f"{row['Lote']}: custo sanitario elevado")
        else:                                           st.success(f"{row['Lote']}: operacao saudavel")

    # ============================================================
    # DASHBOARD EXECUTIVO
    # ============================================================


def page_dashboard_executivo(u):
    lotes = listar_lotes_usuario()
    hdr("Dashboard Executivo", "Visao Executiva", "KPIs consolidados da fazenda com analise de IA")

    with st.spinner("Carregando dados da fazenda..."):
        if is_vet():
            _lotes_exec = listar_lotes_vet(u["id"])
            _ids_exec   = [l[0] for l in _lotes_exec] if _lotes_exec else []
            kpis = kpis_executivos(owner_id=None, lote_ids=_ids_exec) if _ids_exec else {}
        else:
            kpis = kpis_executivos(owner_id=owner_id())

    if not kpis:
        st.warning("Nenhum lote cadastrado. Cadastre lotes e animais para ver o dashboard.")
        st.stop()

    # ── Linha 1: KPIs principais ──────────────────────────────────────────────
    st.subheader("Visao Geral da Fazenda")
    card_kpi_row([
        dict(titulo="Total de Lotes",     valor=kpis['total_lotes']),
        dict(titulo="Animais Ativos",      valor=kpis['total_animais']),
        dict(titulo="GMD Medio Geral",     valor=f"{kpis['gmd_geral']:.3f} kg/d",
             cor='#1565C0' if kpis['gmd_geral'] >= 0.8 else '#E65100'),
        dict(titulo="Taxa Mortalidade",    valor=f"{kpis['taxa_mortalidade']}%",
             cor='#B71C1C' if kpis['taxa_mortalidade'] > 2 else '#1F5C2E'),
        dict(titulo="Custo Sanitario",     valor=f"R$ {kpis['custo_sanitario']:,.0f}",
             subtitulo=f"R$ {kpis['custo_por_animal']:.0f}/animal"),
    ])
    st.write("")

    # ── Linha 2: Alertas ──────────────────────────────────────────────────────
    col_al1, col_al2, col_al3, col_al4 = st.columns(4)
    with col_al1:
        st.metric("Vacinas Pendentes",  kpis['vacinas_pendentes'],
                 delta="atencao" if kpis['vacinas_pendentes'] > 0 else None,
                 delta_color="inverse")
    with col_al2:
        st.metric("Em Tratamento",      kpis['em_tratamento'],
                 delta="atencao" if kpis['em_tratamento'] > 0 else None,
                 delta_color="inverse")
    with col_al3:
        st.metric("Risco Medio",        f"{kpis['risco_medio']}/100",
                 delta="alto" if kpis['risco_medio'] >= 40 else None,
                 delta_color="inverse")
    with col_al4:
        st.metric("Lotes Alto Risco",   kpis['n_lotes_alto_risco'],
                 delta="critico" if kpis['n_lotes_alto_risco'] > 0 else None,
                 delta_color="inverse")

    st.divider()

    # ── Linha 3: Lote mais critico ────────────────────────────────────────────
    col_crit, col_evol = st.columns([1, 2])

    with col_crit:
        st.subheader("Lote Mais Critico")
        lc = kpis['lote_critico']
        if lc:
            cores_n = {'Critico':'#B71C1C','Alto':'#E65100','Medio':'#F9A825',
                      'Baixo':'#2E7D4F','Saudavel':'#1B5E20'}
            cor_lc = cores_n.get(lc['risco_nivel'], '#546E7A')
            st.markdown(
                f"<div style='background:{cor_lc}22;border-left:4px solid {cor_lc};"
                f"border-radius:8px;padding:16px'>"
                f"<div style='font-size:18px;font-weight:700;color:{cor_lc}'>"
                f"{lc['lote_nome']}</div>"
                f"<div style='font-size:32px;font-weight:700;margin:8px 0'>"
                f"{lc['risco_score']}<span style='font-size:14px'>/100</span></div>"
                f"<div style='font-size:13px;color:#444'>{lc['risco_nivel']}</div>"
                f"<div style='font-size:12px;color:#666;margin-top:8px'>"
                f"{lc['principal_risco']}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
            st.caption(f"{lc['animais_ativos']} animais ativos")
        else:
            st.success("Nenhum lote em situacao critica!")

        st.write("")
        st.subheader("Situacao Sanitaria")
        if kpis['taxa_mortalidade'] >= 3:
            st.error(f"Mortalidade critica: {kpis['taxa_mortalidade']}%")
        elif kpis['taxa_mortalidade'] >= 1:
            st.warning(f"Mortalidade elevada: {kpis['taxa_mortalidade']}%")
        else:
            st.success("Mortalidade dentro do normal")

        if kpis['gmd_geral'] >= 0.8:
            st.success(f"GMD excelente: {kpis['gmd_geral']:.3f} kg/d")
        elif kpis['gmd_geral'] >= 0.5:
            st.warning(f"GMD moderado: {kpis['gmd_geral']:.3f} kg/d")
        else:
            st.error(f"GMD abaixo do esperado: {kpis['gmd_geral']:.3f} kg/d")

    with col_evol:
        st.subheader("Ranking de Risco dos Lotes")
        resumo_r = resumo_ia_fazenda(owner_id=owner_id())
        if resumo_r:
            df_rank = pd.DataFrame(resumo_r)[
                ['lote_nome','risco_nivel','risco_score','animais_ativos','principal_risco']
            ]
            df_rank.columns = ['Lote','Nivel','Score','Animais','Principal Risco']
            st.dataframe(df_rank, width='stretch', hide_index=True)

    st.divider()

    # ── Linha 4: Previsao de abate e anomalias ────────────────────────────────
    col_prev, col_anom = st.columns(2)

    with col_prev:
        st.subheader("Previsao de Abate por Lote")
        col_p1, col_p2 = st.columns(2)
        with col_p1: peso_exec = st.number_input("Peso alvo (kg)", 300.0, 600.0, 450.0, key="exec_pa")
        with col_p2: preco_exec = st.number_input("Preco/kg (R$)", 1.0, 50.0, 10.0, key="exec_pp")

        total_prontos = total_proximos = total_receita = 0
        for lid in [l[0] for l in listar_lotes_usuario()]:
            try:
                prev = prever_abate(lid, peso_exec, preco_exec, 12.0)
                total_prontos  += sum(1 for p in prev if p['status'] == 'Pronto para abate')
                total_proximos += sum(1 for p in prev if p['status'] == 'Proximo do abate')
                total_receita  += sum(p['receita_prevista'] or 0 for p in prev if p['receita_prevista'])
            except Exception:
                pass

        st.metric("Prontos para abate", total_prontos,
                 delta="acao" if total_prontos > 0 else None)
        st.metric("Proximos (30 dias)", total_proximos)
        st.metric("Receita estimada total", f"R$ {total_receita:,.0f}")

    with col_anom:
        st.subheader("Anomalias de Peso Detectadas")
        total_anom = total_graves = 0
        for lid in [l[0] for l in listar_lotes_usuario()]:
            try:
                anoms = detectar_anomalias_peso(lid)
                total_anom   += len(anoms)
                total_graves += sum(1 for a in anoms if a['gravidade'] == 'Alta')
            except Exception:
                pass

        if total_anom == 0:
            st.success("Nenhuma anomalia detectada na fazenda")
        else:
            st.metric("Total de anomalias", total_anom)
            if total_graves > 0:
                st.error(f"{total_graves} anomalia(s) de gravidade ALTA")
            st.caption("Acesse Analise > Anomalias de Peso para detalhes por lote")

    # ============================================================
    # PESQUISAR OCORRENCIAS
    # ============================================================


def page_margem_real(u):
    hdr("Margem Real", "Margem Real do Lote", "Resultado: compra x venda x custos")
    if is_vet():
        st.error("Acesso restrito. Dados financeiros nao disponiveis para veterinarios.")
        st.stop()
    lote_id, _ = sel_lote("margem_lote")
    if lote_id:
        t1,t2 = st.tabs(["Resultado","Registrar Venda"])
        with t1:
            mg = calcular_margem_lote(lote_id)
            if mg:
                if not mg["venda_registrada"]: st.info("Registre uma venda na aba ao lado para ver a margem real.")
                m1,m2,m3 = st.columns(3)
                m1.metric("Custo de compra",  f"R$ {mg['custo_compra']:,.2f}")
                m2.metric("Receita real",      f"R$ {mg['receita_real']:,.2f}")
                m3.metric("Custo sanitario",   f"R$ {mg['custo_sanitario']:,.2f}")
                st.metric("Margem liquida", f"R$ {mg['margem']:,.2f}", delta=f"{mg['margem_pct']:.1f}%",
                          delta_color="normal" if mg["margem"]>=0 else "inverse")
                if mg["venda_registrada"]:
                    st.success(f"Frigorifico: {mg['frigorific']} | Venda: {mg['data_venda']}")
                vendas = listar_vendas_lote(lote_id)
                if vendas:
                    df_v = pd.DataFrame(vendas, columns=["ID","Lote","Data","R$/kg","Peso kg","Frigorifico","Obs"])
                    st.dataframe(df_v, width='stretch')
        with t2:
            st.subheader("Registrar Venda")

            # Calcular peso automatico dos animais
            _animais_lote = listar_animais_por_lote(lote_id)
            _pes_todos = listar_pesagens_todos_animais(lote_id)
            # Peso mais recente por animal
            _peso_map = {}
            for p in _pes_todos:
                aid = p[1]
                if aid not in _peso_map or p[3] > _peso_map[aid][3]:
                    _peso_map[aid] = p
            _peso_total_lote = sum(float(p[2]) for p in _peso_map.values())
            _n_animais = len(_animais_lote)

            st.info(f"Lote com **{_n_animais} animais** | Peso total acumulado: **{_peso_total_lote:.0f} kg**")

            tipo_venda = st.radio("Tipo de venda", ["Lote inteiro", "Animal individual"], horizontal=True, key="tv_radio")

            if tipo_venda == "Animal individual":
                _opts_anim = {f"{a[1]} (ID {a[0]})": a[0] for a in _animais_lote}
                _sel_anim = st.selectbox("Selecionar animal", list(_opts_anim.keys()), key="mv_anim")
                _aid_sel  = _opts_anim[_sel_anim]
                _peso_anim = float(_peso_map[_aid_sel][2]) if _aid_sel in _peso_map else 0.0
                st.caption(f"Ultimo peso registrado: {_peso_anim:.1f} kg")
                _peso_sugerido = _peso_anim
            else:
                _peso_sugerido = _peso_total_lote

            with st.form("form_venda"):
                v1, v2 = st.columns(2)
                with v1:
                    data_v = st.date_input("Data venda")
                    pr_kg  = st.number_input("Preco de venda (R$/kg)", 0.0, 100.0, 22.0)
                with v2:
                    peso_v = st.number_input(
                        "Peso total vendido (kg)",
                        min_value=0.0,
                        value=float(_peso_sugerido),
                        help="Preenchido automaticamente com base nas pesagens. Ajuste se necessario."
                    )
                    frig_v = st.text_input("Frigorifico")
                    obs_v  = st.text_area("Observacao")

                if st.form_submit_button("Registrar Venda", type="primary"):
                    if peso_v > 0:
                        registrar_venda_lote(lote_id, str(data_v), pr_kg, peso_v, frig_v, obs_v)
                        registrar_auditoria(u["id"], "venda_lote", "vendas", lote_id,
                                           f"R${pr_kg}/kg {peso_v}kg ({tipo_venda})")
                        st.success(f"Venda registrada! {peso_v:.0f} kg x R${pr_kg:.2f}/kg = R${peso_v*pr_kg:,.2f}")
                        st.rerun()
                    else:
                        st.error("Informe o peso total.")

    # ============================================================
    # COTACAO CEPEA
    # ============================================================


def page_cotacao_cepea(u):
    hdr("Cotacao Cepea", "Cotacao Boi Gordo", "Preco do boi gordo ESALQ/Cepea")
    c1,c2 = st.columns([2,1])
    with c1:
        if st.button("Buscar cotacao atual"):
            if _CEPEA:
                from cepea import buscar_cotacao_cepea
                with st.spinner("Buscando..."):
                    res = buscar_cotacao_cepea()
                if res["sucesso"]:
                    salvar_cotacao(res["data"], res["preco"], res["fonte"])
                    st.success(f"R$ {res['preco']:.2f}/@ - {res['data']}")
                else:
                    st.warning(f"Indisponivel: {res['msg']}")
            else: st.warning("cepea.py nao encontrado.")
    with c2:
        with st.form("form_cot_m"):
            dt_c = st.date_input("Data")
            pr_c = st.number_input("Preco (R$/@)", 0.0, 1000.0, 195.0)
            if st.form_submit_button("Salvar manual"):
                salvar_cotacao(str(dt_c), pr_c, "manual")
                st.success("Salvo!"); st.rerun()
    cots = listar_cotacoes(0)
    if cots:
        ult = cots[-1]
        st.metric("Ultima cotacao", f"R$ {ult[2]:.2f}/@", delta=f"{ult[1]} ({ult[3]})")
        hist = historico_grafico(cots[-60:])
        if hist["datas"]:
            df_cot = pd.DataFrame({"Data":hist["datas"],"Preco R$/@":hist["precos"]}).set_index("Data")
            st.line_chart(df_cot)
    else:
        st.info("Nenhuma cotacao. Insira manualmente ou clique em buscar.")

    # ============================================================
    # RASTREABILIDADE GTA
    # ============================================================


def page_rastreabilidade_gta(u):
    hdr("Rastreabilidade GTA", "GTA e SISBOV", "Guia de Transito Animal e certificacao")
    if is_vet():
        st.error("Acesso restrito. Rastreabilidade GTA disponivel apenas para fazendeiros e admin.")
        st.stop()
    t1,t2,t3 = st.tabs(["GTAs","Emitir GTA","SISBOV"])
    with t1:
        gtas = listar_gta()
        if gtas:
            df_g = pd.DataFrame(gtas, columns=["ID","Lote ID","Lote","Num GTA","Emissao","Origem","Destino","Qtd","Finalidade","Obs"])
            st.dataframe(df_g, width='stretch')
        else: st.info("Nenhuma GTA.")
    with t2:
        lotes = listar_lotes_usuario()
        if not lotes: st.warning("Cadastre um lote.")
        else:
            dict_l = {f"{l[1]} (ID {l[0]})": l[0] for l in lotes}
            with st.form("form_gta"):
                g1,g2 = st.columns(2)
                with g1:
                    lote_g  = st.selectbox("Lote", list(dict_l.keys()))
                    num_g   = st.text_input("Numero GTA *")
                    data_g  = st.date_input("Data emissao")
                    qtd_g   = st.number_input("Quantidade animais", 1, step=1)
                with g2:
                    orig_g  = st.text_input("Origem *")
                    dest_g  = st.text_input("Destino *")
                    fin_g   = st.selectbox("Finalidade", ["Abate","Venda","Recria","Engorda","Reproducao"])
                    obs_g   = st.text_area("Observacao")
                if st.form_submit_button("Registrar GTA", type="primary"):
                    if num_g and orig_g and dest_g:
                        registrar_gta(dict_l[lote_g], num_g, str(data_g), orig_g, dest_g, int(qtd_g), fin_g, obs_g)
                        registrar_auditoria(u["id"], "gta", "gta", dict_l[lote_g], num_g)
                        st.success("GTA registrada!"); st.rerun()
                    else: st.error("Preencha numero, origem e destino.")
    with t3:
        lotes = listar_lotes_usuario()
        if lotes:
            dict_l = {f"{l[1]} (ID {l[0]})": l[0] for l in lotes}
            s1,s2 = st.columns(2)
            with s1: lote_s = st.selectbox("Lote", list(dict_l.keys()), key="sib_lote")
            anim_s = listar_animais_por_lote(dict_l[lote_s])
            if anim_s:
                dict_as = {f"{a[1]} (ID {a[0]})": a[0] for a in anim_s}
                with s2: anim_ss = st.selectbox("Animal", list(dict_as.keys()), key="sib_anim")
                aid_s = dict_as[anim_ss]
                sb = obter_sisbov(aid_s)
                if sb: st.success(f"SISBOV: **{sb[2]}** - {sb[3]}")
                else:  st.info("Sem SISBOV.")
                with st.form("form_sib"):
                    num_sb = st.text_input("Numero SISBOV (15 digitos)")
                    dt_sb  = st.date_input("Data certificacao")
                    if st.form_submit_button("Cadastrar", type="primary"):
                        if len(num_sb) == 15:
                            registrar_sisbov(aid_s, num_sb, str(dt_sb))
                            st.success("SISBOV cadastrado!"); st.rerun()
                        else: st.error("SISBOV deve ter 15 digitos.")

    # ============================================================
    # EXPORTAR RELATORIOS
    # ============================================================
