# pages/gestao.py -- Telas: Calendario Sanitario, Estoque Medicamentos, Controle Reprodutivo, Mapa Piquetes, Workspace do Lote, Prontuario Animal

import streamlit as st
import pandas as pd
from datetime import datetime, date
from database import *
try:
    from exports import gerar_excel_lote, gerar_pdf_relatorio
except ImportError:
    def gerar_excel_lote(*a, **k): return b""
    def gerar_pdf_relatorio(*a, **k): return b""

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

def page_calendario_sanitario(u):
    hdr("Calendario Sanitario", "Vacinas e Medicacoes", "Agenda de vacinas e alertas")
    t1,t2,t3 = st.tabs(["Agenda","Agendar","Confirmar"])
    with t1:
        lotes = listar_lotes_usuario()
        if lotes:
            d = {"Todos": None, **{f"{l[1]} (ID {l[0]})": l[0] for l in lotes}}
            f  = st.selectbox("Lote", list(d.keys()), key="cal_f")
            vs = listar_vacinas_agenda(d[f])
            if vs:
                df_v = pd.DataFrame(vs, columns=["ID","Lote","Vacina","Previsto","Realizado","Status","Obs"])
                st.dataframe(df_v, use_container_width=True)
                hoje = date.today()
                for _, row in df_v.iterrows():
                    try:
                        dt_p = datetime.strptime(str(row["Previsto"]), "%Y-%m-%d").date()
                        atrasado = dt_p < hoje and row["Status"]=="pendente"
                    except: atrasado = False
                    if row["Status"]=="realizado":  st.success(f"{row['Vacina']} - realizada")
                    elif atrasado:                  st.error(f"ATRASADA: {row['Vacina']} - previsto {row['Previsto']}")
                    else:                           st.warning(f"Pendente: {row['Vacina']} - {row['Previsto']}")
            else: st.info("Nenhuma vacina agendada.")
    with t2:
        lotes = listar_lotes_usuario()
        if not lotes: st.warning("Cadastre um lote.")
        else:
            dict_l = {f"{l[1]} (ID {l[0]})": l[0] for l in lotes}
            with st.form("form_vac"):
                vs1,vs2 = st.columns(2)
                with vs1:
                    lote_v = st.selectbox("Lote", list(dict_l.keys()))
                    nome_v = st.text_input("Nome da vacina *")
                with vs2:
                    data_v = st.date_input("Data prevista", value=date.today()+timedelta(days=7))
                    obs_v  = st.text_area("Observacao")
                if st.form_submit_button("Agendar", type="primary"):
                    if nome_v:
                        adicionar_vacina_agenda(dict_l[lote_v], nome_v, str(data_v), obs_v)
                        st.success("Agendado!"); st.rerun()
                    else: st.error("Informe o nome.")
    with t3:
        pend_v = listar_vacinas_pendentes(owner_id=owner_id())
        if not pend_v: st.success("Nenhuma vacina pendente.")
        else:
            df_p = pd.DataFrame(pend_v, columns=["ID","Lote ID","Lote","Vacina","Previsto","Status","Obs"])
            op   = {f"{r['Vacina']} - {r['Lote']} (prev. {r['Previsto']})": r["ID"] for _,r in df_p.iterrows()}
            with st.form("form_real_v"):
                sel_v = st.selectbox("Vacina", list(op.keys()))
                dt_r  = st.date_input("Data realizacao")
                if st.form_submit_button("Confirmar", type="primary"):
                    registrar_vacina_realizada(op[sel_v], str(dt_r))
                    st.success("Registrado!"); st.rerun()

    # ============================================================
    # ESTOQUE MEDICAMENTOS
    # ============================================================


def page_estoque_medicamentos(u):
    hdr("Estoque Medicamentos", "Controle de Medicamentos", "Estoque, validade e uso")
    t1,t2,t3 = st.tabs(["Estoque","Cadastrar","Registrar Uso"])
    with t1:
        meds  = listar_medicamentos_usuario()
        crits = listar_medicamentos_criticos()
        if crits:
            for m in crits:
                mot = "estoque baixo" if m[3]<=m[4] else f"vence {m[5]}"
                st.error(f"{m[1]} - {m[3]:.1f} {m[2]} ({mot})")
        if meds:
            df_m = pd.DataFrame(meds, columns=["ID","Nome","Unidade","Estoque","Minimo","Validade","Custo Unit."])
            st.dataframe(df_m, use_container_width=True)
            m1,m2 = st.columns(2)
            m1.metric("Valor total estoque", f"R$ {sum(m[3]*m[6] for m in meds):,.2f}")
            m2.metric("Itens cadastrados",   len(meds))
        else: st.info("Nenhum medicamento.")
    with t2:
        with st.form("form_med"):
            mn1,mn2 = st.columns(2)
            with mn1:
                nome_md = st.text_input("Nome *")
                unid_md = st.selectbox("Unidade", ["dose","mL","g","comprimido","frasco","kg"])
                estq_md = st.number_input("Estoque inicial", 0.0, step=1.0)
            with mn2:
                emin_md = st.number_input("Estoque minimo (alerta)", 0.0, step=1.0)
                val_md  = st.date_input("Validade")
                cust_md = st.number_input("Custo unitario (R$)", 0.0)
            if st.form_submit_button("Cadastrar", type="primary"):
                if nome_md:
                    adicionar_medicamento(nome_md, unid_md, estq_md, emin_md, str(val_md), cust_md, owner_id=u.get("owner_id", u["id"]))
                    st.success("Medicamento cadastrado!"); st.rerun()
                else: st.error("Informe o nome.")
    with t3:
        meds  = listar_medicamentos_usuario()
        lotes = listar_lotes_usuario()
        if not meds or not lotes: st.warning("Cadastre medicamentos e lotes.")
        else:
            dict_md = {f"{m[1]} ({m[3]:.1f} {m[2]})": m[0] for m in meds}
            dict_l  = {f"{l[1]} (ID {l[0]})": l[0] for l in lotes}
            with st.form("form_uso_md"):
                u1,u2 = st.columns(2)
                with u1:
                    med_s  = st.selectbox("Medicamento", list(dict_md.keys()))
                    lote_s = st.selectbox("Lote", list(dict_l.keys()))
                with u2:
                    animais_u = listar_animais_por_lote(dict_l[lote_s])
                    dict_au   = {f"{a[1]} (ID {a[0]})": a[0] for a in animais_u}
                    anim_s    = st.selectbox("Animal", list(dict_au.keys()) if dict_au else ["--"])
                    qtd_u     = st.number_input("Quantidade", 0.01, step=0.5)
                    data_u    = st.date_input("Data")
                if st.form_submit_button("Registrar", type="primary") and dict_au:
                    registrar_uso_medicamento(dict_md[med_s], dict_au[anim_s], str(data_u), qtd_u)
                    st.success("Uso registrado e estoque atualizado!"); st.rerun()

    # ============================================================
    # CONTROLE REPRODUTIVO
    # ============================================================


