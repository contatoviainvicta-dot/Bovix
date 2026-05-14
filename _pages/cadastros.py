# pages/cadastros.py -- Telas: Cadastrar Lote, Cadastrar Animal, Registrar Pesagem, Registrar Ocorrencia, Registrar Morte, Importar CSV, Editar Lote, Editar Animal, Editar Pesagens, Gerenciar Ocorrencias, Transferir Animal, Status do Lote

import streamlit as st
import pandas as pd
from datetime import datetime, date
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

def page_cadastrar_lote(u):
    lotes = listar_lotes_usuario()
    hdr("Cadastrar Lote", "Novo Lote", "Registre um novo lote de animais")
    c1,c2 = st.columns([2,1])
    with c1:
        with st.form("form_lote"):
            st.markdown("#### Dados do lote")
            col1,col2 = st.columns(2)
            with col1:
                nome         = st.text_input("Nome do lote *")
                data_ent     = st.date_input("Data de entrada")
                qtd_comp     = st.number_input("Qtd comprada", 0, step=1)
                transporte   = st.text_input("Transportadora")
            with col2:
                descricao    = st.text_area("Descricao", height=70)
                qtd_rec      = st.number_input("Qtd recebida", 0, step=1)
                preco_anim   = st.number_input("Preco por animal (R$)", 0.0)
            st.markdown("#### Manejo")
            m1,m2 = st.columns(2)
            with m1: tipo_alim = st.selectbox("Alimentacao", ["Pasto","Confinamento","Semi-confinamento"])
            with m2: tipo_diet = st.selectbox("Dieta", ["Capim","Racao","Silagem","Misto"])
            salvar = st.form_submit_button("Salvar Lote", width='stretch', type="primary")
        if salvar:
            if not nome:               st.error("Informe o nome do lote")
            elif qtd_rec > qtd_comp:   st.error("Qtd recebida nao pode ser maior que comprada")
            elif qtd_rec == 0:         st.error("Informe a quantidade recebida")
            else:
                _oid_lote = u.get("owner_id", u["id"])
                lid = adicionar_lote(nome, descricao, str(data_ent), qtd_comp, qtd_rec, transporte,
                                    owner_id=_oid_lote)
                registrar_auditoria(u["id"], "criar_lote", "lotes", lid, nome)
                limpar_cache()
                st.success(f"Lote **{nome}** criado!")
    with c2:
        st.markdown("#### Dicas")
        st.info("Use um nome facil de identificar, ex: Nelore Jan/25")
        st.info("Qtd recebida pode ser menor que a comprada se houve perdas no transporte")
        if qtd_comp > 0 and preco_anim > 0:
            st.metric("Custo total estimado", f"R$ {preco_anim*qtd_comp:,.2f}")

    # ============================================================
    # CADASTRAR ANIMAL
    # ============================================================


def page_cadastrar_animal(u):
    hdr("Cadastrar Animal", "Novo Animal", "Vincule um animal a um lote")
    lotes = listar_lotes_usuario()
    if not lotes:
        st.warning("Cadastre um lote primeiro.")
    else:
        dict_l = {f"{l[1]} (ID {l[0]})": l[0] for l in lotes}
        c_sel,c_info = st.columns([2,1])
        with c_sel: lote_sel = st.selectbox("Lote", list(dict_l.keys()))
        lote_id = dict_l[lote_sel]
        lote    = obter_lote(lote_id)
        total   = contar_animais_no_lote(lote_id)
        vagas   = max(0, lote[5] - total)
        with c_info:
            st.metric("Cadastrados / Capacidade", f"{total} / {lote[5]}",
                      delta=f"{vagas} vaga(s)" if vagas > 0 else "Lote cheio",
                      delta_color="normal" if vagas > 0 else "inverse")
        if total >= lote[5]:
            st.error("Limite do lote atingido.")
        else:
            with st.form("form_animal"):
                a1,a2,a3 = st.columns(3)
                with a1: ident  = st.text_input("Brinco / Identificacao *", placeholder="BOI-001")
                with a2: idade  = st.number_input("Idade (meses)", 0, 240, 24)
                with a3: p_ent  = st.number_input("Peso entrada (kg)", 0.0)
                b1,b2,b3 = st.columns(3)
                with b1: raca   = st.text_input("Raca", placeholder="Nelore")
                with b2: sexo   = st.selectbox("Sexo", ["indefinido","macho","femea"])
                with b3: p_alvo = st.number_input("Peso alvo abate (kg)", 0.0)
                salvar = st.form_submit_button("Cadastrar Animal", width='stretch', type="primary")
            if salvar:
                if not ident:
                    st.error("Informe a identificacao do animal")
                else:
                    # Verificar limite do plano antes de cadastrar
                    _oid_anim = u.get("owner_id", u["id"])
                    _lim = verificar_limite_animais(_oid_anim) if not is_admin() else dict(ok=True)
                    if not _lim["ok"]:
                        st.error(f"Limite do plano atingido: {_lim.get('msg','')}. Faca upgrade para continuar.")
                    else:
                        aid = adicionar_animal(ident, idade, lote_id)
                        if p_alvo > 0: atualizar_animal_detalhes(aid, peso_alvo=p_alvo)
                        registrar_auditoria(u["id"], "cadastro_animal", "animais", aid, ident)
                        limpar_cache()
                        st.success(f"**{ident}** cadastrado no lote **{lote[1]}**!")
                        st.rerun()

    # ============================================================
    # REGISTRAR PESAGEM
    # ============================================================


