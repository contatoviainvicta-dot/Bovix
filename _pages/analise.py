# pages/analise.py -- Telas: Dashboard Sanitario, Analisar por Lote, Analisar Animal, Score de Saude, GMD Temporal, Comparativo Lotes, Pesquisar Ocorrencias, Risco Sanitario IA, Previsao de Abate IA, Anomalias de Peso, Previsao Abate

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

def page_dashboard_sanitario(u):
    hdr("Dashboard Sanitario", "Saude do Rebanho", "Incidencias, curva epidemica e alertas")
    lotes = listar_lotes_usuario()
    opcoes = ["Todos os lotes"] + [f"{l[1]} (ID {l[0]})" for l in lotes]
    dict_l = {f"{l[1]} (ID {l[0]})": l[0] for l in lotes}
    escolha = st.selectbox("Filtrar por lote", opcoes)
    if escolha == "Todos os lotes":
        animais = [a for l in listar_lotes_usuario() for a in listar_animais_por_lote(l[0])]
    else:
        animais = listar_animais_por_lote(dict_l[escolha])

    # Query agregada em vez de N+1
    if escolha == "Todos os lotes":
        import database as _dbl
        todas_oc = []
        for l in listar_lotes_usuario():
            todas_oc.extend(listar_ocorrencias_todos_animais(l[0]))
    else:
        lote_id_san = dict_l.get(escolha)
        todas_oc = list(listar_ocorrencias_todos_animais(lote_id_san)) if lote_id_san else []
        # Ajustar indices para compatibilidade (sem coluna extra "identificacao")
        todas_oc = [r[:10] for r in todas_oc]

    df_oc = pd.DataFrame(todas_oc, columns=["id","animal_id","data","tipo","descricao","gravidade","custo","dias_rec","status","identificacao"]) if todas_oc else pd.DataFrame(columns=["id","animal_id","data","tipo","descricao","gravidade","custo","dias_rec","status"])

    total_a  = len(animais)
    c_oc     = df_oc["animal_id"].nunique() if len(df_oc)>0 else 0
    inc      = (c_oc/total_a*100) if total_a>0 else 0
    custo_oc = df_oc["custo"].fillna(0).sum() if len(df_oc)>0 else 0

    k1,k2,k3,k4 = st.columns(4)
    k1.metric("Animais", total_a)
    k2.metric("Com ocorrencia", c_oc)
    k3.metric("Incidencia", f"{inc:.1f}%", delta="Alta" if inc>20 else None, delta_color="inverse" if inc>20 else "normal")
    k4.metric("Custo sanitario", f"R$ {custo_oc:.2f}")

    st.divider()

    if len(df_oc) > 0:
        t1,t2,t3,t4 = st.tabs(["Graficos","Por Lote","Curva Epidemica","Alertas"])
        with t1:
            c1,c2 = st.columns(2)
            with c1:
                st.subheader("Por tipo")
                st.bar_chart(df_oc["tipo"].value_counts())
            with c2:
                st.subheader("Por gravidade")
                st.bar_chart(df_oc["gravidade"].value_counts())
        with t2:
            dados_l = []
            for lote in lotes:
                anim_l = listar_animais_por_lote(lote[0])
                tot_l  = len(anim_l)
                ids_l  = [a[0] for a in anim_l]
                oc_l   = df_oc[df_oc["animal_id"].isin(ids_l)] if len(df_oc)>0 else pd.DataFrame()
                doentes_l = oc_l["animal_id"].nunique() if len(oc_l)>0 else 0
                inc_l  = (doentes_l/tot_l*100) if tot_l>0 else 0
                dados_l.append((lote[1], inc_l))
            df_l = pd.DataFrame(dados_l, columns=["Lote","Incidencia (%)"]).set_index("Lote")
            st.bar_chart(df_l)
        with t3:
            df_oc2 = df_oc.copy()
            df_oc2["data"] = pd.to_datetime(df_oc2["data"])
            curva = df_oc2.groupby(["data","tipo"]).size().unstack(fill_value=0)
            st.line_chart(curva)
        with t4:
            for nome_l, inc_l in dados_l:
                if inc_l > 20:  st.error(f"{nome_l}: alta incidencia ({inc_l:.1f}%)")
                elif inc_l > 5: st.warning(f"{nome_l}: incidencia moderada ({inc_l:.1f}%)")
                else:           st.success(f"{nome_l}: controle adequado ({inc_l:.1f}%)")
    else:
        st.info("Nenhuma ocorrencia registrada ainda.")

    # ============================================================
    # ANALISAR POR LOTE
    # ============================================================


