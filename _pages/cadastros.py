# pages/cadastros.py -- Telas: Cadastrar Lote, Cadastrar Animal, Registrar Pesagem, Registrar Ocorrencia, Registrar Morte, Importar CSV, Editar Lote, Editar Animal, Editar Pesagens, Gerenciar Ocorrencias, Transferir Animal, Status do Lote

import streamlit as st
try:
    from ux_helpers import (aplicar_css_global, fmt_brl, fmt_data,
                             safe_bar_chart, safe_line_chart,
                             toast_ok, toast_erro, empty_state)
except ImportError:
    def aplicar_css_global(): pass
    def fmt_brl(v):
        try:
            v=float(v or 0); i=int(abs(v)); c=round((abs(v)-i)*100)
            s=f"{i:,}".replace(",","."); r=f"R$ {s},{c:02d}"
            return f"-{r}" if v<0 else r
        except: return "R$ 0,00"
    def fmt_data(d):
        try:
            p=str(d)[:10].split("-")
            m={"01":"jan","02":"fev","03":"mar","04":"abr","05":"mai",
               "06":"jun","07":"jul","08":"ago","09":"set","10":"out",
               "11":"nov","12":"dez"}
            return f"{p[2]}/{m.get(p[1],p[1])}/{p[0]}"
        except: return str(d)
    def safe_bar_chart(df, **k):
        import streamlit as _st
        _st.caption("Gráfico indisponível.")
    def safe_line_chart(df, **k):
        import streamlit as _st
        _st.caption("Gráfico indisponível.")
    def toast_ok(m): import streamlit as _st; _st.success(f"✅ {m}")
    def toast_erro(m): import streamlit as _st; _st.error(f"❌ {m}")
    def empty_state(m, **k): import streamlit as _st; _st.info(m)
try:
    from ux_helpers import (aplicar_css_global, toast_ok, toast_erro,
                            toast_aviso, empty_state, erro_com_acao,
                            fmt_brl, fmt_data, fmt_data_hora,
                            tabela_paginada, paginar_dataframe)
except ImportError:
    def aplicar_css_global(): pass
    def toast_ok(m): st.success(m)
    def toast_erro(m): st.error(m)
    def toast_aviso(m): st.warning(m)
    def empty_state(t, d, **k): st.info(f"{t} — {d}"); return False
    def erro_com_acao(e, a=""): st.error(str(e))
    def fmt_brl(v):
        try:
            v=float(v); i=int(abs(v)); c=round((abs(v)-i)*100)
            s=f"{i:,}".replace(",","."); r=f"R$ {s},{c:02d}"
            return f"-{r}" if v<0 else r
        except: return "R$ 0,00"
    def fmt_data(d):
        m={"01":"jan","02":"fev","03":"mar","04":"abr","05":"mai","06":"jun",
           "07":"jul","08":"ago","09":"set","10":"out","11":"nov","12":"dez"}
        try: d=str(d)[:10]; p=d.split("-"); return f"{p[2]} {m.get(p[1],p[1])} {p[0]}"
        except: return str(d)
    def fmt_data_hora(d): return fmt_data(d)
    def tabela_paginada(df, key, **kw):
        import streamlit as st
        if df is not None and not (hasattr(df,"empty") and df.empty):
            st.dataframe(df, hide_index=True)
    def paginar_dataframe(df, key, **kw): return df
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
    sel_fazenda_vet,
    listar_lotes_vet_filtrado,
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
            salvar = st.form_submit_button("Salvar Lote", use_container_width=True, type="primary")
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
                toast_ok("Lote **{nome}** criado!")
    with c2:
        st.markdown("#### Dicas")
        st.info("Use um nome facil de identificar, ex: Nelore Jan/25")
        st.info("Qtd recebida pode ser menor que a comprada se houve perdas no transporte")
        if qtd_comp > 0 and preco_anim > 0:
            st.metric("Custo total estimado", fmt_brl(preco_anim*qtd_comp))

    # ============================================================
    # CADASTRAR ANIMAL
    # ============================================================