def page_registrar_pesagem(u):
    hdr("Registrar Pesagem", "Novo Peso", "Registre o peso atual de um animal")
    lotes = listar_lotes_usuario()
    if not lotes:
        st.warning("Cadastre um lote primeiro.")
    else:
        dict_l = {f"{l[1]} (ID {l[0]})": l[0] for l in lotes}
        c1,c2 = st.columns(2)
        with c1: lote_sel = st.selectbox("Lote", list(dict_l.keys()), key="pes_lote")
        lote_id = dict_l[lote_sel]
        animais = listar_animais_por_lote(lote_id)
        if not animais:
            st.warning("Nenhum animal neste lote.")
        else:
            dict_a = {f"{a[1]} (ID {a[0]})": a[0] for a in animais}
            with c2: anim_sel = st.selectbox("Animal", list(dict_a.keys()), key="pes_anim")
            animal_id = dict_a[anim_sel]
            ps_ant = listar_pesagens(animal_id)
            if ps_ant:
                ult = ps_ant[-1]
                det = obter_animal(animal_id)
                r1,r2,r3 = st.columns(3)
                r1.metric("Ultimo peso", f"{ult[2]:.1f} kg", f"em {ult[3]}")
                if det and det[7] > 0:
                    falta = det[7] - ult[2]
                    r2.metric("Peso alvo", f"{det[7]:.0f} kg", f"faltam {falta:.1f} kg" if falta>0 else "Atingido!")
                if len(ps_ant) >= 2:
                    df_r = pd.DataFrame(ps_ant, columns=["id","aid","peso","data"])
                    df_r["data"] = pd.to_datetime(df_r["data"])
                    df_r = df_r.sort_values("data")
                    dias_r = (df_r["data"].iloc[-1]-df_r["data"].iloc[0]).days
                    if dias_r > 0:
                        gmd_r = (df_r["peso"].iloc[-1]-df_r["peso"].iloc[0])/dias_r
                        r3.metric("GMD atual", f"{gmd_r:.3f} kg/dia")
                st.divider()
            with st.form("form_pesagem"):
                p1,p2 = st.columns(2)
                with p1: peso   = st.number_input("Peso (kg) *", 0.0, 1000.0, step=0.5)
                with p2: data_p = st.date_input("Data")
                salvar = st.form_submit_button("Salvar Pesagem", width='stretch', type="primary")
            if salvar:
                if peso <= 0:    st.error("Peso invalido")
                elif peso > 1000: st.error("Peso muito alto")
                else:
                    adicionar_pesagem(animal_id, peso, str(data_p))
                    registrar_auditoria(u["id"], "pesagem", "pesagens", animal_id, f"{peso}kg em {data_p}")
                    st.success(f"Pesagem de **{peso:.1f} kg** registrada!")
                    st.rerun()

    # ============================================================
    # REGISTRAR OCORRENCIA
    # ============================================================


def page_registrar_ocorrencia(u):
    hdr("Registrar Ocorrencia", "Nova Ocorrencia", "Doencas, lesoes e medicacoes")
    lotes = listar_lotes_usuario()
    if not lotes:
        st.warning("Cadastre um lote primeiro.")
    else:
        dict_l = {f"{l[1]} (ID {l[0]})": l[0] for l in lotes}
        o1,o2 = st.columns(2)
        with o1: lote_sel = st.selectbox("Lote", list(dict_l.keys()), key="oc_lote")
        lote_id = dict_l[lote_sel]
        animais = listar_animais_por_lote(lote_id)
        if not animais:
            st.warning("Nenhum animal neste lote.")
        else:
            dict_a = {f"{a[1]} (ID {a[0]})": a[0] for a in animais}
            with o2: anim_sel = st.selectbox("Animal", list(dict_a.keys()), key="oc_anim")
            animal_id = dict_a[anim_sel]
            with st.form("form_oc"):
                oc1,oc2,oc3 = st.columns(3)
                with oc1: data_oc  = st.date_input("Data")
                with oc2: tipo_oc  = st.selectbox("Tipo", ["Doenca","Lesao","Medicamento","Outros"])
                with oc3: grav_oc  = st.selectbox("Gravidade", ["Baixa","Media","Alta"])
                desc_oc  = st.text_area("Descricao")
                oc4,oc5,oc6 = st.columns(3)
                with oc4: custo_oc = st.number_input("Custo (R$)", 0.0)
                with oc5: dias_oc  = st.number_input("Dias recuperacao", 0)
                with oc6: stat_oc  = st.selectbox("Status", ["Em tratamento","Resolvido"])
                salvar = st.form_submit_button("Salvar Ocorrencia", width='stretch', type="primary")
            if salvar:
                oid = adicionar_ocorrencia(animal_id, str(data_oc), tipo_oc, desc_oc, grav_oc, custo_oc, dias_oc, stat_oc)
                registrar_auditoria(u["id"], "ocorrencia", "ocorrencias", oid, f"{tipo_oc}/{grav_oc}")
                st.success("Ocorrencia registrada!")
                st.rerun()

    # ============================================================
    # REGISTRAR MORTE
    # ============================================================