def page_analisar_por_lote(u):
    lotes = listar_lotes_usuario()
    pend  = listar_vacinas_pendentes(owner_id=owner_id())
    hdr("Analisar por Lote", "Analise do Lote", "Desempenho economico e zootecnico")
    lote_id, lotes = sel_lote("analise_lote")
    if lote_id:
        lote   = obter_lote(lote_id)
        animais = listar_animais_por_lote(lote_id)
        rs = resumo_lote(lote_id)
        k1,k2,k3,k4,k5 = st.columns(5)
        k1.metric("Ativos",    rs["ativos"])
        k2.metric("Mortes",    rs["mortos"])
        k3.metric("GTAs",      rs["gtas_emitidas"])
        k4.metric("Ocorrencias", rs["ocorrencias"])
        k5.metric("Vac. pend.",  rs["vacinas_pendentes"])
        st.divider()

        custo_diar = st.number_input("Custo diario por animal (R$)", 0.0, 100.0, 10.0)
        preco_kg   = st.number_input("Preco do kg (R$)", 0.0, 50.0, 10.0)

        # Queries agregadas - sem N+1
        pes_lote = listar_pesagens_todos_animais(lote_id)
        ocs_lote = listar_ocorrencias_todos_animais(lote_id)

        datas = [p[3] for p in pes_lote]
        dias_lote = 0
        if len(datas) > 1:
            dts = pd.to_datetime(datas)
            dias_lote = (max(dts)-min(dts)).days

        custo_op = custo_diar * len(animais) * dias_lote
        ganho_t  = 0
        custo_san = sum(r[6] for r in ocs_lote if r[6])
        gmds = list(calcular_gmds_lote(lote_id).values())
        gmds = [g for g in gmds if 0 <= g <= 2]

        # Calcular ganho total
        pes_por_animal = {}
        for p in pes_lote:
            pes_por_animal.setdefault(p[1], []).append(p)
        for aid, ps in pes_por_animal.items():
            if len(ps) >= 2:
                ps_sorted = sorted(ps, key=lambda x: x[3])
                g = ps_sorted[-1][2] - ps_sorted[0][2]
                if g > 0: ganho_t += g

        receita = ganho_t * preco_kg
        lucro   = receita - custo_op - custo_san
        gmd_m   = sum(gmds)/len(gmds) if gmds else 0

        st.subheader("Resultado Economico")
        re1,re2,re3,re4 = st.columns(4)
        re1.metric("Receita estimada", f"R$ {receita:,.2f}")
        re2.metric("Custo operacional", f"R$ {custo_op:,.2f}")
        re3.metric("Custo sanitario",  f"R$ {custo_san:,.2f}")
        re4.metric("Lucro / Prejuizo", f"R$ {lucro:,.2f}", delta="Lucro" if lucro>=0 else "Prejuizo", delta_color="normal" if lucro>=0 else "inverse")

        st.metric("GMD medio do lote", f"{gmd_m:.3f} kg/dia")
        if gmd_m < 0.5: st.warning("Baixo desempenho")
        elif gmd_m > 0: st.success("Bom desempenho")

        lucro_anim = lucro/len(animais) if animais else 0
        st.metric("Lucro por animal", f"R$ {lucro_anim:,.2f}")

        # Ranking GMD
        # Usar gmds calculados em batch
        gmds_rank = calcular_gmds_lote(lote_id)
        ranking = []
        for a in animais:
            gmd = gmds_rank.get(a[0])
            if gmd is not None:
                    if 0 <= gmd <= 2: ranking.append((a[1], gmd))
        if ranking:
            ranking.sort(key=lambda x: x[1], reverse=True)
            st.subheader("Ranking GMD")
            for i,(nm,gmd) in enumerate(ranking,1):
                st.write(f"{i}. {nm} -> {gmd:.3f} kg/dia")

    # ============================================================
    # ANALISAR ANIMAL
    # ============================================================


