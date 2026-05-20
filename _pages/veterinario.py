# _pages/veterinario.py -- Telas exclusivas do perfil veterinario
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database import *
from database import _conexao, _ph, _usar_postgres
from ui import (
    card_kpi, card_kpi_row, alerta, badge,
    badge_status_animal, badge_status_lote, badge_gravidade,
    card_animal, insight_card,
)
from rules import (
    is_admin, is_vet, is_fazendeiro, owner_id,
    usuario_atual, sel_fazenda_vet, limpar_cache
)


# hdr e definida em app.py e injetada no namespace — definir localmente
def hdr(titulo, subtitulo="", descricao=""):
    st.markdown(f"## {titulo}")
    if subtitulo and subtitulo != titulo:
        st.caption(descricao or subtitulo)
    elif descricao:
        st.caption(descricao)
    st.divider()


def _requer_vet():
    """Garante que apenas vet acessa a tela."""
    if not is_vet():
        st.error("Acesso restrito a veterinarios.")
        st.stop()


def _crmv_atual(u):
    """Retorna CRMV do vet logado, mostra aviso se nao cadastrou."""
    crmv = obter_crmv_usuario(u["id"])
    if not crmv:
        st.warning(
            "Voce ainda nao cadastrou seu CRMV. "
            "Acesse Veterinario > Meu CRMV para registrar."
        )
    return crmv


def _fmt_dt(d):
    """Formata YYYY-MM-DD para DD/MM/AAAA."""
    if not d or str(d) in ("None", ""):
        return "-"
    try:
        return "/".join(reversed(str(d)[:10].split("-")))
    except Exception:
        return str(d)


# ════════════════════════════════════════════════════════════════════════════
# TELA 1: MEU CRMV - Cadastro do CRMV
# ════════════════════════════════════════════════════════════════════════════
def page_meu_crmv(u):
    _requer_vet()
    hdr("Meu CRMV", "Registro Profissional",
        "CRMV usado em receituarios e relatorios tecnicos")

    crmv_atual = obter_crmv_usuario(u["id"])

    if crmv_atual:
        st.success(f"CRMV cadastrado: **{crmv_atual}**")
    else:
        st.info("Nenhum CRMV cadastrado ainda.")

    with st.form("form_crmv"):
        novo_crmv = st.text_input(
            "CRMV (numero e UF)",
            value=crmv_atual,
            placeholder="Ex: CRMV-SP 12345",
            help="Sera usado em todos os documentos emitidos por voce"
        )
        if st.form_submit_button("Salvar CRMV", type="primary"):
            if atualizar_crmv(u["id"], novo_crmv):
                st.success("CRMV atualizado!")
                st.rerun()
            else:
                st.error("Erro ao atualizar CRMV.")