def page_registrar_morte(u):
    hdr("Registrar Morte", "Baixa de Animal", "Registre a morte e retire o animal do lote")
    tab1,tab2 = st.tabs(["Registrar", "Historico"])
    with tab1:
        lotes = listar_lotes_usuario()
        if not lotes:
            st.warning("Cadastre um lote primeiro.")
        else:
            dict_l = {f"{l[1]} (ID {l[0]})": l[0] for l in lotes}
            lote_sel_m = st.selectbox("Lote", list(dict_l.keys()), key="morte_lote")
            lote_id_m  = dict_l[lote_sel_m]
            animais_m  = listar_animais_por_lote(lote_id_m)
            if not animais_m:
                st.warning("Nenhum animal ativo neste lote.")
            else:
                dict_am = {f"{a[1]} (ID {a[0]})": a[0] for a in animais_m}
                with st.form("form_morte"):
                    anim_sel_m = st.selectbox("Animal", list(dict_am.keys()))
                    m1,m2 = st.columns(2)
                    with m1:
                        data_m  = st.date_input("Data")
                        causa_m = st.selectbox("Causa", ["Doenca","Acidente","Desaparecimento","Predador","Outras"])
                    with m2:
                        custo_m = st.number_input("Custo da perda (R$)", 0.0)
                        desc_m  = st.text_area("Descricao")
                    salvar = st.form_submit_button("Registrar Morte", width='stretch', type="primary")
                if salvar:
                    registrar_morte(dict_am[anim_sel_m], str(data_m), causa_m, desc_m, custo_m)
                    registrar_auditoria(u["id"], "morte_animal", "animais", dict_am[anim_sel_m], f"{anim_sel_m} - {causa_m}")
                    st.success("Morte registrada. Animal removido do lote.")
                    st.rerun()
    with tab2:
        lotes = listar_lotes_usuario()
        if lotes:
            dict_l2 = {"Todos": None, **{f"{l[1]} (ID {l[0]})": l[0] for l in lotes}}
            filtro_m = st.selectbox("Filtrar por lote", list(dict_l2.keys()), key="mort_hist")
            morts = listar_mortalidade(dict_l2[filtro_m])
            if morts:
                df_m = pd.DataFrame(morts, columns=["ID","Animal ID","Animal","Data","Causa","Descricao","Custo Perda"])
                st.dataframe(df_m, width='stretch')
                st.metric("Custo total perdas", f"R$ {sum(m[6] for m in morts if m[6]):.2f}")
            else:
                st.success("Nenhuma morte registrada.")

    # ============================================================
    # IMPORTAR CSV
    # ============================================================


def page_importar_csv(u):
    hdr("Importar CSV", "Importacao em Lote", "Importe pesagens e animais via planilha CSV")
    lotes = listar_lotes_usuario()
    st.subheader("Lote de destino")
    opcao = st.radio("", ["Usar lote existente","Criar novo lote"], horizontal=True, key="imp_op")
    lote_id = None
    if opcao == "Criar novo lote":
        with st.form("form_lote_imp"):
            ci1,ci2 = st.columns(2)
            with ci1:
                nome_nl = st.text_input("Nome do lote *")
                qtd_c2  = st.number_input("Qtd comprada", 0, step=1)
                qtd_r2  = st.number_input("Qtd recebida", 0, step=1)
            with ci2:
                data_nl = st.date_input("Data entrada")
                trp_nl  = st.text_input("Transportadora")
            if st.form_submit_button("Criar lote"):
                if nome_nl:
                    lote_id = adicionar_lote(nome_nl, "", str(data_nl), qtd_c2, qtd_r2, trp_nl, owner_id=u.get("owner_id", u["id"]))
                    registrar_auditoria(u["id"], "criar_lote", "lotes", lote_id, nome_nl)
                    limpar_cache()
                    st.success(f"Lote '{nome_nl}' criado!")
                    st.rerun()
                else: st.error("Informe o nome.")
        lotes = listar_lotes_usuario()
        if lotes: lote_id = lotes[0][0]; st.info(f"Lote: {lotes[0][1]}")
    else:
        if not lotes: st.warning("Crie um lote primeiro."); st.stop()
        dict_l = {f"{l[1]} (ID {l[0]})": l[0] for l in lotes}
        lote_id = dict_l[st.selectbox("Selecione o lote", list(dict_l.keys()), key="imp_lote")]

    if not lote_id: st.stop()
    st.divider()
    tab_p,tab_a = st.tabs(["Importar Pesagens","Importar Animais"])

    with tab_p:
        st.markdown("**Formato CSV:**")
        st.code("identificacao,peso,data\nBOI-001,310.5,2024-01-15")
        arq = st.file_uploader("CSV de pesagens", type=["csv"], key="csv_pes")
        if arq:
            import csv, io as _io
            txt = arq.read().decode("utf-8-sig", errors="ignore")
            linhas = list(csv.DictReader(_io.StringIO(txt)))
            st.info(f"{len(linhas)} linhas encontradas.")
            if st.button("Importar pesagens"):
                res = importar_pesagens_csv(linhas, lote_id)
                registrar_auditoria(u["id"], "import_pesagens", "pesagens", lote_id, f"{res['importados']} importadas")
                st.success(f"Importadas: {res['importados']} | Animais criados: {res['animais_criados']} | Erros: {res['erros']}")
                for msg in res["mensagens"]: st.warning(msg)

    with tab_a:
        st.markdown("**Formato CSV:**")
        st.code("identificacao,idade,raca,sexo,peso_alvo\nBOI-001,24,Nelore,macho,450")
        arq2 = st.file_uploader("CSV de animais", type=["csv"], key="csv_anim")
        if arq2:
            import csv, io as _io
            txt2 = arq2.read().decode("utf-8-sig", errors="ignore")
            linhas2 = list(csv.DictReader(_io.StringIO(txt2)))
            st.info(f"{len(linhas2)} linhas encontradas.")
            if st.button("Importar animais"):
                # Verificar limite do plano ANTES de importar
                n_novos = len(linhas2)
                lim = verificar_limite_animais(u["id"], n_novos)
                if not lim["pode"]:
                    st.error(
                        f"Importacao bloqueada: voce tentou importar {n_novos} animais "
                        f"mas seu plano permite apenas {lim['disponiveis']} adicionais "
                        f"(limite: {lim['limite']}, atual: {lim['atual']}). "
                        f"Faca upgrade do plano para continuar."
                    )
                else:
                    res2 = importar_animais_csv(linhas2, lote_id)
                    registrar_auditoria(u["id"], "import_animais", "animais", lote_id, f"{res2['importados']} importados")
                    st.success(f"Importados: {res2['importados']} | Erros: {res2['erros']}")
                    for msg in res2["mensagens"]: st.warning(msg)

    # ============================================================
    # DASHBOARD SANITARIO
    # ============================================================