def page_analisar_animal(u):
    hdr("Analisar Animal", "Analise Individual", "Historico de peso, ocorrencias e alertas")
    lotes = listar_lotes_usuario()
    if not lotes:
        st.warning("Nenhum lote cadastrado")
    else:
        dict_l = {f"{l[1]} (ID {l[0]})": l[0] for l in lotes}
        aa1,aa2 = st.columns(2)
        with aa1: lote_s = st.selectbox("Lote", list(dict_l.keys()), key="aa_lote")
        lote_id = dict_l[lote_s]
        animais = listar_animais_por_lote(lote_id)
        if not animais:
            st.warning("Nenhum animal neste lote.")
        else:
            dict_a = {f"{a[1]} (ID {a[0]})": a[0] for a in animais}
            with aa2: anim_s = st.selectbox("Animal", list(dict_a.keys()), key="aa_anim")
            animal_id = dict_a[anim_s]
            pesagens   = listar_pesagens(animal_id)
            ocorrencias = listar_ocorrencias(animal_id)
            sc = calcular_score_saude(animal_id)
            gmd = None

            km1,km2,km3,km4 = st.columns(4)
            km1.metric("Pesagens",    len(pesagens))
            km2.metric("Ocorrencias", len(ocorrencias))
            km3.metric("Score saude", f"{sc['score']}/100")
            km4.metric("Classificacao", sc["classificacao"])

            t1,t2,t3 = st.tabs(["Pesagens & GMD","Ocorrencias","Alertas"])

            with t1:
                if pesagens:
                    df = pd.DataFrame(pesagens, columns=["ID","Animal","Peso","Data"])
                    df["Data"] = pd.to_datetime(df["Data"])
                    df = df.sort_values("Data")
                    st.line_chart(df.set_index("Data")["Peso"])
                    st.dataframe(df[["Data","Peso"]].rename(columns={"Peso":"Peso (kg)"}), width='stretch')
                    if len(df) > 1:
                        dias = (df["Data"].iloc[-1]-df["Data"].iloc[0]).days
                        if dias > 0:
                            gmd = (df["Peso"].iloc[-1]-df["Peso"].iloc[0])/dias
                            d1,d2,d3 = st.columns(3)
                            d1.metric("Ganho total", f"{df['Peso'].iloc[-1]-df['Peso'].iloc[0]:.2f} kg")
                            d2.metric("Periodo",     f"{dias} dias")
                            d3.metric("GMD",         f"{gmd:.3f} kg/dia")
                            if gmd < 0:    st.error("Perda de peso - possivel doenca")
                            elif gmd > 2:  st.error("GMD irreal - revisar dados")
                            elif gmd < 0.5: st.warning("GMD baixo")
                            else:          st.success("Bom desempenho")
                else:
                    st.info("Sem pesagens registradas.")

            with t2:
                if ocorrencias:
                    df_oc = pd.DataFrame(ocorrencias, columns=["id","animal_id","data","tipo","descricao","gravidade","custo","dias_rec","status"])
                    df_oc["data"] = pd.to_datetime(df_oc["data"])
                    st.dataframe(df_oc[["data","tipo","gravidade","descricao","custo","status"]], width='stretch')
                    custo_tot = df_oc["custo"].fillna(0).sum()
                    st.metric("Custo total tratamentos", f"R$ {custo_tot:.2f}")
                else:
                    st.success("Nenhuma ocorrencia registrada.")

            with t3:
                det = sc["detalhes"]
                s1,s2,s3 = st.columns(3)
                s1.metric("GMD (pts)",        f"{det['pts_gmd']}/50")
                s2.metric("Ocorrencias (pts)",f"{det['pts_ocorrencias']}/35")
                s3.metric("Reproducao (pts)", f"{det['pts_reproducao']}/15")
                if gmd is not None:
                    if gmd < 0.5 and ocorrencias: st.error("Alto risco: baixo GMD + ocorrencias")
                    elif gmd < 0.5:               st.warning("Baixo GMD")
                    elif ocorrencias:             st.warning("Historico clinico - monitorar")
                    else:                         st.success("Animal saudavel e produtivo")
                car = verificar_carencia(animal_id)
                if car["em_carencia"]:
                    st.error(f"Em carencia ate {car['liberado_em']} - nao abater!")
                else:
                    st.success("Sem restricao de carencia")

    # ============================================================
    # SCORE DE SAUDE
    # ============================================================