def page_cadastrar_animal(u):
    # Seletor de fazenda para veterinario (aparece antes de tudo)
    hdr("Cadastrar Animal", "Novo Animal", "Vincule um animal a um lote")
    if is_vet():
        sel_fazenda_vet(key="vet_faz_cad_anim")

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
                salvar = st.form_submit_button("Cadastrar Animal", use_container_width=True, type="primary")
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
                        aid = adicionar_animal(
                            ident, idade, lote_id,
                            sexo=sexo, peso_entrada=p_ent, peso_alvo=p_alvo
                        )
                        registrar_auditoria(u["id"], "cadastro_animal", "animais", aid, ident)
                        limpar_cache()
                        toast_ok(f"**{ident}** cadastrado no lote **{lote[1]}**!")
                        st.rerun()

    # ============================================================
    # REGISTRAR PESAGEM
    # ============================================================


def page_registrar_pesagem(u):
    hdr("Registrar Pesagem", "Novo Peso", "Registre o peso atual de um animal")
    if is_vet():
        sel_fazenda_vet(key="vet_faz_reg_pes")
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
                salvar = st.form_submit_button("Salvar Pesagem", use_container_width=True, type="primary")
            if salvar:
                if peso <= 0:    st.error("Peso invalido")
                elif peso > 1000: st.error("Peso muito alto")
                else:
                    adicionar_pesagem(animal_id, peso, str(data_p))
                    registrar_auditoria(u["id"], "pesagem", "pesagens", animal_id, f"{peso}kg em {data_p}")
                    toast_ok(f"Pesagem de **{peso:.1f} kg** registrada!")
                    st.rerun()

    # ============================================================
    # REGISTRAR OCORRENCIA
    # ============================================================


def page_registrar_ocorrencia(u):
    hdr("Registrar Ocorrencia", "Nova Ocorrencia", "Doencas, lesoes e medicacoes")
    if is_vet():
        sel_fazenda_vet(key="vet_faz_reg_oc")
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
                salvar = st.form_submit_button("Salvar Ocorrencia", use_container_width=True, type="primary")
            if salvar:
                oid = adicionar_ocorrencia(animal_id, str(data_oc), tipo_oc, desc_oc, grav_oc, custo_oc, dias_oc, stat_oc)
                registrar_auditoria(u["id"], "ocorrencia", "ocorrencias", oid, f"{tipo_oc}/{grav_oc}")
                toast_ok("Ocorrência registrada!")
                st.rerun()

    # ============================================================
    # REGISTRAR MORTE
    # ============================================================


def page_registrar_morte(u):
    hdr("Registrar Morte", "Baixa de Animal", "Registre a morte e retire o animal do lote")
    tab1,tab2 = st.tabs(["Registrar", "Historico"])
    if is_vet():
        sel_fazenda_vet(key="vet_faz_morte")

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
                    salvar = st.form_submit_button("Registrar Morte", use_container_width=True, type="primary")
                if salvar:
                    registrar_morte(dict_am[anim_sel_m], str(data_m), causa_m, desc_m, custo_m)
                    registrar_auditoria(u["id"], "morte_animal", "animais", dict_am[anim_sel_m], f"{anim_sel_m} - {causa_m}")
                    toast_ok("Morte registrada. Animal removido do lote.")
                    st.rerun()
    with tab2:
        lotes = lotes
        if lotes:
            dict_l2 = {"Todos": None, **{f"{l[1]} (ID {l[0]})": l[0] for l in lotes}}
            filtro_m = st.selectbox("Filtrar por lote", list(dict_l2.keys()), key="mort_hist")
            morts = listar_mortalidade(dict_l2[filtro_m])
            if morts:
                df_m = pd.DataFrame(morts, columns=["ID","Animal ID","Animal","Data","Causa","Descricao","Custo Perda"])
                st.dataframe(df_m, use_container_width=True)
                st.metric("Custo total perdas", fmt_brl(sum(m[6] for m in morts if m[6])))
            else:
                st.info("Nenhuma morte registrada.")

    # ============================================================
    # IMPORTAR CSV
    # ============================================================