def page_editar_lote(u):
    hdr("Editar Lote", "Editar / Excluir Lote", "Altere ou remova um lote cadastrado")

    # Botao de sincronizacao em massa (corrige dados historicos)
    with st.expander("Corrigir contagem de animais em todos os lotes"):
        st.caption("Use este botao se a quantidade de animais exibida estiver incorreta.")
        if st.button("Sincronizar todos os lotes agora", key="sync_todos"):
            resultados = sincronizar_todos_lotes()
            for lid_s, nome_s, n_s in resultados:
                st.write(f"Lote **{nome_s}**: {n_s} animais ativos")
            st.success("Contagens atualizadas com sucesso!")
            st.rerun()

    lotes = listar_lotes_usuario()
    if not lotes:
        st.warning("Nenhum lote cadastrado.")
    else:
        dict_l  = {f"{l[1]} (ID {l[0]})": l[0] for l in lotes}
        lote_sel = st.selectbox("Selecione o lote para editar", list(dict_l.keys()), key="ed_lote")
        lote_id  = dict_l[lote_sel]
        lote     = obter_lote(lote_id)
        rs       = resumo_lote(lote_id)

        # Resumo do lote
        k1,k2,k3,k4 = st.columns(4)
        k1.metric("Animais ativos", rs["ativos"])
        k2.metric("Ocorrencias",    rs["ocorrencias"])
        k3.metric("Mortes",         rs["mortos"])
        k4.metric("GTAs emitidas",  rs["gtas_emitidas"])
        st.divider()

        # Contagem real de animais ativos (fonte da verdade)
        ativos_reais = rs["ativos"]
        st.info(f"Animais ativos no banco: **{ativos_reais}** (calculado automaticamente a partir dos cadastros)")

        tab_edit, tab_del = st.tabs(["Editar dados", "Excluir lote"])

        with tab_edit:
            with st.form("form_edit_lote"):
                el1,el2 = st.columns(2)
                with el1:
                    nome_e     = st.text_input("Nome *",          value=lote[1])
                    data_e     = st.date_input("Data entrada",    value=pd.to_datetime(lote[3]).date())
                    qtd_comp_e = st.number_input("Qtd comprada",  0, step=1, value=int(lote[4]))
                    transp_e   = st.text_input("Transportadora",  value=lote[6] or "")
                with el2:
                    desc_e     = st.text_area("Descricao",        value=lote[2] or "", height=70)
                    st.caption(f"Qtd recebida atual: {ativos_reais} animais ativos (atualizado automaticamente)")
                    preco_e    = st.number_input("Preco por animal (R$)", 0.0, step=50.0)
                salvar_e = st.form_submit_button("Salvar alteracoes", type="primary", width='stretch')
            if salvar_e:
                if not nome_e:
                    st.error("Informe o nome do lote.")
                else:
                    # qtd_recebida e sempre recalculada pelos animais ativos reais
                    atualizar_lote(lote_id, nome_e, desc_e, str(data_e), qtd_comp_e, ativos_reais, transp_e, preco_e)
                    registrar_auditoria(u["id"], "editar_lote", "lotes", lote_id, nome_e)
                    limpar_cache()
                    st.success(f"Lote **{nome_e}** atualizado! Animais ativos: {ativos_reais}")
                    st.rerun()

        with tab_del:
            st.warning("A exclusao e permanente e nao pode ser desfeita.")
            n_anim = contar_animais_no_lote(lote_id, incluir_inativos=True)
            if n_anim > 0:
                st.error(f"Impossivel excluir: este lote tem {n_anim} animal(is) cadastrado(s).")
                st.info("Exclua ou transfira todos os animais antes de remover o lote.")
            else:
                confirma = st.checkbox("Confirmo que desejo excluir este lote permanentemente")
                if confirma:
                    if st.button("Excluir lote definitivamente", type="primary"):
                        excluir_lote(lote_id)
                        registrar_auditoria(u["id"], "excluir_lote", "lotes", lote_id, lote[1])
                        limpar_cache()
                        st.success("Lote excluido com sucesso.")
                        st.rerun()

    # ============================================================
    # EDITAR ANIMAL
    # ============================================================