# ════════════════════════════════════════════════════════════════════════════
# TELA 2: RECEITUARIO DIGITAL
# ════════════════════════════════════════════════════════════════════════════
def page_receituario(u):
    _requer_vet()
    hdr("Receituario Digital", "Emissao de Receitas",
        "Receitas com validade legal e assinatura digital")

    crmv = _crmv_atual(u)

    # Seletor de fazenda
    sel_fazenda_vet(key="vet_faz_recituario")
    foid = st.session_state.get("_vet_foid")

    if not foid:
        st.warning("Selecione uma fazenda.")
        return

    t1, t2 = st.tabs(["Emitir Receita", "Historico"])

    with t1:
        # Buscar animais/lotes da fazenda
        from database import listar_lotes
        lotes_faz = listar_lotes(owner_id=foid)
        if not lotes_faz:
            st.warning("Nenhum lote nesta fazenda.")
            return

        alvo = st.radio("Aplicar em:", ["Lote inteiro", "Animal especifico"],
                       horizontal=True, key="rec_alvo")
        lote_id_rec  = None
        animal_id_rec = None

        if alvo == "Lote inteiro":
            dict_l = {f"{l[1]}": l[0] for l in lotes_faz}
            lote_sel = st.selectbox("Lote", list(dict_l.keys()), key="rec_lote")
            lote_id_rec = dict_l[lote_sel]
        else:
            dict_l = {f"{l[1]}": l[0] for l in lotes_faz}
            lote_sel = st.selectbox("Lote do animal", list(dict_l.keys()),
                                   key="rec_lote_anim")
            animais_l = listar_animais_por_lote(dict_l[lote_sel])
            if animais_l:
                dict_a = {f"{a[1]}": a[0] for a in animais_l}
                an_sel = st.selectbox("Animal", list(dict_a.keys()),
                                     key="rec_animal")
                animal_id_rec = dict_a[an_sel]

        with st.form("form_emit_receita"):
            c1, c2 = st.columns(2)
            with c1:
                medicamento = st.text_input("Medicamento *",
                                            placeholder="Ex: Oxitetraciclina LA")
                dose = st.text_input("Dose *",
                                    placeholder="Ex: 1mL para cada 10kg")
                via = st.selectbox("Via de administracao",
                                  ["Intramuscular","Subcutanea","Oral",
                                   "Intravenosa","Topica"])
            with c2:
                duracao = st.text_input("Duracao do tratamento",
                                       placeholder="Ex: 3 dias / dose unica")
                carencia = st.number_input("Carencia para abate (dias)",
                                          min_value=0, value=0, step=1)
                obs = st.text_area("Observacoes", height=80)

            if st.form_submit_button("Emitir Receita", type="primary"):
                if not medicamento or not dose:
                    st.error("Preencha medicamento e dose.")
                else:
                    rid = adicionar_receita(
                        vet_id=u["id"], fazenda_owner_id=foid,
                        medicamento=medicamento, dose=dose, via=via,
                        duracao=duracao or "", animal_id=animal_id_rec,
                        lote_id=lote_id_rec, carencia_dias=int(carencia),
                        observacoes=obs or "", crmv=crmv
                    )
                    # Se carencia > 0, registrar para os animais
                    if carencia and animal_id_rec:
                        adicionar_carencia(animal_id_rec, medicamento,
                                          str(date.today()), int(carencia))
                    elif carencia and lote_id_rec:
                        for a in listar_animais_por_lote(lote_id_rec):
                            adicionar_carencia(a[0], medicamento,
                                              str(date.today()), int(carencia))
                    st.success(f"Receita #{rid} emitida com sucesso!")
                    st.rerun()

    with t2:
        receitas = listar_receitas(vet_id=u["id"])
        if not receitas:
            st.info("Nenhuma receita emitida ainda.")
        else:
            st.caption(f"{len(receitas)} receita(s) emitida(s)")
            for r in receitas[:30]:
                (rid, _, _, an_id, lt_id, dt_em, med, dose, via, dur,
                 carenc, obs_r, crmv_r) = r
                with st.expander(f"#{rid} - {med} ({_fmt_dt(dt_em)})"):
                    st.markdown(f"**Medicamento:** {med}")
                    st.markdown(f"**Dose:** {dose}")
                    st.markdown(f"**Via:** {via}")
                    st.markdown(f"**Duracao:** {dur}")
                    if carenc:
                        st.markdown(f"**Carencia:** {carenc} dias")
                    if obs_r:
                        st.caption(f"Obs: {obs_r}")
                    st.caption(f"CRMV: {crmv_r or '-'}")