def page_importar_csv(u):
    hdr("Importar CSV", "Importacao em Lote", "Importe pesagens e animais via planilha CSV")
    if is_vet():
        sel_fazenda_vet(key="vet_faz_imp_csv")

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
                    toast_ok("Lote '{nome_nl}' criado!")
                    st.rerun()
                else: st.error("Informe o nome.")
        lotes = lotes
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
                toast_ok(f"Importadas: {res['importados']} | Animais criados: {res['animais_criados']} | Erros: {res['erros']}")
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
                    toast_ok("Importados: {res2['importados']} | Erros: {res2['erros']}")
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
                st.markdown(f"Lote **{nome_s}**: {n_s} animais ativos")
            toast_ok("Contagens atualizadas!")
            st.rerun()

    if is_vet():
        sel_fazenda_vet(key="vet_faz_edit_lote")

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
                    preco_e    = st.number_input("Preco por animal (R$)", 0.0, step=50.0,
                                          value=float(lote[9] or 0.0))
                salvar_e = st.form_submit_button("Salvar alteracoes", type="primary", use_container_width=True)
            if salvar_e:
                if not nome_e:
                    st.error("Informe o nome do lote.")
                else:
                    # qtd_recebida e sempre recalculada pelos animais ativos reais
                    atualizar_lote(lote_id, nome_e, desc_e, str(data_e), qtd_comp_e, ativos_reais, transp_e, preco_e)
                    registrar_auditoria(u["id"], "editar_lote", "lotes", lote_id, nome_e)
                    limpar_cache()
                    toast_ok(f"Lote **{nome_e}** atualizado! Animais ativos: {ativos_reais}")
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
                        toast_ok("Lote excluido com sucesso.")
                        st.rerun()

    # ============================================================
    # EDITAR ANIMAL
    # ============================================================