def page_editar_animal(u):
    hdr("Editar Animal", "Editar / Excluir Animal", "Altere ou remova um animal cadastrado")
    lotes = listar_lotes_usuario()
    if not lotes:
        st.warning("Nenhum lote cadastrado.")
    else:
        dict_l = {f"{l[1]} (ID {l[0]})": l[0] for l in lotes}
        ea1,ea2 = st.columns(2)
        with ea1: lote_sel = st.selectbox("Lote", list(dict_l.keys()), key="ea_lote")
        lote_id  = dict_l[lote_sel]
        # Mostrar todos incluindo inativos para poder editar
        animais  = listar_animais_por_lote(lote_id, incluir_inativos=True)
        if not animais:
            st.warning("Nenhum animal neste lote.")
        else:
            dict_a = {f"{a[1]} (ID {a[0]})": a[0] for a in animais}
            with ea2: anim_sel = st.selectbox("Animal", list(dict_a.keys()), key="ea_anim")
            animal_id = dict_a[anim_sel]
            det = obter_animal(animal_id)

            # Indicadores do animal
            n_pes = len(listar_pesagens(animal_id))
            n_ocs = len(listar_ocorrencias(animal_id))
            sc    = calcular_score_saude(animal_id)
            i1,i2,i3 = st.columns(3)
            i1.metric("Pesagens",     n_pes)
            i2.metric("Ocorrencias",  n_ocs)
            i3.metric("Score saude",  f"{sc['score']}/100")
            st.divider()

            tab_edit, tab_del = st.tabs(["Editar dados", "Excluir animal"])

            with tab_edit:
                with st.form("form_edit_animal"):
                    eab1,eab2 = st.columns(2)
                    with eab1:
                        ident_e  = st.text_input("Identificacao / Brinco *", value=det[1] if det else "")
                        idade_e  = st.number_input("Idade (meses)", 0, 240, value=int(det[2]) if det else 0)
                        raca_e   = st.text_input("Raca", value=det[5] if det else "")
                    with eab2:
                        p_alvo_e = st.number_input("Peso alvo abate (kg)", 0.0, value=float(det[7]) if det else 0.0)
                        sexo_e   = st.selectbox("Sexo", ["indefinido","macho","femea"],
                                                 index=["indefinido","macho","femea"].index(det[4])
                                                 if det and det[4] in ["indefinido","macho","femea"] else 0)
                        obs_e    = st.text_area("Observacoes", value=det[8] if det else "", height=68)
                    salvar_ea = st.form_submit_button("Salvar alteracoes", type="primary", width='stretch')
                if salvar_ea:
                    if not ident_e:
                        st.error("Informe a identificacao.")
                    else:
                        atualizar_animal(animal_id, ident_e, idade_e)
                        atualizar_animal_detalhes(animal_id,
                                                  peso_alvo=p_alvo_e if p_alvo_e > 0 else None,
                                                  observacoes=obs_e)
                        registrar_auditoria(u["id"], "editar_animal", "animais", animal_id, ident_e)
                        st.success(f"Animal **{ident_e}** atualizado!")
                        st.rerun()

            with tab_del:
                st.warning("A exclusao remove o animal e todo seu historico.")
                st.caption(f"Este animal tem {n_pes} pesagem(ns) e {n_ocs} ocorrencia(s).")
                confirma_a = st.checkbox("Confirmo a exclusao permanente deste animal")
                if confirma_a:
                    if st.button("Excluir animal definitivamente", type="primary"):
                        excluir_animal(animal_id)
                        registrar_auditoria(u["id"], "excluir_animal", "animais", animal_id, det[1] if det else "")
                        st.success("Animal excluido.")
                        st.rerun()

    # ============================================================
    # EDITAR PESAGENS
    # ============================================================


def page_editar_pesagens(u):
    hdr("Editar Pesagens", "Corrigir Pesagens", "Edite ou exclua pesagens incorretas")
    lotes = listar_lotes_usuario()
    if not lotes:
        st.warning("Nenhum lote cadastrado.")
    else:
        dict_l  = {f"{l[1]} (ID {l[0]})": l[0] for l in lotes}
        ep1,ep2 = st.columns(2)
        with ep1: lote_sel = st.selectbox("Lote", list(dict_l.keys()), key="ep_lote")
        lote_id  = dict_l[lote_sel]
        animais  = listar_animais_por_lote(lote_id)

        if not animais:
            st.warning("Nenhum animal neste lote.")
        else:
            modo = st.radio("Visualizar", ["Todas do lote","Por animal"], horizontal=True)

            if modo == "Por animal":
                dict_a = {f"{a[1]} (ID {a[0]})": a[0] for a in animais}
                with ep2: anim_sel = st.selectbox("Animal", list(dict_a.keys()), key="ep_anim")
                pesagens = listar_pesagens(dict_a[anim_sel])
            else:
                pesagens_raw = listar_pesagens_lote(lote_id)
                pesagens     = [(r[0], r[4], r[2], r[3]) for r in pesagens_raw]
                nomes_map    = {r[4]: r[1] for r in pesagens_raw}

            if not pesagens:
                st.info("Nenhuma pesagem registrada.")
            else:
                # Tabela visual
                df_ps = pd.DataFrame(pesagens, columns=["ID","Animal ID","Peso (kg)","Data"])
                if modo == "Todas do lote" and "nomes_map" in dir():
                    df_ps["Animal"] = df_ps["Animal ID"].map(nomes_map)
                    df_ps = df_ps[["ID","Animal","Peso (kg)","Data"]]
                df_ps["Data"] = pd.to_datetime(df_ps["Data"]).dt.strftime("%d/%m/%Y")
                st.dataframe(df_ps, width='stretch')

                st.divider()
                st.subheader("Selecionar pesagem para editar")
                dict_pes = {f"ID {p[0]} | {pd.to_datetime(p[3]).strftime('%d/%m/%Y')} | {p[2]:.1f} kg": p[0]
                            for p in pesagens}
                pes_sel  = st.selectbox("Pesagem", list(dict_pes.keys()), key="ep_pes")
                pes_id   = dict_pes[pes_sel]
                pes_cur  = next((p for p in pesagens if p[0]==pes_id), None)

                tab_edit_p, tab_del_p = st.tabs(["Corrigir", "Excluir"])

                with tab_edit_p:
                    with st.form("form_edit_pes"):
                        fe1,fe2 = st.columns(2)
                        with fe1:
                            peso_novo = st.number_input("Peso (kg) *", 0.0, 1000.0,
                                                         value=float(pes_cur[2]) if pes_cur else 0.0,
                                                         step=0.5)
                        with fe2:
                            data_nova = st.date_input("Data",
                                                       value=pd.to_datetime(pes_cur[3]).date() if pes_cur else date.today())
                        if st.form_submit_button("Salvar correcao", type="primary", width='stretch'):
                            if peso_novo <= 0:       st.error("Peso invalido.")
                            elif peso_novo > 1000:   st.error("Peso muito alto.")
                            else:
                                atualizar_pesagem(pes_id, peso_novo, str(data_nova))
                                registrar_auditoria(u["id"], "editar_pesagem", "pesagens", pes_id,
                                                    f"{peso_novo}kg em {data_nova}")
                                st.success("Pesagem corrigida!")
                                st.rerun()

                with tab_del_p:
                    if pes_cur:
                        st.warning(f"Excluir pesagem de {pes_cur[2]:.1f} kg registrada em {pd.to_datetime(pes_cur[3]).strftime('%d/%m/%Y')}?")
                    confirma_p = st.checkbox("Confirmo a exclusao desta pesagem")
                    if confirma_p:
                        if st.button("Excluir pesagem", type="primary"):
                            excluir_pesagem(pes_id)
                            registrar_auditoria(u["id"], "excluir_pesagem", "pesagens", pes_id, "excluido")
                            st.success("Pesagem excluida.")
                            st.rerun()

    # ============================================================
    # GERENCIAR OCORRENCIAS
    # ============================================================


