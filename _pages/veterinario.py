# _pages/veterinario.py -- Telas exclusivas do perfil veterinario
import streamlit as st
import pandas as pd
import json
import io
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
                if not novo_crmv.strip():
                    st.error("Informe o CRMV antes de salvar.")
                else:
                    try:
                        atualizar_crmv(u["id"], novo_crmv.strip())
                        st.success(f"CRMV **{novo_crmv.strip()}** salvo!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")


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
            if st.button("🔄 Sincronizar ocorrencias no prontuario",
                        help="Gera ocorrencias no prontuario para receitas antigas"):
                try:
                    n = sincronizar_ocorrencias_receitas()
                    if n:
                        st.success(f"{n} ocorrencia(s) criada(s) nos prontuarios!")
                    else:
                        st.info("Prontuarios ja estao atualizados.")
                except Exception as e:
                    st.error(f"Erro: {e}")
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
                    # Botao PDF
                    if st.button(f"Baixar PDF", key=f"pdf_rec_{rid}"):
                        try:
                            from pdf_vet import gerar_pdf_receita
                            nome_faz = obter_nome_usuario(foid) if foid else ""
                            nome_an  = ""
                            if an_id:
                                try:
                                    an_data = obter_animal(an_id)
                                    nome_an = an_data[1] if an_data else f"#{an_id}"
                                except Exception:
                                    nome_an = f"#{an_id}"
                            pdf_bytes = gerar_pdf_receita({
                                "id": rid, "nome_vet": u.get("nome",""),
                                "crmv": crmv, "nome_fazenda": nome_faz,
                                "nome_animal": nome_an or "Lote inteiro",
                                "medicamento": med, "dose": dose,
                                "via": via, "duracao": dur,
                                "carencia_dias": carenc,
                                "observacoes": obs_r or "",
                                "data_emissao": _fmt_dt(dt_em),
                            })
                            st.download_button(
                                label=f"Clique para baixar receita_{rid}.pdf",
                                data=pdf_bytes,
                                file_name=f"receita_{rid}.pdf",
                                mime="application/pdf",
                                key=f"dl_rec_{rid}"
                            )
                        except Exception as e:
                            st.error(f"Erro ao gerar PDF: {e}")


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
                    if st.button(f"Baixar PDF", key=f"pdf_rel_{rid}"):
                        try:
                            from pdf_vet import gerar_pdf_relatorio_visita
                            nome_faz_r = obter_nome_usuario(foid) if foid else ""
                            pdf_bytes = gerar_pdf_relatorio_visita({
                                "id": rid, "nome_vet": u.get("nome",""),
                                "crmv": crmv_r or crmv,
                                "nome_fazenda": nome_faz_r,
                                "data_relatorio": _fmt_dt(dt_rel),
                                "animais_inspecionados": n_a,
                                "achados": ach, "tratamentos": trat,
                                "recomendacoes": rec,
                                "proxima_visita": _fmt_dt(prox) if prox and str(prox) != "None" else "",
                            })
                            st.download_button(
                                label=f"Clique para baixar relatorio_{rid}.pdf",
                                data=pdf_bytes,
                                file_name=f"relatorio_visita_{rid}.pdf",
                                mime="application/pdf",
                                key=f"dl_rel_{rid}"
                            )
                        except Exception as e:
                            st.error(f"Erro ao gerar PDF: {e}")


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