def page_editar_animal(u):
    hdr("Editar Animal", "Editar / Excluir Animal", "Altere dados ou exclua animais em massa")
    if is_vet():
        sel_fazenda_vet(key="vet_faz_edit_anim")

    lotes = listar_lotes_usuario()
    if not lotes:
        st.warning("Nenhum lote cadastrado.")
        return

    dict_l  = {f"{l[1]} (ID {l[0]})": l[0] for l in lotes}
    lote_sel = st.selectbox("Selecionar lote", list(dict_l.keys()), key="ea_lote")
    lote_id  = dict_l[lote_sel]

    animais = listar_animais_por_lote(lote_id, incluir_inativos=True)
    if not animais:
        st.warning("Nenhum animal neste lote.")
        return

    tab_editar, tab_excluir = st.tabs(["Editar animal", "Excluir animais"])

    # ── ABA 1: Editar animal individual ──────────────────────────────────────
    with tab_editar:
        dict_a   = {f"{a[1]} (ID {a[0]})": a[0] for a in animais}
        anim_sel = st.selectbox("Animal", list(dict_a.keys()), key="ea_anim")
        anim_id  = dict_a[anim_sel]

        # obter_animal retorna tupla: (id,ident,idade,lote_id,sexo,raca,peso_ent,peso_alvo,obs,foto)
        dados = obter_animal(anim_id)
        if dados:
            _d_ident = dados[1] or ""
            _d_idade = int(dados[2] or 0)
            _d_sexo  = dados[4] or "indefinido"
            _d_raca  = dados[5] or ""
            _d_pe    = float(dados[6] or 0)
            _d_palvo = float(dados[7] or 0)
            _d_obs   = dados[8] or ""

            with st.form("form_edit_anim"):
                f1, f2 = st.columns(2)
                with f1:
                    n_ident = st.text_input("Identificacao (brinco)", value=_d_ident)
                    n_idade = st.number_input("Idade (meses)", 0, 300, _d_idade)
                    n_raca  = st.text_input("Raca", value=_d_raca)
                with f2:
                    _sexos  = ["indefinido","macho","femea"]
                    _si     = _sexos.index(_d_sexo) if _d_sexo in _sexos else 0
                    n_sexo  = st.selectbox("Sexo", _sexos, index=_si)
                    n_pe    = st.number_input("Peso de entrada (kg)", 0.0, value=_d_pe)
                    n_palvo = st.number_input("Peso alvo (kg)", 0.0, value=_d_palvo)
                n_obs = st.text_area("Observacoes", value=_d_obs)

                # Um form deve ter exatamente um submit button principal
                _salvar = st.form_submit_button("Salvar alteracoes", type="primary")

            # Acoes fora do form para evitar conflito
            if _salvar:
                atualizar_animal(anim_id, n_ident, n_idade, n_raca,
                                n_sexo, n_pe, n_palvo, n_obs)
                registrar_auditoria(u["id"], "editar_animal",
                                   "animais", anim_id, n_ident)
                toast_ok("Animal {n_ident} atualizado!")
                limpar_cache(); st.rerun()

            st.divider()
            st.caption("Zona de perigo")
            _key_conf = f"confirm_excluir_{anim_id}"
            if not st.session_state.get(_key_conf):
                if st.button("🗑️ Excluir este animal", type="secondary",
                             key="excluir_1_anim"):
                    st.session_state[_key_conf] = True
                    st.rerun()
            else:
                st.warning(f"⚠️ Confirma exclusão de **{_d_ident}**? Esta ação não pode ser desfeita.")
                c_sim, c_nao = st.columns(2)
                if c_sim.button("✅ Sim, excluir", type="primary", key="excluir_confirm_sim"):
                    excluir_animal(anim_id)
                    registrar_auditoria(u["id"], "excluir_animal",
                                       "animais", anim_id, "excluido")
                    st.session_state.pop(_key_conf, None)
                    toast_ok(f"Animal {_d_ident} excluído.")
                    limpar_cache(); st.rerun()
                if c_nao.button("❌ Cancelar", key="excluir_confirm_nao"):
                    st.session_state.pop(_key_conf, None)
                    st.rerun()

    # ── ABA 2: Excluir em massa com data_editor ──────────────────────────────
    with tab_excluir:
        st.subheader("Excluir animais em massa")
        st.caption("Marque a coluna Excluir nos animais desejados e clique em confirmar.")

        _busca_ex = st.text_input(
            "Filtrar por brinco",
            placeholder="Digite parte do brinco...",
            key="ex_busca"
        )
        _anim_filtrados = [
            a for a in animais
            if _busca_ex.lower() in str(a[1]).lower()
        ] if _busca_ex else animais

        if not _anim_filtrados:
            st.info("Nenhum animal encontrado.")
        else:
            import pandas as pd

            # Montar DataFrame para edicao
            _df_ex = pd.DataFrame([
                {
                    "Excluir": False,
                    "ID":      a[0],
                    "Brinco":  a[1],
                    "Idade":   f"{a[2]} meses",
                }
                for a in _anim_filtrados
            ])

            # Botoes rapidos de selecao
            _bc1, _bc2, _bc3 = st.columns(3)
            if _bc1.button("Selecionar todos", key="ex_sel_todos",
                           use_container_width=True):
                st.session_state["ex_todos_flag"] = True
            if _bc2.button("Desmarcar todos", key="ex_desel_todos",
                           use_container_width=True):
                st.session_state["ex_todos_flag"] = False
            _bc3.caption(f"{len(_anim_filtrados)} animais no lote")

            # Aplicar selecao rapida
            if st.session_state.get("ex_todos_flag") is True:
                _df_ex["Excluir"] = True
            elif st.session_state.get("ex_todos_flag") is False:
                _df_ex["Excluir"] = False

            # Tabela editavel
            _df_editado = st.data_editor(
                _df_ex,
                column_config={
                    "Excluir": st.column_config.CheckboxColumn(
                        "Excluir", help="Marque para excluir", default=False
                    ),
                    "ID":     st.column_config.NumberColumn("ID",  disabled=True),
                    "Brinco": st.column_config.TextColumn("Brinco", disabled=True),
                    "Idade":  st.column_config.TextColumn("Idade",  disabled=True),
                },
                hide_index=True,
                use_container_width=True,
                key="ex_data_editor"
            )

            _selecionados = _df_editado[_df_editado["Excluir"] == True]
            _n_sel = len(_selecionados)

            st.divider()
            if _n_sel == 0:
                st.info("Marque animais na coluna Excluir para continuar.")
            else:
                st.warning(f"**{_n_sel} animal(is) selecionado(s)** para exclusao definitiva.")
                if st.button(
                    f"Confirmar exclusao de {_n_sel} animal(is)",
                    type="primary", key="ex_confirmar"
                ):
                    _n_ok = 0
                    for _, _row in _selecionados.iterrows():
                        try:
                            excluir_animal(int(_row["ID"]))
                            registrar_auditoria(
                                u["id"], "excluir_animal_massa",
                                "animais", int(_row["ID"]),
                                f"excluido: {_row['Brinco']}"
                            )
                            _n_ok += 1
                        except Exception as _e:
                            pass  # silenced
                    st.session_state.pop("ex_todos_flag", None)
                    limpar_cache()
                    st.success(f"{_n_ok} animal(is) excluido(s) com sucesso!")
                    st.rerun()