def page_gerenciar_ocorrencias(u):
    hdr("Gerenciar Ocorrencias", "Tratamentos e Ocorrencias", "Edite ocorrencias e resolva tratamentos pendentes")

    # ── Painel de alertas de tratamentos vencidos ──────────────────────
    vencidos = listar_tratamentos_vencidos(owner_id=owner_id())
    if vencidos:
        st.error(f"ATENCAO: {len(vencidos)} tratamento(s) com prazo vencido!")
        with st.expander(f"Ver {len(vencidos)} tratamento(s) vencido(s)", expanded=True):
            for v in vencidos:
                try:
                    prev_alta  = pd.to_datetime(v[10]).date()
                    dias_atraso = (date.today() - prev_alta).days
                except Exception:
                    dias_atraso = 0
                c1,c2,c3,c4 = st.columns([2,2,1,2])
                c1.write(f"**{v[2]}**")
                c2.write(f"Lote: {v[3]}")
                c3.write(f"Tipo: {v[5]}")
                c4.write(f"Vencido ha {dias_atraso} dia(s)")
    else:
        st.success("Nenhum tratamento com prazo vencido.")

    st.divider()

    # ── Selecao ────────────────────────────────────────────────────────
    lotes = listar_lotes_usuario()
    if not lotes:
        st.warning("Nenhum lote cadastrado.")
        st.stop()

    dict_l   = {f"{l[1]} (ID {l[0]})": l[0] for l in lotes}
    go1,go2  = st.columns(2)
    with go1: lote_sel = st.selectbox("Lote", list(dict_l.keys()), key="go_lote")
    lote_id  = dict_l[lote_sel]
    animais  = listar_animais_por_lote(lote_id)

    if not animais:
        st.warning("Nenhum animal neste lote.")
        st.stop()

    dict_a   = {f"{a[1]} (ID {a[0]})": a[0] for a in animais}
    with go2: anim_sel = st.selectbox("Animal", list(dict_a.keys()), key="go_anim")
    animal_id = dict_a[anim_sel]
    ocs = listar_ocorrencias(animal_id)

    if not ocs:
        st.info("Nenhuma ocorrencia registrada para este animal.")
        st.stop()

    # ── Cards de status ────────────────────────────────────────────────
    st.subheader(f"Ocorrencias de {anim_sel.split(' (ID')[0]}")

    em_trat  = [o for o in ocs if o[8] == "Em tratamento"]
    resolvidas = [o for o in ocs if o[8] == "Resolvido"]

    r1,r2,r3 = st.columns(3)
    r1.metric("Total",         len(ocs))
    r2.metric("Em tratamento", len(em_trat),
              delta="Atencao" if em_trat else None,
              delta_color="inverse" if em_trat else "normal")
    r3.metric("Resolvidas",    len(resolvidas))

    st.divider()

    for oc in ocs:
        oc_id, _, data_oc, tipo_oc, desc_oc, grav_oc, custo_oc, dias_oc, stat_oc = oc
        try:
            prev_alta   = (pd.to_datetime(data_oc) + pd.Timedelta(days=int(dias_oc or 0))).date()
            dias_rest   = (prev_alta - date.today()).days
            atraso      = max(0, -dias_rest) if stat_oc == "Em tratamento" else 0
        except Exception:
            prev_alta = None; dias_rest = 0; atraso = 0

        if stat_oc == "Resolvido":
            ic = "Resolvido"
            st.success(f"{ic} | {data_oc} | {tipo_oc} | Grav: {grav_oc} | {desc_oc[:60]}")
        elif atraso > 0:
            ic = f"VENCIDO ha {atraso} dia(s)"
            st.error(f"{ic} | {data_oc} | {tipo_oc} | Prev. alta: {prev_alta} | {desc_oc[:60]}")
        else:
            ic = f"Em tratamento | faltam {dias_rest}d"
            st.warning(f"{ic} | {data_oc} | {tipo_oc} | Prev. alta: {prev_alta} | {desc_oc[:60]}")

    st.divider()
    st.subheader("Selecionar ocorrencia para editar")

    dict_oc = {}
    for oc in ocs:
        label = f"ID {oc[0]} | {oc[2]} | {oc[3]} | {oc[8]}"
        dict_oc[label] = oc[0]

    oc_sel  = st.selectbox("Ocorrencia", list(dict_oc.keys()), key="go_oc_sel")
    oc_id   = dict_oc[oc_sel]
    oc_cur  = next((o for o in ocs if o[0]==oc_id), None)

    if oc_cur:
        stat_cur = oc_cur[8]
        is_resolv = (stat_cur == "Resolvido")

        if is_resolv:
            st.info("Esta ocorrencia esta resolvida. Voce pode editar os dados mas nao pode reabrir o tratamento.")

        tab_edit_o, tab_del_o = st.tabs(["Editar ocorrencia", "Excluir"])

        with tab_edit_o:
            with st.form("form_edit_oc"):
                oe1,oe2,oe3 = st.columns(3)
                with oe1:
                    data_oe = st.date_input("Data",    value=pd.to_datetime(oc_cur[2]).date())
                    tipo_oe = st.selectbox("Tipo",     ["Doenca","Lesao","Medicamento","Outros"],
                                            index=["Doenca","Lesao","Medicamento","Outros"].index(oc_cur[3])
                                            if oc_cur[3] in ["Doenca","Lesao","Medicamento","Outros"] else 0)
                with oe2:
                    grav_oe  = st.selectbox("Gravidade",["Baixa","Media","Alta"],
                                             index=["Baixa","Media","Alta"].index(oc_cur[5])
                                             if oc_cur[5] in ["Baixa","Media","Alta"] else 0)
                    custo_oe = st.number_input("Custo (R$)", 0.0,
                                               value=float(oc_cur[6]) if oc_cur[6] else 0.0)
                with oe3:
                    dias_oe  = st.number_input("Dias recuperacao", 0,
                                               value=int(oc_cur[7]) if oc_cur[7] else 0)
                    if is_resolv:
                        st.info("Status: Resolvido (imutavel)")
                        stat_oe = "Resolvido"
                    else:
                        stat_oe = st.selectbox("Novo status",
                                               ["Em tratamento","Resolvido"],
                                               index=0 if stat_cur=="Em tratamento" else 1)
                desc_oe   = st.text_area("Descricao", value=oc_cur[4] or "")
                salvar_oc = st.form_submit_button("Salvar alteracoes", type="primary", width='stretch')

            if salvar_oc:
                atualizar_ocorrencia(oc_id, tipo_oe, desc_oe, grav_oe, custo_oe, dias_oe, stat_oe, str(data_oe))
                registrar_auditoria(u["id"], "editar_ocorrencia", "ocorrencias", oc_id,
                                    f"{tipo_oe}/{grav_oe}/{stat_oe}")
                if stat_oe == "Resolvido" and stat_cur == "Em tratamento":
                    st.success("Tratamento encerrado! Ocorrencia marcada como Resolvida.")
                else:
                    st.success("Ocorrencia atualizada!")
                st.rerun()

        with tab_del_o:
            if stat_cur == "Em tratamento":
                st.warning("Resolva o tratamento antes de excluir esta ocorrencia.")
                st.info("Edite o status para 'Resolvido' na aba ao lado e depois exclua se necessario.")
            else:
                st.warning("A exclusao e permanente e nao pode ser desfeita.")
                confirma_oc = st.checkbox("Confirmo a exclusao permanente desta ocorrencia")
                if confirma_oc:
                    if st.button("Excluir ocorrencia definitivamente", type="primary"):
                        excluir_ocorrencia(oc_id)
                        registrar_auditoria(u["id"], "excluir_ocorrencia", "ocorrencias", oc_id, "excluido")
                        st.success("Ocorrencia excluida.")
                        st.rerun()


    # ============================================================
    # TRANSFERIR ANIMAL
    # ============================================================