# ════════════════════════════════════════════════════════════════════════════
# TELA 3: PROTOCOLOS SANITARIOS
# ════════════════════════════════════════════════════════════════════════════
def page_protocolos(u):
    _requer_vet()
    hdr("Protocolos Sanitarios", "Protocolos de Manejo",
        "Sequencias reutilizaveis de vacinas e medicacoes")

    t1, t2, t3 = st.tabs(["Meus Protocolos", "Criar Protocolo", "Aplicar em Lote"])

    with t1:
        protos = listar_protocolos(u["id"])
        if not protos:
            st.info("Nenhum protocolo cadastrado. Crie um na aba 'Criar Protocolo'.")
        else:
            for pr in protos:
                pid, _, nome_p, desc_p, cat_p, criado = pr
                with st.expander(f"📋 {nome_p} ({cat_p})"):
                    if desc_p: st.caption(desc_p)
                    itens = listar_itens_protocolo(pid)
                    if itens:
                        df_i = pd.DataFrame(itens, columns=[
                            "ID","ProtID","Ordem","Tipo","Nome",
                            "Dia","Obs"
                        ])
                        st.dataframe(
                            df_i[["Dia","Tipo","Nome","Obs"]].rename(
                                columns={"Dia":"Dia (offset)"}
                            ),
                            use_container_width=True, hide_index=True
                        )
                    else:
                        st.caption("Nenhum item neste protocolo.")

    with t2:
        with st.form("form_criar_proto"):
            nome_proto = st.text_input("Nome do protocolo *",
                                      placeholder="Ex: Engorda Nelore 18 meses")
            desc_proto = st.text_area("Descricao", height=60)
            cat_proto  = st.selectbox("Categoria",
                ["geral","engorda","cria","leite","reproducao","sanitario"])

            st.markdown("**Itens do protocolo** (sera adicionado apos criar)")

            if st.form_submit_button("Criar Protocolo", type="primary"):
                if not nome_proto:
                    st.error("Informe o nome.")
                else:
                    pid = adicionar_protocolo(u["id"], nome_proto,
                                             desc_proto or "", cat_proto)
                    st.session_state["_proto_recem_criado"] = pid
                    st.success(f"Protocolo criado! Adicione itens abaixo.")
                    st.rerun()

        # Se acabou de criar, mostrar form para adicionar itens
        pid_novo = st.session_state.get("_proto_recem_criado")
        if pid_novo:
            st.divider()
            st.subheader(f"Adicionar item ao protocolo #{pid_novo}")
            with st.form("form_add_item"):
                col1, col2 = st.columns(2)
                with col1:
                    tipo_i = st.selectbox("Tipo", ["vacina","medicacao","exame"])
                    nome_i = st.text_input("Nome do item *",
                                          placeholder="Ex: Aftosa, Vermifugacao")
                with col2:
                    dia_i  = st.number_input("Dia (offset do inicio)",
                                            min_value=0, value=0)
                    obs_i  = st.text_input("Observacao")
                if st.form_submit_button("Adicionar Item"):
                    if not nome_i:
                        st.error("Informe o nome.")
                    else:
                        n_atual = len(listar_itens_protocolo(pid_novo))
                        adicionar_item_protocolo(
                            pid_novo, n_atual + 1, tipo_i,
                            nome_i, int(dia_i), obs_i or ""
                        )
                        st.success(f"Item '{nome_i}' adicionado!")
                        st.rerun()

            if st.button("Finalizar protocolo"):
                st.session_state.pop("_proto_recem_criado", None)
                st.rerun()

    with t3:
        sel_fazenda_vet(key="vet_faz_aplic_proto")
        foid_ap = st.session_state.get("_vet_foid")
        if not foid_ap:
            st.warning("Selecione uma fazenda.")
            return

        protos2 = listar_protocolos(u["id"])
        if not protos2:
            st.info("Crie um protocolo primeiro.")
            return

        from database import listar_lotes
        lotes_ap = listar_lotes(owner_id=foid_ap)
        if not lotes_ap:
            st.warning("Nenhum lote nesta fazenda.")
            return

        with st.form("form_aplic_proto"):
            dict_p = {f"{p[2]}": p[0] for p in protos2}
            proto_sel = st.selectbox("Protocolo", list(dict_p.keys()))
            dict_la = {f"{l[1]}": l[0] for l in lotes_ap}
            lote_ap = st.selectbox("Lote de destino", list(dict_la.keys()))
            data_ini = st.date_input("Data de inicio (dia 0)")

            if st.form_submit_button("Aplicar Protocolo", type="primary"):
                n = aplicar_protocolo_no_lote(
                    dict_p[proto_sel], dict_la[lote_ap],
                    str(data_ini), u["id"]
                )
                st.success(f"{n} agendamento(s) criado(s)! "
                          f"Veja em Calendario Sanitario.")