# ════════════════════════════════════════════════════════════════════════════
# TELA 9: EXAMES LABORATORIAIS
# ════════════════════════════════════════════════════════════════════════════
def page_exames_laboratoriais(u):
    _requer_vet()
    hdr("Exames Laboratoriais", "Registro de Exames",
        "Solicite e registre resultados de exames dos animais")

    sel_fazenda_vet(key="vet_faz_exames")
    foid = st.session_state.get("_vet_foid")
    if not foid:
        st.warning("Selecione uma fazenda.")
        return

    from database import listar_lotes
    lotes_ex = listar_lotes(owner_id=foid)
    if not lotes_ex:
        st.warning("Nenhum lote nesta fazenda.")
        return

    t1, t2 = st.tabs(["Solicitar / Registrar", "Historico"])

    with t1:
        dict_l = {f"{l[1]}": l[0] for l in lotes_ex}
        lote_sel = st.selectbox("Lote", list(dict_l.keys()), key="ex_lote")
        animais_ex = listar_animais_por_lote(dict_l[lote_sel])
        if not animais_ex:
            st.warning("Nenhum animal neste lote.")
        else:
            dict_a = {f"{a[1]}": a[0] for a in animais_ex}
            an_sel = st.selectbox("Animal *", list(dict_a.keys()), key="ex_animal")
            animal_id_ex = dict_a[an_sel]

            with st.form("form_exame"):
                c1, c2 = st.columns(2)
                with c1:
                    tipo_ex = st.selectbox("Tipo de exame *", [
                        "Hemograma completo",
                        "Bioquimica serica",
                        "Brucelose (AAT)",
                        "Tuberculose (IDTB)",
                        "Parasitologico",
                        "Cultura e antibiograma",
                        "PCR",
                        "Sorologico",
                        "Urinanalise",
                        "Outro",
                    ])
                    data_col = st.date_input("Data da coleta *",
                                            value=date.today())
                with c2:
                    laboratorio = st.text_input("Laboratorio",
                        placeholder="Ex: LabVet SP")
                    status_ex = st.selectbox("Status",
                        ["aguardando", "concluido"])

                resultado = st.text_area("Resultado",
                    height=80,
                    placeholder="Preencha quando o resultado chegar...")
                interpretacao = st.text_area("Interpretacao clinica",
                    height=80,
                    placeholder="Sua avaliacao do resultado...")
                alerta = st.checkbox(
                    "Resultado alterado (marcar para alertar fazendeiro)",
                    value=False
                )

                if st.form_submit_button("Salvar Exame", type="primary"):
                    eid = adicionar_exame(
                        animal_id=animal_id_ex,
                        vet_id=u["id"],
                        tipo_exame=tipo_ex,
                        data_coleta=str(data_col),
                        laboratorio=laboratorio or "",
                        resultado=resultado or "",
                        interpretacao=interpretacao or "",
                        status=status_ex,
                        alerta=1 if alerta else 0,
                    )
                    msg = f"Exame #{eid} salvo!"
                    if alerta:
                        msg += " Fazendeiro sera alertado."
                    st.success(msg)
                    st.rerun()

    with t2:
        # Listar todos os exames do vet nesta fazenda
        exames_vet = listar_exames(vet_id=u["id"])
        # Filtrar pelos animais da fazenda selecionada
        ids_anim_faz = set()
        for l in lotes_ex:
            for a in listar_animais_por_lote(l[0]):
                ids_anim_faz.add(a[0])
        exames_faz = [e for e in exames_vet if e[1] in ids_anim_faz]

        if not exames_faz:
            st.info("Nenhum exame nesta fazenda ainda.")
        else:
            st.caption(f"{len(exames_faz)} exame(s) registrado(s)")
            for ex in exames_faz[:30]:
                (eid, aid, vid, dt_col, tipo, lab,
                 res, interp, stat, alt) = ex
                # Buscar nome do animal
                nome_a = next((a[1] for a in
                    listar_animais_por_lote(dict_l[list(dict_l.keys())[0]])
                    if a[0] == aid), f"#{aid}")
                icone = "🔴" if alt else ("✅" if stat == "concluido" else "⏳")
                with st.expander(
                    f"{icone} {tipo} — {_fmt_dt(dt_col)} — {nome_a}"
                ):
                    c1e, c2e = st.columns(2)
                    with c1e:
                        st.markdown(f"**Laboratorio:** {lab or '-'}")
                        st.markdown(f"**Status:** {stat}")
                    with c2e:
                        if alt:
                            st.error("Resultado alterado!")
                    if res:
                        st.markdown(f"**Resultado:** {res}")
                    if interp:
                        st.markdown(f"**Interpretacao:** {interp}")

                    # Form para atualizar resultado
                    with st.form(f"form_upd_ex_{eid}"):
                        novo_res   = st.text_area("Atualizar resultado",
                            value=res or "", height=60,
                            key=f"nres_{eid}")
                        novo_interp = st.text_area("Atualizar interpretacao",
                            value=interp or "", height=60,
                            key=f"nint_{eid}")
                        novo_alt = st.checkbox("Resultado alterado",
                            value=bool(alt), key=f"nalt_{eid}")
                        if st.form_submit_button("Atualizar"):
                            atualizar_exame(
                                eid, novo_res, novo_interp,
                                "concluido", 1 if novo_alt else 0
                            )
                            st.success("Exame atualizado!")
                            st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# TELA 10: MONITORAMENTO POS-TRATAMENTO