def page_editar_pesagens(u):
    hdr("Editar Pesagens", "Corrigir Pesagens", "Edite ou exclua pesagens incorretas")
    if is_vet():
        sel_fazenda_vet(key="vet_faz_edit_pes")

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
                empty_state("Sem pesagens registradas", "Registre pesagens para acompanhar o desenvolvimento do rebanho.", icone="⚖️")
            else:
                # Tabela visual
                df_ps = pd.DataFrame(pesagens, columns=["ID","Animal ID","Peso (kg)","Data"])
                if modo == "Todas do lote" and "nomes_map" in dir():
                    df_ps["Animal"] = df_ps["Animal ID"].map(nomes_map)
                    df_ps = df_ps[["ID","Animal","Peso (kg)","Data"]]
                df_ps["Data"] = pd.to_datetime(df_ps["Data"]).dt
                st.dataframe(df_ps, use_container_width=True)

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
                        if st.form_submit_button("Salvar correcao", type="primary", use_container_width=True):
                            if peso_novo <= 0:       st.error("Peso invalido.")
                            elif peso_novo > 1000:   st.error("Peso muito alto.")
                            else:
                                atualizar_pesagem(pes_id, peso_novo, str(data_nova))
                                registrar_auditoria(u["id"], "editar_pesagem", "pesagens", pes_id,
                                                    f"{peso_novo}kg em {data_nova}")
                                toast_ok("Pesagem corrigida!")
                                st.rerun()

                with tab_del_p:
                    if pes_cur:
                        st.warning(f"Excluir pesagem de {pes_cur[2]:.1f} kg registrada em {pd.to_datetime(pes_cur[3]).strftime('%d/%m/%Y')}?")
                    confirma_p = st.checkbox("Confirmo a exclusao desta pesagem")
                    if confirma_p:
                        if st.button("Excluir pesagem", type="primary"):
                            excluir_pesagem(pes_id)
                            registrar_auditoria(u["id"], "excluir_pesagem", "pesagens", pes_id, "excluido")
                            toast_ok("Pesagem excluída.")
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
        st.info("Nenhum tratamento com prazo vencido.")

    st.divider()

    # ── Selecao ────────────────────────────────────────────────────────
    if is_vet():
        sel_fazenda_vet(key="vet_faz_ger_oc")

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
                salvar_oc = st.form_submit_button("Salvar alteracoes", type="primary", use_container_width=True)

            if salvar_oc:
                atualizar_ocorrencia(oc_id, tipo_oe, desc_oe, grav_oe, custo_oe, dias_oe, stat_oe, str(data_oe))
                registrar_auditoria(u["id"], "editar_ocorrencia", "ocorrencias", oc_id,
                                    f"{tipo_oe}/{grav_oe}/{stat_oe}")
                if stat_oe == "Resolvido" and stat_cur == "Em tratamento":
                    toast_ok("Tratamento encerrado! Ocorrencia marcada como Resolvida.")
                else:
                    toast_ok("Ocorrência atualizada!")
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
                        toast_ok("Ocorrência excluída.")
                        st.rerun()


    # ============================================================
    # TRANSFERIR ANIMAL
    # ============================================================