# ════════════════════════════════════════════════════════════════════════════
# TELA 4: DIAGNOSTICO CLINICO COM IA
# ════════════════════════════════════════════════════════════════════════════
def page_diagnostico_ia(u):
    _requer_vet()
    hdr("Diagnostico Clinico IA", "Analise com IA",
        "Descreva os sintomas e receba sugestao de diagnostico")

    st.info(
        "Esta ferramenta usa IA para sugerir diagnosticos diferenciais. "
        "**Nao substitui exame clinico presencial.**"
    )

    with st.form("form_diag_ia"):
        c1, c2 = st.columns(2)
        with c1:
            especie = st.selectbox("Especie",
                ["Bovino","Bufalino","Equino","Ovino","Caprino"])
            idade_anim = st.text_input("Idade do animal",
                                      placeholder="Ex: 18 meses")
            peso_anim  = st.text_input("Peso aproximado",
                                      placeholder="Ex: 380 kg")
        with c2:
            temp = st.text_input("Temperatura",
                                placeholder="Ex: 39.5 graus C")
            tempo_sint = st.text_input("Tempo de sintomas",
                                      placeholder="Ex: 3 dias")
            ja_tratado = st.text_input("Ja foi tratado com algo?")

        sintomas = st.text_area(
            "Descreva os sintomas observados *",
            height=150,
            placeholder="Ex: Apatia, perda de apetite, salivacao excessiva, "
                       "ulceras na lingua, claudicacao..."
        )
        contexto = st.text_area(
            "Contexto epidemiologico (opcional)",
            height=80,
            placeholder="Outros animais afetados, mudancas recentes, "
                       "vacinas, alimentacao..."
        )

        if st.form_submit_button("Analisar com IA", type="primary"):
            if not sintomas:
                st.error("Descreva os sintomas para analisar.")
            else:
                with st.spinner("Analisando com IA..."):
                    try:
                        import anthropic, os
                        prompt = f"""Voce e um veterinario consultor experiente.
Analise o caso clinico abaixo e forneca:

1. **3 a 5 diagnosticos diferenciais** (do mais ao menos provavel)
2. **Exames complementares recomendados** para confirmar
3. **Tratamento inicial sugerido** (com cautela)
4. **Sinais de alerta** que indicariam piora
5. **Medidas de manejo** para o lote/rebanho

DADOS DO CASO:
- Especie: {especie}
- Idade: {idade_anim or 'nao informada'}
- Peso: {peso_anim or 'nao informado'}
- Temperatura: {temp or 'nao informada'}
- Tempo de sintomas: {tempo_sint or 'nao informado'}
- Tratamento previo: {ja_tratado or 'nenhum'}

SINTOMAS OBSERVADOS:
{sintomas}

CONTEXTO:
{contexto or 'sem informacoes adicionais'}

Use linguagem tecnica clara. Use markdown. Sempre lembre que isto e
uma sugestao e nao substitui exame clinico presencial."""

                        client = anthropic.Anthropic(
                            api_key=st.secrets.get("ANTHROPIC_API_KEY",
                                                  os.environ.get("ANTHROPIC_API_KEY",""))
                        )
                        msg = client.messages.create(
                            model="claude-sonnet-4-20250514",
                            max_tokens=2000,
                            messages=[{"role":"user","content":prompt}]
                        )
                        resposta = msg.content[0].text
                        st.divider()
                        st.subheader("Analise Clinica IA")
                        st.markdown(resposta)
                        st.caption("⚠ Esta analise e auxiliar. "
                                   "Confirme com exame presencial.")
                    except Exception as e:
                        st.error(f"Erro ao consultar IA: {e}")
                        st.info("Verifique a chave ANTHROPIC_API_KEY "
                               "em st.secrets")