def page_score_de_saude(u):
    hdr("Score de Saude", "Ranking de Saude", "Nota 0-100 por animal (GMD + ocorrencias + reproducao)")
    lote_id, _ = sel_lote("score_lote")
    if lote_id:
        animais = listar_animais_por_lote(lote_id)
        if not animais:
            st.warning("Nenhum animal.")
        else:
            # Calcular todos os scores em batch (sem N+1 queries)
            scores_batch = calcular_scores_lote(lote_id)
            scores = []
            for a in animais:
                sc  = scores_batch.get(a[0], dict(score=65, classificacao="Regular", gmd=0.0, n_ocorrencias=0))
                car = verificar_carencia(a[0])
                scores.append({"Animal": a[1], "Score": sc["score"], "Classificacao": sc["classificacao"],
                               "GMD": sc["gmd"], "Ocorrencias": sc["n_ocorrencias"],
                               "Em Carencia": "Sim" if car["em_carencia"] else "Nao"})
            df_sc = pd.DataFrame(scores).sort_values("Score", ascending=False)
            st.dataframe(df_sc, width='stretch')
            c1,c2,c3 = st.columns(3)
            c1.metric("Score medio",   f"{df_sc['Score'].mean():.1f}")
            c2.metric("Melhor animal", df_sc.iloc[0]["Animal"])
            c3.metric("Criticos (<40)", len(df_sc[df_sc["Score"]<40]))
            st.bar_chart(df_sc.set_index("Animal")["Score"])
            st.subheader("Alertas")
            for _, row in df_sc.iterrows():
                if row["Score"] < 40:   st.error(f"{row['Animal']}: Score {row['Score']} - CRITICO")
                elif row["Score"] < 60: st.warning(f"{row['Animal']}: Score {row['Score']} - Regular")
                if row["Em Carencia"] == "Sim": st.warning(f"{row['Animal']}: em carencia de medicamento")

    # ============================================================
    # GMD TEMPORAL
    # ============================================================


def page_gmd_temporal(u):
    hdr("GMD Temporal", "Evolucao do GMD", "Evolucao do ganho de peso ao longo do tempo")
    lote_id, _ = sel_lote("gmd_lote")
    if lote_id:
        janela = st.slider("Janela de calculo (dias)", 7, 60, 14)
        pontos = calcular_gmd_temporal(lote_id, janela)
        if pontos:
            df_g = pd.DataFrame(pontos, columns=["Data","GMD medio (kg/dia)"]).set_index("Data")
            st.line_chart(df_g)
            st.dataframe(df_g, width='stretch')
            ult = pontos[-1][1]; pri = pontos[0][1]
            st.metric("GMD atual", f"{ult:.3f} kg/dia", delta=f"{ult-pri:+.3f} vs inicio")
            if ult-pri < -0.1:   st.error("GMD em queda - revisar nutricao")
            elif ult-pri > 0.1:  st.success("GMD em melhora")
            else:                st.info("GMD estavel")
        else:
            st.info("Dados insuficientes. Registre pesagens em datas diferentes.")

    # ============================================================
    # COMPARATIVO LOTES
    # ============================================================