# ════════════════════════════════════════════════════════════════════════════
def page_monitoramento(u):
    _requer_vet()
    hdr("Monitoramento Pos-Tratamento", "Follow-up Clinico",
        "Acompanhe a evolucao dos animais apos tratamento")

    sel_fazenda_vet(key="vet_faz_monitor")
    foid = st.session_state.get("_vet_foid")
    if not foid:
        st.warning("Selecione uma fazenda.")
        return

    from database import listar_lotes
    lotes_m = listar_lotes(owner_id=foid)
    if not lotes_m:
        st.warning("Nenhum lote nesta fazenda.")
        return

    t1, t2 = st.tabs(["Monitoramentos Ativos", "Criar Monitoramento"])

    with t1:
        mons = listar_monitoramentos(vet_id=u["id"], apenas_ativos=True)
        # Filtrar pela fazenda
        ids_anim_faz = set()
        for l in lotes_m:
            for a in listar_animais_por_lote(l[0]):
                ids_anim_faz.add(a[0])
        mons_faz = [m for m in mons if m["animal_id"] in ids_anim_faz]

        if not mons_faz:
            st.success("Nenhum monitoramento ativo nesta fazenda.")
        else:
            # Separar vencidos e em dia
            vencidos = [m for m in mons_faz if m["vencido"]]
            em_dia   = [m for m in mons_faz if not m["vencido"]]

            if vencidos:
                st.error(f"⚠ {len(vencidos)} retorno(s) em atraso!")
            if em_dia:
                st.info(f"📋 {len(em_dia)} monitoramento(s) em andamento")

            for m in sorted(mons_faz,
                           key=lambda x: x["data_retorno"]):
                venc_icon = "🔴" if m["vencido"] else "🟢"
                dt_ret = _fmt_dt(m["data_retorno"])

                # Buscar nome do animal
                brinco = m.get("brinco") or f"#{m['animal_id']}"

                with st.expander(
                    f"{venc_icon} {brinco} — retorno {dt_ret} — "
                    f"{m['descricao'][:50]}"
                ):
                    st.markdown(f"**Descricao:** {m['descricao']}")
                    st.markdown(
                        f"**Inicio:** {_fmt_dt(m['data_inicio'])} | "
                        f"**Retorno:** {_fmt_dt(m['data_retorno'])}"
                    )

                    # Evolucoes registradas
                    if m["evolucoes"]:
                        st.markdown("**Evolucoes registradas:**")
                        for ev in m["evolucoes"]:
                            quem_ic = "🩺" if ev.get("quem") == "vet" else "🌾"
                            st.caption(
                                f"{quem_ic} {_fmt_dt(ev.get('data',''))} — "
                                f"{ev.get('texto','')}"
                            )

                    # Vet pode registrar evolucao
                    with st.form(f"form_ev_{m['id']}"):
                        nova_ev = st.text_area("Registrar evolucao",
                            height=60,
                            placeholder="Como o animal esta respondendo?",
                            key=f"ev_{m['id']}")
                        c1m, c2m = st.columns(2)
                        with c1m:
                            if st.form_submit_button("Salvar evolucao"):
                                if nova_ev:
                                    registrar_evolucao(
                                        m["id"], nova_ev,
                                        str(date.today()), "vet"
                                    )
                                    st.success("Evolucao registrada!")
                                    st.rerun()
                        with c2m:
                            if st.form_submit_button(
                                "Encerrar monitoramento",
                                type="secondary"
                            ):
                                encerrar_monitoramento(m["id"])
                                st.success("Monitoramento encerrado.")
                                st.rerun()

    with t2:
        dict_l2 = {f"{l[1]}": l[0] for l in lotes_m}
        lote_m = st.selectbox("Lote", list(dict_l2.keys()), key="mon_lote")
        animais_m = listar_animais_por_lote(dict_l2[lote_m])

        if not animais_m:
            st.warning("Nenhum animal neste lote.")
        else:
            dict_a2 = {f"{a[1]}": a[0] for a in animais_m}
            an_m = st.selectbox("Animal *", list(dict_a2.keys()),
                               key="mon_animal")
            animal_id_m = dict_a2[an_m]

            # Vincular a receita existente (opcional)
            receitas_m = listar_receitas(vet_id=u["id"])
            dict_rec = {"-- Sem vinculo a receita --": None}
            dict_rec.update({
                f"#{r[0]} - {r[6]} ({_fmt_dt(r[5])})": r[0]
                for r in receitas_m[:20]
            })

            with st.form("form_criar_monitor"):
                descricao_m = st.text_area("Descricao do tratamento *",
                    height=80,
                    placeholder="Ex: Tratamento de pneumonia com Oxitetraciclina")
                c1n, c2n = st.columns(2)
                with c1n:
                    data_ini_m = st.date_input("Inicio do tratamento",
                                              value=date.today())
                    rec_sel = st.selectbox("Vincular a receita",
                                          list(dict_rec.keys()))
                with c2n:
                    dias_retorno = st.number_input(
                        "Retorno em quantos dias?",
                        min_value=1, value=7, step=1
                    )
                    data_ret = data_ini_m + timedelta(days=int(dias_retorno))
                    st.info(f"Data de retorno: **{_fmt_dt(str(data_ret))}**")

                if st.form_submit_button("Criar Monitoramento",
                                        type="primary"):
                    if not descricao_m:
                        st.error("Informe a descricao.")
                    else:
                        mid = adicionar_monitoramento(
                            animal_id=animal_id_m,
                            vet_id=u["id"],
                            descricao=descricao_m,
                            data_inicio=str(data_ini_m),
                            data_retorno=str(data_ret),
                            receita_id=dict_rec[rec_sel],
                        )
                        st.success(
                            f"Monitoramento #{mid} criado! "
                            f"Retorno em {_fmt_dt(str(data_ret))}. "
                            f"O fazendeiro sera alertado na data."
                        )
                        st.rerun()