# ════════════════════════════════════════════════════════════════════════════
# TELA 5: RELATORIO DE VISITA
# ════════════════════════════════════════════════════════════════════════════
def page_relatorio_visita(u):
    _requer_vet()
    hdr("Relatorio de Visita", "Laudo Tecnico",
        "Documente a visita tecnica realizada")

    crmv = _crmv_atual(u)
    sel_fazenda_vet(key="vet_faz_relat")
    foid = st.session_state.get("_vet_foid")
    if not foid:
        st.warning("Selecione uma fazenda.")
        return

    t1, t2 = st.tabs(["Gerar Relatorio", "Historico"])

    with t1:
        # Buscar visita agendada (opcional)
        visitas_dispon = [v for v in listar_visitas(vet_id=u["id"])
                          if v[2] == foid and v[6] in ("agendada","realizada")]
        visita_id = None
        if visitas_dispon:
            d_vis = {"-- Sem vincular a visita --": None}
            d_vis.update({f"Visita #{v[0]} - {_fmt_dt(v[3])}": v[0]
                         for v in visitas_dispon})
            vis_sel = st.selectbox("Vincular a visita agendada",
                                  list(d_vis.keys()))
            visita_id = d_vis[vis_sel]

        with st.form("form_relat"):
            n_anim = st.number_input("Animais inspecionados",
                                    min_value=0, value=0, step=1)
            achados = st.text_area("Achados clinicos *", height=120,
                placeholder="Animais com sinais clinicos, alteracoes observadas, "
                           "estado corporal geral...")
            tratamentos = st.text_area("Tratamentos realizados", height=100,
                placeholder="Vacinas aplicadas, medicacoes, procedimentos...")
            recomendacoes = st.text_area("Recomendacoes *", height=120,
                placeholder="Acoes que o fazendeiro deve tomar, periodicidade, "
                           "alertas...")
            proxima = st.date_input("Proxima visita sugerida (opcional)",
                                   value=None)

            if st.form_submit_button("Gerar Relatorio", type="primary"):
                if not achados or not recomendacoes:
                    st.error("Preencha achados e recomendacoes.")
                else:
                    rid = adicionar_relatorio_visita(
                        vet_id=u["id"], fazenda_owner_id=foid,
                        achados=achados, tratamentos=tratamentos or "",
                        recomendacoes=recomendacoes,
                        animais_inspecionados=int(n_anim),
                        visita_id=visita_id,
                        proxima_visita=str(proxima) if proxima else None,
                        crmv=crmv
                    )
                    if visita_id:
                        atualizar_status_visita(visita_id, "realizada")
                    st.success(f"Relatorio #{rid} gerado! "
                               f"O fazendeiro recebera no painel dele.")
                    st.rerun()

    with t2:
        relats = listar_relatorios(vet_id=u["id"])
        relats = [r for r in relats if r[3] == foid]
        if not relats:
            st.info("Nenhum relatorio nesta fazenda ainda.")
        else:
            for r in relats[:20]:
                (rid, vis_id, _, _, dt_rel, n_a, ach, trat,
                 rec, prox, crmv_r) = r
                with st.expander(f"Relatorio #{rid} - {_fmt_dt(dt_rel)}"):
                    st.markdown(f"**Animais inspecionados:** {n_a}")
                    st.markdown(f"**Achados:**\n{ach}")
                    if trat: st.markdown(f"**Tratamentos:**\n{trat}")
                    st.markdown(f"**Recomendacoes:**\n{rec}")
                    if prox:
                        st.markdown(f"**Proxima visita:** {_fmt_dt(prox)}")
                    st.caption(f"CRMV: {crmv_r or '-'}")