def page_transferir_animal(u):
    hdr("Transferir Animal", "Transferencia entre Lotes", "Mova animais mantendo o historico completo")

    if is_vet():
        sel_fazenda_vet(key="vet_faz_transf")

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
        if st.button("Transferir animal", type="primary", use_container_width=True):
            res = transferir_animal(animal_id, lote_dest_id, motivo, u["id"])
            if res["ok"]:
                registrar_auditoria(u["id"], "transferir_animal", "animais", animal_id,
                                    f"{lote_orig_s} -> {lote_dest_s}")
                toast_ok(f"Animal transferido com sucesso!")
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
            if st.button(f"Transferir {len(selecionados)} animal(is)", type="primary", use_container_width=True):
                ok_count = 0
                for nome in selecionados:
                    aid_m = int(nome.split("ID ")[1].rstrip(")"))
                    res_m = transferir_animal(aid_m, lote_dest_id, motivo_m, u["id"])
                    if res_m["ok"]:
                        ok_count += 1
                registrar_auditoria(u["id"], "transferir_massa", "animais", lote_orig_id,
                                    f"{ok_count} animais -> {lote_dest_s}")
                toast_ok(f"{ok_count} animal(is) transferido(s)!")
                if ok_count > 0:
                    pass  # transferencia ok
                st.rerun()

    with tab_historico:
        movs = listar_movimentacoes(lote_id=lote_orig_id)
        if movs:
            df_mov = pd.DataFrame(movs,
                columns=["ID", "Animal ID", "Animal", "Lote Origem", "Lote Destino", "Data", "Motivo"])
            st.dataframe(df_mov[["Animal", "Lote Origem", "Lote Destino", "Data", "Motivo"]],
                         use_container_width=True)
        else:
            st.info("Nenhuma transferencia registrada para este lote.")

    # ============================================================
    # STATUS DO LOTE
    # ============================================================


def page_status_do_lote(u):
    hdr("Status do Lote", "Gerenciar Status", "Atualize o status dos seus lotes e animais")

    if is_vet():
        sel_fazenda_vet(key="vet_faz_status")

    lotes = listar_lotes_usuario()
    if not lotes:
        st.warning("Nenhum lote cadastrado.")
        st.stop()

    tab_lotes, tab_animais, tab_vendidos = st.tabs([
        "Status dos Lotes", "Status dos Animais", "Vendidos / Encerrados"
    ])

    with tab_lotes:
        st.subheader("Status atual dos lotes")

        COR_LOTE = {
            "ATIVO":      ("green",  "Operando normalmente"),
            "CRITICO":    ("red",    "Requer atencao imediata"),
            "QUARENTENA": ("orange", "Animais em isolamento"),
            "ENCERRADO":  ("gray",   "Lote finalizado"),
            "VENDIDO":    ("blue",   "Lote comercializado"),
        }

        _lotes_raw = lotes
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
                        toast_ok(f"Status atualizado para {novo_status}")
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
                            toast_ok(f"Status: {novo_sa}")
                            st.rerun()

    # ============================================================
    # WORKSPACE DO LOTE
    # ============================================================


    with tab_vendidos:
        st.subheader("Animais Vendidos e Lotes Encerrados")
        st.caption(
            "Histórico completo de animais marcados como VENDIDO "
            "e lotes encerrados."
        )

        from database import listar_animais_por_lote_status, listar_lotes_historico

        oid_v = owner_id()

        # Lotes encerrados
        lotes_enc = listar_lotes_historico(oid_v or u["id"])
        if lotes_enc:
            st.markdown("**Lotes encerrados**")
            import pandas as pd
            df_enc = pd.DataFrame([{
                "Lote":      l[1],
                "Entrada":   fmt_data(l[3]),
                "Encerrado": fmt_data(l[10])
                              if l[10] and str(l[10]) not in ("","None") else "-",
                "Animais comprados": l[4],
            } for l in lotes_enc])
            st.dataframe(df_enc, hide_index=True, use_container_width=True)
        else:
            empty_state("Nenhum lote encontrado", "Crie um lote para organizar seus animais.", icone="🌾")

        st.divider()

        # Animais vendidos por lote
        st.markdown("**Animais vendidos**")
        # Mostrar todos os lotes (ativos + encerrados)
        todos_lotes = lotes + lotes_enc if lotes_enc else lotes
        for l in todos_lotes[:20]:
            vendidos = listar_animais_por_lote_status(l[0], status='VENDIDO')
            if vendidos:
                with st.expander(
                    f"🏷 {l[1]} — {len(vendidos)} animal(is) vendido(s)"
                ):
                    for av in vendidos:
                        st.caption(
                            f"• {av[1]} | {av[2] or '-'} | {av[3] or '-'} "
                            f"| Status: VENDIDO"
                        )