def page_transferir_animal(u):
    hdr("Transferir Animal", "Transferencia entre Lotes", "Mova animais mantendo o historico completo")

    lotes = listar_lotes_usuario()
    if len(lotes) < 2:
        st.warning("Necessario ter ao menos 2 lotes cadastrados para transferir animais.")
        st.stop()

    dict_l = {f"{l[1]} (ID {l[0]})": l[0] for l in lotes}

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Lote de Origem")
        lote_orig_s = st.selectbox("Selecione o lote de origem", list(dict_l.keys()), key="tr_orig")
        lote_orig_id = dict_l[lote_orig_s]

    animais_orig = listar_animais_por_lote(lote_orig_id)
    if not animais_orig:
        st.warning("Nenhum animal ativo neste lote.")
        st.stop()

    with col2:
        st.subheader("Lote de Destino")
        opcoes_dest = {k: v for k, v in dict_l.items() if v != lote_orig_id}
        lote_dest_s = st.selectbox("Selecione o lote de destino", list(opcoes_dest.keys()), key="tr_dest")
        lote_dest_id = opcoes_dest[lote_dest_s]

    st.divider()

    # Resumo dos lotes
    rs_orig = resumo_lote(lote_orig_id)
    rs_dest = resumo_lote(lote_dest_id)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Animais em " + lote_orig_s.split(" (")[0], rs_orig["ativos"])
    m2.metric("Animais em " + lote_dest_s.split(" (")[0], rs_dest["ativos"])
    m3.metric("Transferencias realizadas", len(listar_movimentacoes(lote_id=lote_orig_id)))
    m4.metric("Total historico", len(listar_movimentacoes()))

    st.divider()

    tab_unico, tab_massa, tab_historico = st.tabs(["Transferir 1 animal", "Transferir em massa", "Historico"])

    with tab_unico:
        dict_a = {f"{a[1]} (ID {a[0]})": a[0] for a in animais_orig}
        anim_s = st.selectbox("Animal para transferir", list(dict_a.keys()), key="tr_anim")
        animal_id = dict_a[anim_s]
        motivo = st.text_input("Motivo (opcional)", placeholder="Ex: Quarentena, Reagrupamento, Doenca")
        if st.button("Transferir animal", type="primary", width='stretch'):
            res = transferir_animal(animal_id, lote_dest_id, motivo, u["id"])
            if res["ok"]:
                registrar_auditoria(u["id"], "transferir_animal", "animais", animal_id,
                                    f"{lote_orig_s} -> {lote_dest_s}")
                st.success(f"Animal transferido com sucesso!")
                st.rerun()
            else:
                st.error(res["msg"])

    with tab_massa:
        st.caption("Selecione os animais que deseja transferir em grupo.")
        nomes = [f"{a[1]} (ID {a[0]})" for a in animais_orig]
        selecionados = st.multiselect("Selecionar animais", nomes, key="tr_massa")
        motivo_m = st.text_input("Motivo", placeholder="Ex: Reagrupamento", key="tr_mot_m")
        if selecionados:
            st.info(f"{len(selecionados)} animal(is) selecionado(s)")
            if st.button(f"Transferir {len(selecionados)} animal(is)", type="primary", width='stretch'):
                ok_count = 0
                for nome in selecionados:
                    aid_m = int(nome.split("ID ")[1].rstrip(")"))
                    res_m = transferir_animal(aid_m, lote_dest_id, motivo_m, u["id"])
                    if res_m["ok"]:
                        ok_count += 1
                registrar_auditoria(u["id"], "transferir_massa", "animais", lote_orig_id,
                                    f"{ok_count} animais -> {lote_dest_s}")
                st.success(f"{ok_count} animal(is) transferido(s) com sucesso!")
                if ok_count > 0:
                    pass  # transferencia ok
                st.rerun()

    with tab_historico:
        movs = listar_movimentacoes(lote_id=lote_orig_id)
        if movs:
            df_mov = pd.DataFrame(movs,
                columns=["ID", "Animal ID", "Animal", "Lote Origem", "Lote Destino", "Data", "Motivo"])
            st.dataframe(df_mov[["Animal", "Lote Origem", "Lote Destino", "Data", "Motivo"]],
                         width='stretch')
        else:
            st.info("Nenhuma transferencia registrada para este lote.")

    # ============================================================
    # STATUS DO LOTE
    # ============================================================


def page_status_do_lote(u):
    hdr("Status do Lote", "Gerenciar Status", "Atualize o status dos seus lotes e animais")

    lotes = listar_lotes_usuario()
    if not lotes:
        st.warning("Nenhum lote cadastrado.")
        st.stop()

    tab_lotes, tab_animais = st.tabs(["Status dos Lotes", "Status dos Animais"])

    with tab_lotes:
        st.subheader("Status atual dos lotes")

        COR_LOTE = {
            "ATIVO":      ("green",  "Operando normalmente"),
            "CRITICO":    ("red",    "Requer atencao imediata"),
            "QUARENTENA": ("orange", "Animais em isolamento"),
            "ENCERRADO":  ("gray",   "Lote finalizado"),
            "VENDIDO":    ("blue",   "Lote comercializado"),
        }

        _lotes_raw = listar_lotes_usuario()
        todos_lotes = [(l[0],l[1],l[2],l[3],l[4],l[5],l[6],l[7] if len(l)>7 else "ATIVO") for l in _lotes_raw]
        for lote_row in todos_lotes:
            lid_s, nome_s = lote_row[0], lote_row[1]
            status_s = lote_row[7] if len(lote_row) > 7 else "ATIVO"
            cor, desc = COR_LOTE.get(status_s, ("gray", ""))
            rs_s = resumo_lote(lid_s)
            with st.expander(f"{nome_s}  -  {status_s}  -  {rs_s['ativos']} animais ativos"):
                c1, c2 = st.columns([2, 1])
                with c1:
                    novo_status = st.selectbox(
                        "Alterar status", STATUS_LOTE,
                        index=STATUS_LOTE.index(status_s) if status_s in STATUS_LOTE else 0,
                        key=f"sl_{lid_s}"
                    )
                with c2:
                    st.write("")
                    st.write("")
                    if st.button("Salvar", key=f"sl_btn_{lid_s}", type="primary"):
                        atualizar_status_lote(lid_s, novo_status)
                        registrar_auditoria(u["id"], "status_lote", "lotes", lid_s, novo_status)
                        st.success(f"Status atualizado para {novo_status}")
                        st.rerun()

    with tab_animais:
        st.subheader("Status dos animais por lote")

        dict_l2 = {f"{l[1]} (ID {l[0]})": l[0] for l in lotes}
        lote_sel2 = st.selectbox("Selecione o lote", list(dict_l2.keys()), key="sa_lote")
        lote_id2  = dict_l2[lote_sel2]

        contagem = contagem_status_animais(lote_id2)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Ativos",      contagem["ATIVO"])
        c2.metric("Vendidos",    contagem["VENDIDO"])
        c3.metric("Mortos",      contagem["MORTO"])
        c4.metric("Transferidos",contagem["TRANSFERIDO"])
        c5.metric("Descartados", contagem["DESCARTADO"])

        st.divider()

        todos_anim = listar_animais_por_status(lote_id2)
        if not todos_anim:
            st.info("Nenhum animal neste lote.")
        else:
            for anim_row in todos_anim:
                aid_s, ident_s = anim_row[0], anim_row[1]
                status_a = anim_row[4] if len(anim_row) > 4 else "ATIVO"
                with st.expander(f"{ident_s}  -  {status_a}"):
                    col_a, col_b = st.columns([2, 1])
                    with col_a:
                        novo_sa = st.selectbox(
                            "Novo status", STATUS_ANIMAL,
                            index=STATUS_ANIMAL.index(status_a) if status_a in STATUS_ANIMAL else 0,
                            key=f"sa_{aid_s}"
                        )
                    with col_b:
                        st.write("")
                        st.write("")
                        if st.button("Salvar", key=f"sa_btn_{aid_s}", type="primary"):
                            atualizar_status_animal(aid_s, novo_sa)
                            registrar_auditoria(u["id"], "status_animal", "animais", aid_s, novo_sa)
                            st.success(f"Status: {novo_sa}")
                            st.rerun()

    # ============================================================
    # WORKSPACE DO LOTE
    # ============================================================