# ════════════════════════════════════════════════════════════════════════════
# TELA 6: AGENDA DE VISITAS
# ════════════════════════════════════════════════════════════════════════════
def page_agenda_visitas(u):
    _requer_vet()
    hdr("Agenda de Visitas", "Agendamento",
        "Suas visitas tecnicas as fazendas atendidas")

    t1, t2 = st.tabs(["Agenda", "Agendar Nova"])

    with t1:
        visitas = listar_visitas(vet_id=u["id"])
        if not visitas:
            st.info("Nenhuma visita agendada.")
        else:
            agend = [v for v in visitas if v[6] == "agendada"]
            real  = [v for v in visitas if v[6] == "realizada"]

            if agend:
                st.subheader("Agendadas")
                for v in agend[:10]:
                    vid, _, foid_v, dt, obj, dur, _, obs = v
                    nome_faz = obter_nome_usuario(foid_v) if foid_v else f"Fazenda {foid_v}"
                    with st.expander(f"📅 {_fmt_dt(dt)} - {nome_faz}"):
                        st.markdown(f"**Objetivo:** {obj or '-'}")
                        st.caption(f"Duracao prevista: {dur} min")
                        if obs: st.caption(f"Obs: {obs}")
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("Marcar realizada",
                                       key=f"vis_real_{vid}"):
                                atualizar_status_visita(vid, "realizada")
                                st.rerun()
                        with c2:
                            if st.button("Cancelar",
                                       key=f"vis_canc_{vid}"):
                                atualizar_status_visita(vid, "cancelada")
                                st.rerun()

            if real:
                st.subheader("Realizadas")
                for v in real[:10]:
                    vid, _, foid_v, dt, obj, _, _, _ = v
                    nome_faz = obter_nome_usuario(foid_v) if foid_v else f"Fazenda {foid_v}"
                    st.caption(f"✅ {_fmt_dt(dt)} - {nome_faz} - {obj or '-'}")

    with t2:
        sel_fazenda_vet(key="vet_faz_agenda")
        foid_a = st.session_state.get("_vet_foid")
        if not foid_a:
            st.warning("Selecione uma fazenda.")
            return

        with st.form("form_agendar_visita"):
            data_v = st.date_input("Data da visita *",
                                  min_value=date.today())
            objetivo = st.text_input("Objetivo *",
                placeholder="Ex: Vacinacao do lote Pasto Norte")
            duracao = st.number_input("Duracao prevista (minutos)",
                                     min_value=15, value=60, step=15)
            obs_v = st.text_area("Observacoes", height=80)

            if st.form_submit_button("Agendar Visita", type="primary"):
                if not objetivo:
                    st.error("Informe o objetivo.")
                else:
                    vid = adicionar_visita(
                        vet_id=u["id"], fazenda_owner_id=foid_a,
                        data_visita=str(data_v), objetivo=objetivo,
                        duracao_min=int(duracao), observacoes=obs_v or ""
                    )
                    st.success(f"Visita #{vid} agendada para {_fmt_dt(str(data_v))}!")
                    st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# TELA 7: PAINEL DE SAUDE DO REBANHO
# ════════════════════════════════════════════════════════════════════════════
def page_painel_saude(u):
    _requer_vet()
    hdr("Painel de Saude do Rebanho", "Visao Clinica",
        "Estatisticas sanitarias por fazenda")

    sel_fazenda_vet(key="vet_faz_painel")
    foid = st.session_state.get("_vet_foid")
    if not foid:
        st.warning("Selecione uma fazenda.")
        return

    dados = painel_saude_rebanho(foid)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Animais ativos", dados["n_ativos"])
    c2.metric("Mortes acumuladas", dados["n_mortes"],
             delta=f"{dados['taxa_mortalidade']}%" if dados['n_mortes'] else None,
             delta_color="inverse" if dados["n_mortes"] else "off")
    c3.metric("Ocorrencias graves", dados["n_graves"],
             delta="atencao" if dados["n_graves"] else None,
             delta_color="inverse" if dados["n_graves"] else "off")
    c4.metric("Taxa mortalidade", f"{dados['taxa_mortalidade']}%")

    st.divider()

    st.subheader("Ocorrencias por tipo")
    if dados["por_tipo"]:
        df_tipos = pd.DataFrame(dados["por_tipo"], columns=["Tipo","Quantidade"])
        c_g, c_t = st.columns([2,1])
        with c_g:
            st.bar_chart(df_tipos.set_index("Tipo"))
        with c_t:
            st.dataframe(df_tipos, hide_index=True, use_container_width=True)
    else:
        st.info("Nenhuma ocorrencia registrada nesta fazenda.")

    st.divider()
    st.subheader("Animais em carencia")
    carencias = listar_carencias_ativas(owner_id=foid)
    if carencias:
        df_car = pd.DataFrame(carencias, columns=[
            "ID","AnimalID","Brinco","Medicamento",
            "Data Aplicacao","Dias","Liberacao"
        ])
        df_car["Data Aplicacao"] = df_car["Data Aplicacao"].apply(_fmt_dt)
        df_car["Liberacao"] = df_car["Liberacao"].apply(_fmt_dt)
        st.dataframe(
            df_car[["Brinco","Medicamento","Data Aplicacao","Dias","Liberacao"]],
            use_container_width=True, hide_index=True
        )
    else:
        st.success("Nenhum animal em periodo de carencia.")