def page_controle_reprodutivo(u):
    parto = listar_partos_previstos(owner_id=owner_id())
    hdr("Controle Reprodutivo", "Reproducao", "IATF, diagnostico, prenhez e partos")
    t1,t2,t3,t4 = st.tabs(["Indicadores","Registrar","Diagnostico","Partos"])
    with t1:
        lote_id, _ = sel_lote("rep_ind")
        if lote_id:
            tp = taxa_prenhez_lote(lote_id)
            c1,c2,c3 = st.columns(3)
            c1.metric("Com registro", tp["total"])
            c2.metric("Positivas",    tp["positivas"])
            c3.metric("Taxa prenhez", f"{tp['taxa']:.1f}%")
    with t2:
        lotes = listar_lotes_usuario()
        if lotes:
            dict_l = {f"{l[1]} (ID {l[0]})": l[0] for l in lotes}
            with st.form("form_cob"):
                r1,r2 = st.columns(2)
                with r1:
                    lote_r = st.selectbox("Lote", list(dict_l.keys()))
                    anim_r = listar_animais_por_lote(dict_l[lote_r])
                    dict_ar = {f"{a[1]} (ID {a[0]})": a[0] for a in anim_r}
                    anim_rs = st.selectbox("Animal", list(dict_ar.keys()) if dict_ar else ["--"])
                with r2:
                    tipo_r = st.selectbox("Tipo", ["IATF","Monta Natural","TE"])
                    data_r = st.date_input("Data cio / IATF")
                    obs_r  = st.text_area("Observacao")
                if st.form_submit_button("Registrar", type="primary") and dict_ar:
                    adicionar_reproducao(dict_ar[anim_rs], tipo_r, data_cio=str(data_r), observacao=obs_r)
                    st.success("Cobertura registrada!"); st.rerun()
    with t3:
        lotes = listar_lotes_usuario()
        if lotes:
            dict_l = {f"{l[1]} (ID {l[0]})": l[0] for l in lotes}
            d1,d2 = st.columns(2)
            with d1: lote_ds = st.selectbox("Lote", list(dict_l.keys()), key="diag_lote")
            anim_d = listar_animais_por_lote(dict_l[lote_ds])
            dict_ad = {f"{a[1]} (ID {a[0]})": a[0] for a in anim_d}
            if dict_ad:
                with d2: anim_ds = st.selectbox("Animal", list(dict_ad.keys()), key="diag_anim")
                repros = listar_reproducao(dict_ad[anim_ds])
                if repros:
                    r = repros[0]
                    st.info(f"Ultimo registro: {r[3]} | Resultado: {r[5]}")
                    with st.form("form_diag"):
                        resultado = st.selectbox("Resultado", ["pendente","positivo","negativo"])
                        data_diag = st.date_input("Data diagnostico")
                        parto_p   = st.date_input("Parto previsto", value=date.today()+timedelta(days=283))
                        if st.form_submit_button("Salvar", type="primary"):
                            atualizar_reproducao(r[0], resultado,
                                data_diagnostico=str(data_diag),
                                data_parto_previsto=str(parto_p) if resultado=="positivo" else None)
                            st.success("Atualizado!"); st.rerun()
                else: st.info("Sem registros reprodutivos.")
    with t4:
        partos = listar_partos_previstos()
        if partos:
            df_p = pd.DataFrame(partos, columns=["ID","Animal","Lote","Parto Previsto","Tipo"])
            st.dataframe(df_p, use_container_width=True)
        else: st.success("Nenhum parto previsto nos proximos 30 dias.")

    # ============================================================
    # MAPA PIQUETES
    # ============================================================