def page_comparativo_lotes(u):
    hdr("Comparativo Lotes", "Comparativo entre Lotes", "Side-by-side de GMD, custos e resultados")
    lotes = listar_lotes_usuario()
    if len(lotes) < 2:
        st.warning("Cadastre pelo menos 2 lotes.")
    else:
        dict_l = {f"{l[1]} (ID {l[0]})": l[0] for l in lotes}
        sels = st.multiselect("Selecione 2 a 4 lotes", list(dict_l.keys()), default=list(dict_l.keys())[:min(2,len(dict_l))])
        if len(sels) < 2:
            st.info("Selecione pelo menos 2 lotes.")
        else:
            pk  = st.number_input("Preco kg (R$)", 0.0, 100.0, 20.0)
            cd  = st.number_input("Custo diario/animal (R$)", 0.0, 100.0, 10.0)
            dados = []
            for nm in sels:
                lid   = dict_l[nm]
                anim  = listar_animais_por_lote(lid)
                tm    = taxa_mortalidade_lote(lid)
                tp    = taxa_prenhez_lote(lid)
                # Queries agregadas
                gmds_comp = list(calcular_gmds_lote(lid).values())
                gmds = [g for g in gmds_comp if 0 < g <= 2]
                ocs_comp = listar_ocorrencias_todos_animais(lid)
                custo_s = sum(r[6] for r in ocs_comp if r[6])
                pes_comp = listar_pesagens_todos_animais(lid)
                ganho, dias_t = 0, 0
                pes_por_a = {}
                for p in pes_comp:
                    pes_por_a.setdefault(p[1],[]).append(p)
                for ps_a in pes_por_a.values():
                    if len(ps_a) >= 2:
                        ps_a_s = sorted(ps_a, key=lambda x: x[3])
                        g = ps_a_s[-1][2]-ps_a_s[0][2]
                        d = (pd.to_datetime(ps_a_s[-1][3])-pd.to_datetime(ps_a_s[0][3])).days
                        ganho += g; dias_t += d
                gmd_m  = sum(gmds)/len(gmds) if gmds else 0
                receita = ganho * pk
                custo_op = cd * len(anim) * (dias_t/max(len(anim),1))
                lucro   = receita - custo_op - custo_s
                dados.append({"Lote": nm.split(" (ID")[0], "Animais": len(anim),
                              "GMD medio": gmd_m, "Incid. %": round(len([a for a in anim if listar_ocorrencias(a[0])])/max(len(anim),1)*100,1),
                              "Mortalidade %": tm["taxa"], "Prenhez %": round(tp["taxa"],1),
                              "Lucro R$": round(lucro,2)})
            df_c = pd.DataFrame(dados).set_index("Lote")
            st.dataframe(df_c, width='stretch')
            c1,c2 = st.columns(2)
            with c1: st.subheader("GMD medio"); st.bar_chart(df_c["GMD medio"])
            with c2: st.subheader("Lucro R$");  st.bar_chart(df_c["Lucro R$"])

    # ============================================================
    # PAINEL DE DECISAO
    # ============================================================