# ════════════════════════════════════════════════════════════════════════════
# TELA 8: CONTROLE DE CARENCIA
# ════════════════════════════════════════════════════════════════════════════
def page_controle_carencia(u):
    _requer_vet()
    hdr("Controle de Carencia", "Carencia para Abate",
        "Registre aplicacoes e veja o periodo de liberacao")

    t1, t2 = st.tabs(["Registrar Carencia", "Animais em Carencia"])

    with t1:
        sel_fazenda_vet(key="vet_faz_carencia")
        foid = st.session_state.get("_vet_foid")
        if not foid:
            st.warning("Selecione uma fazenda.")
            return

        from database import listar_lotes
        lotes_c = listar_lotes(owner_id=foid)
        if not lotes_c:
            st.warning("Nenhum lote nesta fazenda.")
            return

        dict_lc = {f"{l[1]}": l[0] for l in lotes_c}
        lote_c = st.selectbox("Lote", list(dict_lc.keys()), key="car_lote")
        animais_c = listar_animais_por_lote(dict_lc[lote_c])

        alvo_c = st.radio("Aplicar em:",
            ["Lote inteiro","Animal especifico"],
            horizontal=True, key="car_alvo")
        animal_id_c = None
        if alvo_c == "Animal especifico" and animais_c:
            dict_ac = {f"{a[1]}": a[0] for a in animais_c}
            an_c_sel = st.selectbox("Animal", list(dict_ac.keys()), key="car_anim")
            animal_id_c = dict_ac[an_c_sel]

        with st.form("form_carencia"):
            med_c = st.text_input("Medicamento aplicado *",
                                 placeholder="Ex: Oxitetraciclina")
            data_apl = st.date_input("Data da aplicacao",
                                    value=date.today())
            dias_car = st.number_input("Carencia (dias)",
                                      min_value=0, value=30, step=1)

            if st.form_submit_button("Registrar Carencia", type="primary"):
                if not med_c:
                    st.error("Informe o medicamento.")
                else:
                    alvos = [animal_id_c] if animal_id_c else [a[0] for a in animais_c]
                    n_ok = 0
                    for aid in alvos:
                        try:
                            adicionar_carencia(aid, med_c, str(data_apl), int(dias_car))
                            n_ok += 1
                        except Exception:
                            pass
                    data_lib = date.today() + timedelta(days=int(dias_car))
                    st.success(
                        f"Carencia registrada para {n_ok} animal(is). "
                        f"Liberacao em {_fmt_dt(str(data_lib))}."
                    )
                    st.rerun()

    with t2:
        sel_fazenda_vet(key="vet_faz_car_list")
        foid_l = st.session_state.get("_vet_foid")
        if not foid_l:
            st.warning("Selecione uma fazenda.")
            return

        carencias = listar_carencias_ativas(owner_id=foid_l)
        if not carencias:
            st.success("Nenhum animal em carencia.")
        else:
            st.warning(f"{len(carencias)} animal(is) em carencia")
            df_c = pd.DataFrame(carencias, columns=[
                "ID","AnimalID","Brinco","Medicamento",
                "Data Aplicacao","Dias","Liberacao"
            ])
            df_c["Data Aplicacao"] = df_c["Data Aplicacao"].apply(_fmt_dt)
            df_c["Liberacao"] = df_c["Liberacao"].apply(_fmt_dt)
            # Dias restantes
            df_c["Dias rest."] = df_c["ID"].apply(lambda x: "")
            for idx, row in df_c.iterrows():
                try:
                    dt_lib = datetime.strptime(
                        str(carencias[idx][6])[:10], "%Y-%m-%d"
                    ).date()
                    df_c.at[idx, "Dias rest."] = (dt_lib - date.today()).days
                except Exception:
                    df_c.at[idx, "Dias rest."] = "-"

            st.dataframe(
                df_c[["Brinco","Medicamento","Data Aplicacao","Liberacao","Dias rest."]],
                use_container_width=True, hide_index=True
            )