def page_mapa_piquetes(u):
    hdr("Mapa Piquetes", "Pastagens e Piquetes", "Alocacao de lotes e historico")
    t1,t2,t3 = st.tabs(["Piquetes","Cadastrar","Alocar / Liberar"])
    with t1:
        pqs = listar_piquetes()
        if pqs:
            df_pq = pd.DataFrame(pqs, columns=["ID","Fazenda","Nome","Area ha","Cap UA"])
            st.dataframe(df_pq, use_container_width=True)
            p1,p2 = st.columns(2)
            p1.metric("Total piquetes", len(pqs))
            p2.metric("Area total (ha)", f"{sum(p[3] for p in pqs):.1f}")
            dict_pq = {f"{p[2]} (ID {p[0]})": p[0] for p in pqs}
            sel_pq  = st.selectbox("Historico do piquete", list(dict_pq.keys()))
            hist = historico_piquete(dict_pq[sel_pq])
            if hist:
                df_h = pd.DataFrame(hist, columns=["ID","Lote","Entrada","Saida"])
                st.dataframe(df_h, use_container_width=True)
            else: st.info("Nenhum historico.")
        else: st.info("Nenhum piquete cadastrado.")
    with t2:
        with st.form("form_pq"):
            pq1,pq2,pq3 = st.columns(3)
            with pq1: nome_pq = st.text_input("Nome *")
            with pq2: area_pq = st.number_input("Area (ha)", 0.0, step=0.5)
            with pq3: cap_pq  = st.number_input("Capacidade (UA)", 0.0, step=1.0)
            if st.form_submit_button("Cadastrar", type="primary"):
                if nome_pq:
                    adicionar_piquete(nome_pq, area_pq, cap_pq)
                    st.success("Piquete cadastrado!"); st.rerun()
                else: st.error("Informe o nome.")
    with t3:
        pqs   = listar_piquetes()
        lotes = listar_lotes_usuario()
        if not pqs or not lotes: st.warning("Cadastre piquetes e lotes.")
        else:
            dict_pq = {f"{p[2]} (ID {p[0]})": p[0] for p in pqs}
            dict_l  = {f"{l[1]} (ID {l[0]})": l[0] for l in lotes}
            al1,al2 = st.columns(2)
            with al1:
                st.subheader("Alocar")
                with st.form("form_aloc"):
                    pq_a  = st.selectbox("Piquete", list(dict_pq.keys()), key="al_pq")
                    lt_a  = st.selectbox("Lote",    list(dict_l.keys()),  key="al_lt")
                    dt_a  = st.date_input("Entrada",                      key="al_dt")
                    if st.form_submit_button("Alocar", type="primary"):
                        alocar_lote_piquete(dict_pq[pq_a], dict_l[lt_a], str(dt_a))
                        st.success("Alocado!"); st.rerun()
            with al2:
                st.subheader("Liberar")
                with st.form("form_lib"):
                    pq_l = st.selectbox("Piquete", list(dict_pq.keys()), key="lib_pq")
                    dt_l = st.date_input("Saida",                        key="lib_dt")
                    if st.form_submit_button("Liberar", type="primary"):
                        liberar_piquete(dict_pq[pq_l], str(dt_l))
                        st.success("Piquete liberado!"); st.rerun()

    # ============================================================
    # PREVISAO ABATE
    # ============================================================