def page_pesquisar_ocorrencias(u):
    hdr("Pesquisar Ocorrencias", "Busca de Ocorrencias", "Filtros por lote, tipo e gravidade")
    lotes = listar_lotes_usuario()
    dict_l = {f"{l[1]} (ID {l[0]})": l[0] for l in lotes}
    f1,f2,f3 = st.columns(3)
    with f1: escolha_l = st.selectbox("Lote", ["Todos"]+list(dict_l.keys()))
    with f2: tipo_f    = st.selectbox("Tipo", ["Todos","Doenca","Lesao","Medicamento","Outros"])
    with f3: grav_f    = st.selectbox("Gravidade", ["Todas","Baixa","Media","Alta"])
    if escolha_l == "Todos":
        todas_oc_raw = []
        for l in listar_lotes_usuario():
            todas_oc_raw.extend(listar_ocorrencias_todos_animais(l[0]))
    else:
        todas_oc_raw = listar_ocorrencias_todos_animais(dict_l[escolha_l])
    # Converter para formato compativel (sem coluna ident)
    todas_oc = [list(r[:9]) for r in todas_oc_raw]
    df_oc = pd.DataFrame(todas_oc, columns=["id","animal_id","data","tipo","descricao","gravidade","custo","dias_rec","status"]) if todas_oc else pd.DataFrame(columns=["id","animal_id","data","tipo","descricao","gravidade","custo","dias_rec","status"])
    if len(df_oc)>0:
        if tipo_f!="Todos":  df_oc = df_oc[df_oc["tipo"]==tipo_f]
        if grav_f!="Todas":  df_oc = df_oc[df_oc["gravidade"]==grav_f]
        df_oc["data"] = pd.to_datetime(df_oc["data"])
        df_oc = df_oc.sort_values("data", ascending=False)
    st.divider()
    if len(df_oc)>0:
        p1,p2,p3,p4 = st.columns(4)
        p1.metric("Ocorrencias",   len(df_oc))
        p2.metric("Animais afetados", df_oc["animal_id"].nunique())
        p3.metric("Custo total",   f"R$ {df_oc['custo'].fillna(0).sum():.2f}")
        p4.metric("Gravidade Alta", len(df_oc[df_oc["gravidade"]=="Alta"]))
        t1,t2 = st.tabs(["Registros","Graficos"])
        with t1: st.dataframe(df_oc[["data","tipo","gravidade","descricao","custo","status"]], width='stretch')
        with t2:
            c1,c2 = st.columns(2)
            with c1: st.bar_chart(df_oc["tipo"].value_counts())
            with c2: st.bar_chart(df_oc["gravidade"].value_counts())
    else:
        st.info("Nenhuma ocorrencia com esses filtros.")

    # ============================================================
    # CALENDARIO SANITARIO
    # ============================================================