def page_workspace_do_lote(u):
    hdr("Workspace do Lote", "Visao Completa", "Tudo sobre o lote em um lugar so")

    lotes = listar_lotes_usuario()
    if not lotes:
        st.warning("Nenhum lote cadastrado.")
        st.stop()

    # Selector do lote no topo
    _lotes_ws_raw = listar_lotes_usuario()
    todos_lotes_ws = [(l[0],l[1],l[2],l[3],l[4],l[5],l[6],l[7] if len(l)>7 else "ATIVO") for l in _lotes_ws_raw]
    dict_ws = {f"{l[1]}": l[0] for l in todos_lotes_ws}

    col_sel, col_status = st.columns([3, 1])
    with col_sel:
        lote_ws_nome = st.selectbox("Selecione o lote", list(dict_ws.keys()), key="ws_lote")
    lote_ws_id = dict_ws[lote_ws_nome]

    @st.cache_data(ttl=300, show_spinner="Carregando dados do lote...")
    def _ws_dados(lid):
        _raw = listar_lotes_usuario()
        todos = [(l[0],l[1],l[2],l[3],l[4],l[5],l[6],l[7] if len(l)>7 else "ATIVO") for l in _raw]
        return dict(
            lote        = obter_lote(lid),
            status      = next((l[7] for l in todos if l[0]==lid), "ATIVO"),
            rs          = resumo_lote(lid),
            animais     = listar_animais_por_lote(lid),
            mort        = taxa_mortalidade_lote(lid),
            gmds_map    = calcular_gmds_lote(lid),
            insights    = gerar_insights_lote(lid),
            gtas        = listar_gta(lid),
            movs        = listar_movimentacoes(lote_id=lid),
            vacs        = listar_vacinas_agenda(lid),
            plote       = listar_pesagens_lote(lid),
            todas_ocs   = listar_ocorrencias_todos_animais(lid),
            vendas      = listar_vendas_lote(lid),
            scores      = calcular_scores_lote(lid),
            cont_status = contagem_status_animais(lid),
        )

    _ws = _ws_dados(lote_ws_id)
    lote_ws        = _ws['lote']
    lote_ws_status = _ws['status']
    rs_ws          = _ws['rs']
    animais_ws     = _ws['animais']
    mort_ws        = _ws['mort']
    gmds_ws_map    = _ws['gmds_map']
    gmds_ws        = [g for g in gmds_ws_map.values() if g >= 0]
    gmd_ws         = sum(gmds_ws)/len(gmds_ws) if gmds_ws else 0

    with col_status:
        st.write("")
        st.markdown(
            badge_status_lote(lote_ws_status),
            unsafe_allow_html=True
        )

    st.divider()

    card_kpi_row([
        dict(titulo="Animais Ativos",    valor=rs_ws['ativos'],
             subtitulo=f"de {rs_ws['total_animais']} totais"),
        dict(titulo="GMD Medio",         valor=f"{gmd_ws:.3f} kg/d",
             subtitulo="ganho diario medio",
             cor='#1565C0' if gmd_ws >= 0.8 else '#E65100'),
        dict(titulo="Mortalidade",       valor=f"{mort_ws['taxa']}%",
             subtitulo=f"{mort_ws['mortos']} morte(s)",
             cor='#B71C1C' if mort_ws['taxa'] > 2 else '#1F5C2E'),
        dict(titulo="Custo Sanitario",   valor=f"R$ {rs_ws['custo_sanitario']:.0f}",
             subtitulo=f"{rs_ws['ocorrencias']} ocorrencia(s)"),
        dict(titulo="Vacinas Pendentes", valor=rs_ws['vacinas_pendentes'],
             cor='#E65100' if rs_ws['vacinas_pendentes'] > 0 else '#1F5C2E'),
    ])

    st.write("")

    # Insights automáticos
    insights_ws = gerar_insights_lote(lote_ws_id)
    if insights_ws:
        cols_ins = st.columns(min(len(insights_ws), 3))
        for i, ins in enumerate(insights_ws):
            with cols_ins[i % 3]:
                st.markdown(
                    insight_card(ins['titulo'], ins['descricao'], ins['tipo'], ins.get('acao')),
                    unsafe_allow_html=True
                )
        st.write("")

    # Abas do workspace
    if is_vet():
        aba_res, aba_anim, aba_pes, aba_san, aba_rel = st.tabs([
            "Resumo", "Animais", "Pesagens", "Sanidade", "Relatorios"
        ])
        aba_fin = None
    else:
        aba_res, aba_anim, aba_pes, aba_san, aba_fin, aba_rel = st.tabs([
            "Resumo", "Animais", "Pesagens", "Sanidade", "Financeiro", "Relatorios"
        ])

    # ── ABA RESUMO ────────────────────────────────────────────────────────────
    with aba_res:
        c1_r, c2_r = st.columns(2)

        with c1_r:
            st.subheader("Informacoes do Lote")
            if lote_ws:
                st.write(f"**Data de entrada:** {lote_ws[3]}")
                st.write(f"**Transportadora:** {lote_ws[6] or 'Nao informada'}")
                st.write(f"**Descricao:** {lote_ws[2] or 'Sem descricao'}")
                st.write(f"**Preco por animal:** R$ {lote_ws[3] or 0}")

            st.subheader("Status dos animais")
            cont_ws = _ws['cont_status']
            for status_k, qtd_k in cont_ws.items():
                if qtd_k > 0:
                    st.markdown(
                        f"{badge_status_animal(status_k)} {qtd_k} animal(is)",
                        unsafe_allow_html=True
                    )

        with c2_r:
            st.subheader("Movimentacoes recentes")
            movs_ws = listar_movimentacoes(lote_id=lote_ws_id)
            if movs_ws:
                for mv in movs_ws[:5]:
                    st.caption(f"{mv[5]} | {mv[2]} | {mv[3]} -> {mv[4]} | {mv[6] or 'sem motivo'}")
            else:
                st.info("Nenhuma movimentacao registrada.")

            st.subheader("GTAs emitidas")
            gtas_ws = listar_gta(lote_ws_id)
            if gtas_ws:
                for g in gtas_ws[:3]:
                    st.caption(f"{g[4]} | GTA {g[3]} | {g[7]} animais | {g[8]}")
            else:
                st.info("Nenhuma GTA emitida.")

    # ── ABA ANIMAIS ───────────────────────────────────────────────────────────
    with aba_anim:
        filtro_status = st.selectbox(
            "Filtrar por status", ["Todos"] + STATUS_ANIMAL, key="ws_filtro_anim"
        )
        if filtro_status == "Todos":
            lista_anim_ws = listar_animais_por_status(lote_ws_id)
        else:
            lista_anim_ws = listar_animais_por_status(lote_ws_id, filtro_status)

        st.caption(f"{len(lista_anim_ws)} animal(is) encontrado(s)")
        st.write("")

        # Usar dados ja carregados no cache
        scores_ws_map = _ws['scores']
        ocs_ws_map = {}
        for oc_row in _ws['todas_ocs']:
            ocs_ws_map.setdefault(oc_row[1], []).append(oc_row)

        cards_html = ""
        for a_row in lista_anim_ws:
            aid_r, ident_r = a_row[0], a_row[1]
            status_r = a_row[4] if len(a_row) > 4 else 'ATIVO'
            sc_r  = scores_ws_map.get(aid_r, dict(score=65, gmd=0.0))
            n_oc  = len(ocs_ws_map.get(aid_r, []))
            gmd_r = sc_r.get('gmd', 0.0) if sc_r.get('gmd', 0.0) > 0 else None
            cards_html += card_animal(ident_r, status_r, gmd_r, sc_r['score'], n_oc)

        if cards_html:
            st.markdown(cards_html, unsafe_allow_html=True)
        else:
            st.info("Nenhum animal encontrado com este filtro.")

    # ── ABA PESAGENS ──────────────────────────────────────────────────────────
    with aba_pes:
        plote_ws = listar_pesagens_lote(lote_ws_id)
        if plote_ws:
            df_p_ws = pd.DataFrame(plote_ws,
                columns=["ID","LoteID","Peso","Data","Animal","AnimalID"])
            df_p_ws["Data"] = pd.to_datetime(df_p_ws["Data"])
            df_p_ws = df_p_ws.sort_values("Data")

            # Grafico de evolucao media
            df_media = df_p_ws.groupby("Data")["Peso"].mean().reset_index()
            st.subheader("Evolucao do peso medio do lote")
            st.line_chart(df_media.set_index("Data")["Peso"])

            st.subheader("Todas as pesagens")
            st.dataframe(
                df_p_ws[["Animal","Peso","Data"]].rename(columns={"Peso":"Peso (kg)"}),
                use_container_width=True
            )
            st.caption(f"Total: {len(plote_ws)} pesagens | {df_p_ws['Animal'].nunique()} animais")
        else:
            st.info("Nenhuma pesagem registrada neste lote.")
            if st.button("Ir para Registrar Pesagem", type="primary"):
                st.session_state.menu = "Registrar Pesagem"
                st.rerun()

    # ── ABA SANIDADE ──────────────────────────────────────────────────────────
    with aba_san:
        c1_s, c2_s = st.columns(2)

        with c1_s:
            st.subheader("Ocorrencias")
            todas_ocs_raw = _ws['todas_ocs']
            todas_ocs = [{"Animal": r[9], "Data": r[2], "Tipo": r[3],
                          "Gravidade": r[5], "Custo": r[6], "Status": r[8]}
                         for r in todas_ocs_raw]
            if todas_ocs:
                df_oc_ws = pd.DataFrame(todas_ocs)
                # Contagem por tipo
                por_tipo = df_oc_ws.groupby("Tipo").size().reset_index(name="Qtd")
                st.bar_chart(por_tipo.set_index("Tipo")["Qtd"])
                em_trat = df_oc_ws[df_oc_ws["Status"]=="Em tratamento"]
                if len(em_trat) > 0:
                    st.warning(f"{len(em_trat)} ocorrencia(s) em tratamento")
                    st.dataframe(em_trat[["Animal","Data","Tipo","Gravidade"]], use_container_width=True)
            else:
                st.success("Nenhuma ocorrencia registrada.")

        with c2_s:
            st.subheader("Vacinas")
            vacs_ws = _ws['vacs']
            pendentes_ws = [v for v in vacs_ws if v[5]=='pendente']
            realizadas_ws = [v for v in vacs_ws if v[5]=='realizado']
            st.metric("Pendentes", len(pendentes_ws))
            st.metric("Realizadas", len(realizadas_ws))
            if pendentes_ws:
                st.warning("Vacinas pendentes:")
                for vp in pendentes_ws[:5]:
                    st.caption(f"{vp[2]} - Prevista: {vp[3]}")

            st.subheader("Medicamentos criticos")
            meds_ws = listar_medicamentos_criticos()
            if meds_ws:
                for m in meds_ws[:3]:
                    st.warning(f"{m[1]}: {m[3]} {m[2]} (min: {m[4]})")
            else:
                st.success("Estoque OK")

    # ── ABA FINANCEIRO ────────────────────────────────────────────────────────
    if aba_fin is not None:
     with aba_fin:
        col_f1, col_f2 = st.columns(2)

        with col_f1:
            st.subheader("Custo de aquisicao")
            preco_anim = obter_lote(lote_ws_id)
            custo_aq = 0
            if preco_anim:
                try:
                    with __import__('database')._conexao() as _conn:
                        _cur = _conn.cursor()
                        _cur.execute(
                            f"SELECT COALESCE(preco_por_animal,0) FROM lotes WHERE id={__import__('database')._ph()}",
                            (lote_ws_id,)
                        )
                        preco_u = float(_cur.fetchone()[0] or 0)
                    custo_aq = preco_u * rs_ws['total_animais']
                    st.metric("Custo total de compra", f"R$ {custo_aq:,.0f}")
                    st.metric("Preco por animal", f"R$ {preco_u:,.0f}")
                except Exception:
                    pass

            st.metric("Custo sanitario", f"R$ {rs_ws['custo_sanitario']:,.0f}")
            custo_total = custo_aq + rs_ws['custo_sanitario']
            st.metric("Custo total estimado", f"R$ {custo_total:,.0f}")

        with col_f2:
            st.subheader("Venda e margem")
            vendas_ws = _ws['vendas']
            if vendas_ws:
                v = vendas_ws[0]
                receita = v[3] * v[4]
                margem = receita - custo_aq - rs_ws['custo_sanitario']
                st.metric("Receita", f"R$ {receita:,.0f}")
                st.metric("Margem", f"R$ {margem:,.0f}",
                          delta=f"{(margem/custo_aq*100 if custo_aq else 0):.1f}%")
                st.caption(f"Venda em {v[2]} | {v[3]} kg | {v[5]}")
            else:
                st.info("Nenhuma venda registrada.")
                custo_diar = st.number_input("Custo diario/animal (R$)", 0.0, value=8.0, key="ws_cd")
                dias_ws2 = (date.today() - pd.to_datetime(lote_ws[3] if lote_ws else date.today()).date()).days
                custo_op = custo_diar * rs_ws['ativos'] * max(dias_ws2, 1)
                st.metric("Custo operacional estimado", f"R$ {custo_op:,.0f}",
                          help=f"Baseado em {dias_ws2} dias no lote")

    # ── ABA RELATORIOS ────────────────────────────────────────────────────────
    with aba_rel:
        st.subheader("Exportar dados deste lote")
        col_r1, col_r2 = st.columns(2)

        with col_r1:
            if st.button("Gerar Excel do lote", use_container_width=True, type="primary"):
                try:
                    pesagens_dict = {a[0]: listar_pesagens(a[0]) for a in animais_ws}
                    ocorr_dict    = {a[0]: listar_ocorrencias(a[0]) for a in animais_ws}
                    xls = gerar_excel_lote(lote_ws_nome, animais_ws, pesagens_dict, ocorr_dict)
                    st.download_button(
                        "Baixar Excel", xls,
                        file_name=f"lote_{lote_ws_nome.replace(' ','_')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                except Exception as e:
                    st.error(f"Erro: {e}")

        with col_r2:
            if st.button("Gerar PDF do lote", use_container_width=True):
                try:
                    secoes = [
                        dict(titulo="Animais", df=pd.DataFrame(
                            animais_ws, columns=["ID","Identificacao","Idade","LoteID"]
                        )),
                    ]
                    plote2 = listar_pesagens_lote(lote_ws_id)
                    if plote2:
                        secoes.append(dict(titulo="Pesagens", df=pd.DataFrame(
                            plote2, columns=["ID","LoteID","Peso","Data","Animal","AnimalID"]
                        )[["Animal","Peso","Data"]]))
                    pdf = gerar_pdf_relatorio(f"Relatorio - {lote_ws_nome}", secoes)
                    st.download_button(
                        "Baixar PDF", pdf,
                        file_name=f"relatorio_{lote_ws_nome.replace(' ','_')}.pdf",
                        mime="application/pdf"
                    )
                except Exception as e:
                    st.error(f"Erro: {e}")

        st.divider()
        st.subheader("Prontuario rapido por animal")
        if animais_ws:
            dict_anim_r = {a[1]: a[0] for a in animais_ws}
            anim_r = st.selectbox("Animal", list(dict_anim_r.keys()), key="ws_pront")
            aid_r2 = dict_anim_r[anim_r]
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                ps_r2 = listar_pesagens(aid_r2)
                st.metric("Pesagens", len(ps_r2))
                if ps_r2:
                    ultimo = ps_r2[-1]
                    st.metric("Ultimo peso", f"{ultimo[2]:.1f} kg", help=str(ultimo[3]))
            with col_p2:
                ocs_r2 = listar_ocorrencias(aid_r2)
                sc_r2 = calcular_score_saude(aid_r2)
                st.metric("Score saude", f"{sc_r2['score']}/100")
                st.metric("Ocorrencias", len(ocs_r2))

    # ============================================================
    # GESTAO DE USUARIOS - PLANOS E ACESSOS VETERINARIO
    # ============================================================


def page_prontuario_animal(u):
    parto = listar_partos_previstos(owner_id=owner_id())
    hdr("Prontuario Animal", "Prontuario Completo", "Historico de peso, saude e reproducao")

    @st.cache_data(ttl=900, show_spinner="Carregando prontuario...")
    def _dados_prontuario(animal_id):
        return dict(
            pesagens    = listar_pesagens(animal_id),
            ocorrencias = listar_ocorrencias(animal_id),
            reproducao  = listar_reproducao(animal_id),
            score       = calcular_score_saude(animal_id),
            carencia    = verificar_carencia(animal_id),
            previsao    = calcular_previsao_abate(animal_id),
        )

    # ── funcao de timeline ────────────────────────────────────────────────
    def montar_timeline(animal_id, det):
        _pd2 = pd
        eventos = []

        # Pesagens
        ps = listar_pesagens(animal_id)
        if ps:
            df_p = _pd2.DataFrame(ps, columns=["id","aid","peso","data"])
            df_p["data"] = _pd2.to_datetime(df_p["data"])
            df_p = df_p.sort_values("data")
            for _, row in df_p.iterrows():
                eventos.append({
                    "data": row["data"],
                    "tipo": "pesagem",
                    "icone": "scale",
                    "titulo": f"Pesagem: {row['peso']:.1f} kg",
                    "detalhe": "",
                    "cor": "azul",
                })
            # GMD entre pesagens consecutivas
            for i in range(1, len(df_p)):
                dias = (df_p["data"].iloc[i] - df_p["data"].iloc[i-1]).days
                if dias > 0:
                    gmd = (df_p["peso"].iloc[i] - df_p["peso"].iloc[i-1]) / dias
                    if gmd < 0:
                        eventos.append({
                            "data": df_p["data"].iloc[i],
                            "tipo": "alerta_gmd",
                            "icone": "warning",
                            "titulo": f"Queda de GMD: {gmd:.3f} kg/dia",
                            "detalhe": "Perda de peso detectada",
                            "cor": "vermelho",
                        })
                    elif gmd < 0.5:
                        eventos.append({
                            "data": df_p["data"].iloc[i],
                            "tipo": "alerta_gmd",
                            "icone": "warning",
                            "titulo": f"GMD baixo: {gmd:.3f} kg/dia",
                            "detalhe": "Desempenho abaixo do esperado",
                            "cor": "amarelo",
                        })

        # Ocorrencias
        ocs = listar_ocorrencias(animal_id)
        for o in ocs:
            cor_oc = "vermelho" if o[5]=="Alta" else "amarelo" if o[5]=="Media" else "azul_claro"
            eventos.append({
                "data": _pd2.to_datetime(o[2]),
                "tipo": "ocorrencia",
                "icone": "medical",
                "titulo": f"{o[3]}: {o[4][:40]}..." if len(o[4])>40 else f"{o[3]}: {o[4]}",
                "detalhe": f"Gravidade: {o[5]} | Custo: R$ {o[6]:.2f} | Status: {o[8]}",
                "cor": cor_oc,
            })

        # Vacinas realizadas
        try:
            lote_id_anim = det[3] if det else None
            if lote_id_anim:
                vacs = listar_vacinas_agenda(lote_id_anim)
                for v in vacs:
                    if v[5] == "realizado" and v[4]:
                        eventos.append({
                            "data": _pd2.to_datetime(v[4]),
                            "tipo": "vacina",
                            "icone": "syringe",
                            "titulo": f"Vacina: {v[2]}",
                            "detalhe": "Realizada",
                            "cor": "verde",
                        })
        except Exception:
            pass

        # Reproducao
        repros = listar_reproducao(animal_id)
        for r in repros:
            if r[2]:
                eventos.append({
                    "data": _pd2.to_datetime(r[2]),
                    "tipo": "reproducao",
                    "icone": "heart",
                    "titulo": f"Cobertura {r[3]}",
                    "detalhe": f"Resultado: {r[5]}",
                    "cor": "roxo",
                })
            if r[7]:
                eventos.append({
                    "data": _pd2.to_datetime(r[7]),
                    "tipo": "parto",
                    "icone": "baby",
                    "titulo": "Parto realizado",
                    "detalhe": f"Tipo: {r[3]}",
                    "cor": "verde",
                })

        # Ordenar por data
        eventos.sort(key=lambda x: x["data"])
        return eventos

    def render_timeline(eventos):
        if not eventos:
            st.info("Nenhum evento registrado para este animal.")
            return

        COR_MAP = {
            "azul":       ("#1565C0", "#E3F2FD", "Pesagem"),
            "verde":       ("#1B5E20", "#E8F5E9", "Vacina / Parto"),
            "vermelho":    ("#B71C1C", "#FFEBEE", "Alerta / Ocorrencia grave"),
            "amarelo":     ("#E65100", "#FFF3E0", "Alerta moderado"),
            "azul_claro":  ("#0277BD", "#E1F5FE", "Ocorrencia leve"),
            "roxo":        ("#4A148C", "#F3E5F5", "Reproducao"),
        }

        ICONE_MAP = {
            "scale":   "peso",
            "warning": "alerta",
            "medical": "ocorrencia",
            "syringe": "vacina",
            "heart":   "cobertura",
            "baby":    "parto",
        }

        html_parts = [
            "<style>",
            ".tl-wrap{padding:8px 0}",
            ".tl-item{display:flex;gap:12px;margin-bottom:4px;align-items:flex-start}",
            ".tl-line-col{display:flex;flex-direction:column;align-items:center;width:32px;flex-shrink:0}",
            ".tl-dot{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;flex-shrink:0}",
            ".tl-vline{width:2px;flex:1;min-height:16px;background:#E0E0E0;margin:2px 0}",
            ".tl-content{flex:1;border-radius:8px;padding:8px 12px;border-left:3px solid}",
            ".tl-date{font-size:11px;color:#888;margin-bottom:2px}",
            ".tl-title{font-size:13px;font-weight:600;margin:0}",
            ".tl-detail{font-size:11px;color:#666;margin-top:2px}",
            "</style>",
            "<div class='tl-wrap'>",
        ]

        for i, ev in enumerate(eventos):
            cor_key = ev["cor"]
            cor_borda, cor_fundo, _ = COR_MAP.get(cor_key, ("#555","#F5F5F5",""))
            data_str = ev["data"].strftime("%d/%m/%Y")
            icone_str = ICONE_MAP.get(ev["icone"], ev["icone"])[:2].upper()
            is_last = (i == len(eventos)-1)

            html_parts.append("<div class='tl-item'>")
            html_parts.append("<div class='tl-line-col'>")
            html_parts.append(f"<div class='tl-dot' style='background:{cor_fundo};color:{cor_borda};border:2px solid {cor_borda}'>{icone_str}</div>")
            if not is_last:
                html_parts.append("<div class='tl-vline'></div>")
            html_parts.append("</div>")
            html_parts.append(f"<div class='tl-content' style='background:{cor_fundo};border-color:{cor_borda}'>")
            html_parts.append(f"<div class='tl-date'>{data_str}</div>")
            html_parts.append(f"<div class='tl-title'>{ev['titulo']}</div>")
            if ev["detalhe"]:
                html_parts.append(f"<div class='tl-detail'>{ev['detalhe']}</div>")
            html_parts.append("</div>")
            html_parts.append("</div>")

        html_parts.append("</div>")
        st.markdown("".join(html_parts), unsafe_allow_html=True)

    # ── selecao ───────────────────────────────────────────────────────────
    lotes = listar_lotes_usuario()
    if not lotes: st.warning("Nenhum lote.")
    else:
        dict_l = {f"{l[1]} (ID {l[0]})": l[0] for l in lotes}
        pr1,pr2 = st.columns(2)
        with pr1: lote_s = st.selectbox("Lote", list(dict_l.keys()), key="pron_lote")
        animais = listar_animais_por_lote(dict_l[lote_s])
        if not animais: st.warning("Nenhum animal.")
        else:
            dict_a = {f"{a[1]} (ID {a[0]})": a[0] for a in animais}
            with pr2: anim_s = st.selectbox("Animal", list(dict_a.keys()), key="pron_anim")
            animal_id = dict_a[anim_s]
            det = obter_animal(animal_id)

            # Score e status rapido
            sc = calcular_score_saude(animal_id)
            car = verificar_carencia(animal_id)
            km1,km2,km3,km4 = st.columns(4)
            km1.metric("Score Saude", f"{sc['score']}/100")
            km2.metric("Classificacao", sc["classificacao"])
            km3.metric("Ocorrencias", sc["detalhes"]["n_ocorrencias"])
            km4.metric("Carencia", "Sim" if car["em_carencia"] else "Nao",
                       delta="Verificar abate" if car["em_carencia"] else None,
                       delta_color="inverse" if car["em_carencia"] else "normal")

            st.divider()

            # Carregar todos os dados de uma vez (cacheado)
            _dados_p = _dados_prontuario(animal_id)

            t1,t2,t3,t4 = st.tabs(["Timeline","Dados","Pesagens","Ocorrencias"])

            with t1:
                st.subheader(f"Timeline clinica de {anim_s.split(' (ID')[0]}")
                st.caption("Todos os eventos do animal em ordem cronologica")

                # Legenda
                leg = st.columns(6)
                leg[0].markdown("<span style='color:#1565C0'>&#9679;</span> Pesagem", unsafe_allow_html=True)
                leg[1].markdown("<span style='color:#1B5E20'>&#9679;</span> Vacina/Parto", unsafe_allow_html=True)
                leg[2].markdown("<span style='color:#B71C1C'>&#9679;</span> Ocorr. grave", unsafe_allow_html=True)
                leg[3].markdown("<span style='color:#E65100'>&#9679;</span> Alerta", unsafe_allow_html=True)
                leg[4].markdown("<span style='color:#0277BD'>&#9679;</span> Ocorr. leve", unsafe_allow_html=True)
                leg[5].markdown("<span style='color:#4A148C'>&#9679;</span> Reproducao", unsafe_allow_html=True)

                st.divider()
                eventos = montar_timeline(animal_id, det)
                render_timeline(eventos)

                if eventos:
                    st.caption(f"Total: {len(eventos)} eventos registrados")

            with t2:
                with st.form("form_pron"):
                    d1,d2 = st.columns(2)
                    with d1:
                        peso_alvo = st.number_input("Peso alvo abate (kg)", 0.0, 1000.0, float(det[7]) if det else 0.0)
                        raca_p    = st.text_input("Raca", value=det[5] if det else "")
                    with d2:
                        obs_p = st.text_area("Observacoes clinicas", value=det[8] if det else "", height=100)
                    if st.form_submit_button("Salvar", type="primary"):
                        atualizar_animal_detalhes(animal_id, peso_alvo=peso_alvo, observacoes=obs_p)
                        st.success("Prontuario atualizado!"); st.rerun()
                if det and det[7] > 0:
                    prev = calcular_previsao_abate(animal_id)
                    if "erro" not in prev:
                        st.divider()
                        st.subheader("Previsao de Abate")
                        pv1,pv2,pv3 = st.columns(3)
                        pv1.metric("GMD", f"{prev['gmd']:.3f} kg/dia")
                        pv2.metric("Dias restantes", prev["dias_restantes"])
                        pv3.metric("Data prevista", prev["data_prevista"])

            with t3:
                ps = listar_pesagens(animal_id)
                if ps:
                    df_p = pd.DataFrame(ps, columns=["ID","Animal","Peso","Data"])
                    df_p["Data"] = pd.to_datetime(df_p["Data"])
                    df_p = df_p.sort_values("Data")
                    st.line_chart(df_p.set_index("Data")["Peso"])
                    st.dataframe(df_p[["Data","Peso"]].rename(columns={"Peso":"Peso (kg)"}), use_container_width=True)
                else: st.info("Sem pesagens.")

            with t4:
                ocs = listar_ocorrencias(animal_id)
                if ocs:
                    df_oc = pd.DataFrame(ocs, columns=["ID","Animal","Data","Tipo","Desc","Grav","Custo","Dias","Status"])
                    df_oc["Data"] = pd.to_datetime(df_oc["Data"])
                    st.dataframe(df_oc[["Data","Tipo","Grav","Desc","Custo","Status"]], use_container_width=True)
                    st.metric("Custo total tratamentos", f"R$ {sum(o[6] for o in ocs if o[6]):.2f}")
                else: st.success("Nenhuma ocorrencia registrada.")
                repros = listar_reproducao(animal_id)
                if repros:
                    st.subheader("Historico Reprodutivo")
                    df_r = pd.DataFrame(repros, columns=["ID","Animal","Cio","Tipo","Diag","Result","Parto Prev","Parto Real","Obs"])
                    st.dataframe(df_r[["Cio","Tipo","Result","Parto Prev","Parto Real"]], use_container_width=True)

    # ============================================================
    # MARGEM REAL
    # ============================================================