def page_risco_sanitario_ia(u):
    hdr("Risco Sanitario IA", "Score de Risco", "Analise inteligente de risco sanitario do lote")

    lote_id, _ = sel_lote("risco_lote")
    if lote_id:
        with st.spinner("Calculando risco sanitario..."):
            risco = calcular_risco_sanitario(lote_id)

        # Score visual
        score = risco['score']
        nivel = risco['nivel']
        cores = {'Saudavel':'#1B5E20','Baixo':'#2E7D4F','Medio':'#E65100','Alto':'#B71C1C','Critico':'#7B0000'}
        cor = cores.get(nivel, '#546E7A')

        c1, c2, c3 = st.columns([1,1,2])
        with c1:
            st.markdown(
                f"<div style='background:{cor};color:white;border-radius:12px;"
                f"padding:20px;text-align:center'>"
                f"<div style='font-size:48px;font-weight:700'>{score}</div>"
                f"<div style='font-size:16px'>Score de Risco</div>"
                f"<div style='font-size:20px;margin-top:4px'>{nivel}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        with c2:
            st.metric("Mortalidade", f"{risco['mortalidade']}%",
                     delta="critico" if risco['mortalidade'] >= 3 else None,
                     delta_color="inverse")
            st.metric("Ocorr. Graves", risco['ocorrencias_graves'],
                     delta="atencao" if risco['ocorrencias_graves'] > 0 else None,
                     delta_color="inverse")
        with c3:
            st.subheader("Fatores de risco")
            for fator in risco['fatores']:
                st.warning(f"⚠ {fator}")

            st.subheader("Recomendacoes")
            for rec in risco['recomendacoes']:
                st.info(f"→ {rec}")

        st.divider()

        # Evolucao do GMD
        if risco['gmds']:
            st.subheader("Distribuicao de GMD no lote")
            import pandas as pd
            df_gmd = pd.DataFrame({'GMD (kg/dia)': risco['gmds']})
            st.bar_chart(df_gmd)
            gmd_m = sum(risco['gmds'])/len(risco['gmds'])
            col_g1, col_g2, col_g3 = st.columns(3)
            col_g1.metric("GMD Medio", f"{gmd_m:.3f} kg/d")
            col_g2.metric("GMD Maximo", f"{max(risco['gmds']):.3f} kg/d")
            col_g3.metric("GMD Minimo", f"{min(risco['gmds']):.3f} kg/d")

        st.divider()
        st.subheader("Visao geral da fazenda")
        resumo_todos = resumo_ia_fazenda(owner_id=owner_id())
        if resumo_todos:
            df_r = pd.DataFrame(resumo_todos)
            df_r = df_r[['lote_nome','risco_nivel','risco_score','animais_ativos','principal_risco']]
            df_r.columns = ['Lote','Nivel','Score','Animais','Principal Risco']
            st.dataframe(df_r, width='stretch', hide_index=True)


    # ============================================================
    # PREVISAO DE ABATE IA
    # ============================================================


def page_previsao_de_abate_ia(u):
    hdr("Previsao de Abate IA", "Predicao de Abate", "Estimativa de data e resultado financeiro por animal")

    lote_id, _ = sel_lote("prev_lote")
    if lote_id:
        c1, c2, c3 = st.columns(3)
        with c1: peso_alvo = st.number_input("Peso alvo (kg)", 300.0, 600.0, 450.0, key="pa_kg")
        with c2: preco_kg  = st.number_input("Preco por kg (R$)", 1.0, 50.0, 10.0, key="pa_preco")
        with c3: custo_d   = st.number_input("Custo diario/animal (R$)", 1.0, 100.0, 12.0, key="pa_custo")

        with st.spinner("Calculando previsoes..."):
            previsoes = prever_abate(lote_id, peso_alvo, preco_kg, custo_d)

        if not previsoes:
            st.warning("Nenhum animal com dados suficientes.")
        else:
            # KPIs resumo
            com_prev = [p for p in previsoes if p['dias_restantes'] is not None]
            prontos  = [p for p in previsoes if p['status'] == 'Pronto para abate']
            proximos = [p for p in previsoes if p['status'] == 'Proximo do abate']

            card_kpi_row([
                dict(titulo="Total animais",    valor=len(previsoes)),
                dict(titulo="Prontos para abate", valor=len(prontos),
                     cor='#1B5E20' if prontos else '#546E7A'),
                dict(titulo="Proximos (30d)",   valor=len(proximos),
                     cor='#E65100' if proximos else '#546E7A'),
                dict(titulo="Receita estimada", valor=f"R$ {sum(p['receita_prevista'] or 0 for p in com_prev):,.0f}"),
                dict(titulo="Margem estimada",  valor=f"R$ {sum(p['margem_estimada'] or 0 for p in com_prev):,.0f}",
                     cor='#1B5E20'),
            ])

            st.write("")

            # Tabela de previsoes
            import pandas as pd
            df_prev = pd.DataFrame(previsoes)
            df_prev = df_prev[[
                'identificacao','peso_atual','gmd','dias_restantes',
                'data_prevista','receita_prevista','custo_estimado',
                'margem_estimada','status'
            ]]
            df_prev.columns = [
                'Animal','Peso Atual','GMD','Dias p/ Abate',
                'Data Prevista','Receita','Custo','Margem','Status'
            ]

            # Colorir por status
            def _cor_status(s):
                mapa = {
                    'Pronto para abate': 'background-color: #E8F5E9',
                    'Proximo do abate':  'background-color: #FFF3E0',
                    'Em engorda':        'background-color: #E3F2FD',
                    'GMD negativo':      'background-color: #FFEBEE',
                    'Sem dados suficientes': 'background-color: #ECEFF1',
                }
                return [mapa.get(v, '') for v in s]

            st.dataframe(
                df_prev.style.apply(_cor_status, subset=['Status']),
                width='stretch', hide_index=True
            )

            # Grafico de dias restantes
            st.subheader("Dias ate o abate por animal")
            df_bar = df_prev[df_prev['Dias p/ Abate'].notna()][['Animal','Dias p/ Abate']]
            if not df_bar.empty:
                st.bar_chart(df_bar.set_index('Animal'))


    # ============================================================
    # ANOMALIAS DE PESO
    # ============================================================


def page_anomalias_de_peso(u):
    hdr("Anomalias de Peso", "Alertas Inteligentes", "Deteccao automatica de comportamento anomalo de peso")

    lote_id, _ = sel_lote("anom_lote")
    if lote_id:
        with st.spinner("Analisando padroes de peso..."):
            anomalias = detectar_anomalias_peso(lote_id)

        if not anomalias:
            st.success("Nenhuma anomalia detectada. Padroes de peso normais.")
        else:
            altas  = [a for a in anomalias if a['gravidade'] == 'Alta']
            medias = [a for a in anomalias if a['gravidade'] == 'Media']

            card_kpi_row([
                dict(titulo="Total anomalias",  valor=len(anomalias)),
                dict(titulo="Gravidade Alta",   valor=len(altas),
                     cor='#B71C1C' if altas else '#546E7A'),
                dict(titulo="Gravidade Media",  valor=len(medias),
                     cor='#E65100' if medias else '#546E7A'),
            ])

            st.write("")
            st.subheader("Animais com comportamento anomalo")

            for a in sorted(anomalias, key=lambda x: x['gravidade']):
                cor = '#B71C1C' if a['gravidade'] == 'Alta' else '#E65100'
                cor_bg = '#FFEBEE' if a['gravidade'] == 'Alta' else '#FFF3E0'
                st.markdown(
                    f"<div style='background:{cor_bg};border-left:4px solid {cor};"
                    f"border-radius:6px;padding:12px;margin-bottom:8px'>"
                    f"<div style='display:flex;justify-content:space-between'>"
                    f"<div><strong>{a['identificacao']}</strong> - {a['tipo']}</div>"
                    f"<span style='background:{cor};color:white;padding:2px 8px;"
                    f"border-radius:10px;font-size:11px'>{a['gravidade']}</span>"
                    f"</div>"
                    f"<div style='color:#444;font-size:13px;margin-top:4px'>{a['descricao']}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

            st.divider()
            st.subheader("Recomendacoes")
            if altas:
                st.error(f"{len(altas)} animal(is) com anomalia grave - avaliar imediatamente")
            if medias:
                st.warning(f"{len(medias)} animal(is) com anomalia media - monitorar de perto")
            st.info("Registre novas pesagens para validar os padroes identificados")


def page_previsao_abate(u):
    hdr("Previsao Abate", "Previsao de Abate", "Data estimada e receita projetada por GMD")
    lote_id, _ = sel_lote("abate_lote")
    if lote_id:
        animais = listar_animais_por_lote(lote_id)
        if not animais: st.warning("Nenhum animal."); st.stop()
        preco_kg = st.number_input("Preco de abate (R$/kg)", 0.0, 100.0, 20.0)
        st.info("Defina o peso alvo em Prontuario do Animal para cada animal.")
        resultados = []
        for a in animais:
            prev = calcular_previsao_abate(a[0])
            if "erro" not in prev:
                resultados.append({"Animal": a[1], "Peso Atual": prev["peso_atual"],
                    "Peso Alvo": prev["peso_alvo"], "GMD": prev["gmd"],
                    "Dias Rest.": prev["dias_restantes"], "Data Prevista": prev["data_prevista"],
                    "Receita Est.": round(prev["peso_alvo"]*preco_kg,2), "Confianca": prev["confianca"]})
        if resultados:
            df_prev = pd.DataFrame(resultados).sort_values("Dias Rest.")
            st.dataframe(df_prev, width='stretch')
            pr1,pr2 = st.columns(2)
            pr1.metric("Animais analisados", len(resultados))
            pr2.metric("Receita total estimada", f"R$ {sum(r['Receita Est.'] for r in resultados):,.2f}")
            st.bar_chart(df_prev.set_index("Animal")["Dias Rest."])
            for r in resultados:
                if r["Dias Rest."] == 0:   st.success(f"{r['Animal']}: atingiu o peso alvo!")
                elif r["Dias Rest."] <= 15: st.warning(f"{r['Animal']}: {r['Dias Rest.']} dias - prepare o abate")
        else: st.info("Nenhum animal com peso alvo e pesagens suficientes.")

    # ============================================================
    # PRONTUARIO ANIMAL
    # ============================================================
