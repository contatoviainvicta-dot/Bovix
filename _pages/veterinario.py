# _pages/veterinario.py -- Telas exclusivas do perfil veterinario
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
                            tabela_paginada, paginar_dataframe,
                            safe_line_chart, safe_bar_chart)
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
    def safe_line_chart(df, titulo=None, empty_msg="Sem dados."):
        import pandas as pd
        if df is None or (hasattr(df,"empty") and df.empty): st.info(empty_msg); return
        try:
            df = pd.DataFrame(df).replace([float("inf"),float("-inf")],None).dropna(how="all")
            if not df.empty: safe_line_chart(df)
            else: st.info(empty_msg)
        except Exception as e: st.info(f"Grafico indisponivel: {e}")
    def safe_bar_chart(df, titulo=None, empty_msg="Sem dados."):
        import pandas as pd
        if df is None or (hasattr(df,"empty") and df.empty): st.info(empty_msg); return
        try:
            df = pd.DataFrame(df).replace([float("inf"),float("-inf")],None).dropna(how="all")
            if not df.empty: safe_bar_chart(df)
            else: st.info(empty_msg)
        except Exception as e: st.info(f"Grafico indisponivel: {e}")
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
        return fmt_data(d)
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
        toast_ok("CRMV cadastrado: **{crmv_atual}**")
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
                        toast_ok("CRMV **{novo_crmv.strip()}** salvo!")
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
                    toast_ok(f"Receita #{rid} emitida com sucesso!")
                    st.rerun()

    with t2:
        try:
            receitas = listar_receitas(vet_id=u["id"])
        except Exception:
            receitas = []
            st.warning("⚠️ Erro ao carregar receitas. Tente novamente.")
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
            desc_proto = st.text_area("Descricao", height=68)
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
                    toast_ok("Protocolo criado! Adicione itens abaixo.")
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
                        toast_ok(f"Item '{nome_i}' adicionado!")
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
                    toast_ok(f"Relatorio #{rid} gerado! "
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

    # seletor de fazenda disponivel em TODAS as abas
    sel_fazenda_vet(key="vet_faz_agenda")
    foid_a = st.session_state.get("_vet_foid")

    t1, t2 = st.tabs(["Agenda", "Agendar Nova"])

    with t1:
        visitas = listar_visitas(vet_id=u["id"])
        if not visitas:
            empty_state("Sem visitas agendadas", "Agende uma visita técnica para começar.", icone="📅")
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

                        c1, c2, c3 = st.columns(3)
                        with c1:
                            if st.button("Marcar realizada",
                                        key=f"vis_real_{vid}"):
                                atualizar_status_visita(vid, "realizada")
                                st.session_state[f"_lan_hon_{vid}"] = True
                                st.rerun()
                        with c2:
                            if st.button("Cancelar",
                                        key=f"vis_canc_{vid}"):
                                atualizar_status_visita(vid, "cancelada")
                                st.rerun()
                        with c3:
                            if st.button("Lancar honorario",
                                        key=f"vis_hon_{vid}"):
                                st.session_state[f"_lan_hon_{vid}"] = True
                                st.rerun()

                        # Form de honorario inline
                        if st.session_state.get(f"_lan_hon_{vid}"):
                            _foid_hon = foid_v  # usar fazenda da visita
                            st.divider()
                            st.markdown("**Lancar honorario desta visita:**")
                            with st.form(f"form_hon_{vid}"):
                                h1, h2 = st.columns(2)
                                with h1:
                                    desc_h = st.text_input(
                                        "Descricao *",
                                        value=f"Visita tecnica - {obj or ''}",
                                        key=f"hon_desc_{vid}"
                                    )
                                    tipo_h = st.selectbox(
                                        "Tipo",
                                        ["consulta","vacinacao","cirurgia",
                                         "exame","procedimento","outros"],
                                        key=f"hon_tipo_{vid}"
                                    )
                                with h2:
                                    val_h = st.number_input(
                                        "Valor total (R$) *",
                                        min_value=0.0, value=0.0,
                                        step=50.0, format="%.2f",
                                        key=f"hon_val_{vid}"
                                    )
                                    obs_h = st.text_input(
                                        "Observacoes",
                                        key=f"hon_obs_{vid}"
                                    )

                                st.markdown("**Itens / Procedimentos** (opcional):")
                                n_itens = st.number_input(
                                    "Quantos itens detalhar?",
                                    min_value=0, max_value=10,
                                    value=0, step=1,
                                    key=f"hon_ni_{vid}"
                                )
                                itens_h = []
                                for ii in range(int(n_itens)):
                                    ic1, ic2, ic3 = st.columns([3, 1, 1])
                                    with ic1:
                                        d_i = st.text_input(
                                            f"Item {ii+1}",
                                            key=f"hon_id_{vid}_{ii}"
                                        )
                                    with ic2:
                                        q_i = st.number_input(
                                            "Qtd", min_value=1, value=1,
                                            key=f"hon_iq_{vid}_{ii}"
                                        )
                                    with ic3:
                                        v_i = st.number_input(
                                            "R$ unit", min_value=0.0,
                                            value=0.0, step=10.0,
                                            format="%.2f",
                                            key=f"hon_iv_{vid}_{ii}"
                                        )
                                    if d_i:
                                        itens_h.append({
                                            "descricao": d_i,
                                            "quantidade": q_i,
                                            "valor_unitario": v_i
                                        })

                                c_s1, c_s2 = st.columns(2)
                                with c_s1:
                                    if st.form_submit_button(
                                        "Confirmar lancamento",
                                        type="primary"
                                    ):
                                        if not desc_h or val_h <= 0:
                                            st.error("Informe descricao e valor.")
                                        else:
                                            lancar_honorario(
                                                vet_id=u["id"],
                                                fazenda_owner_id=_foid_hon,
                                                descricao=desc_h,
                                                valor=val_h,
                                                tipo=tipo_h,
                                                visita_id=vid,
                                                itens=itens_h or None,
                                                observacoes=obs_h or ""
                                            )
                                            st.session_state.pop(
                                                f"_lan_hon_{vid}", None
                                            )
                                            st.success(
                                                f"Honorario de "
                                                f"R$ {val_h:.2f} lancado!"
                                            )
                                            st.rerun()
                                with c_s2:
                                    if st.form_submit_button("Cancelar"):
                                        st.session_state.pop(
                                            f"_lan_hon_{vid}", None
                                        )
                                        st.rerun()

            if real:
                st.subheader("Realizadas")
                for v in real[:10]:
                    vid, _, foid_v, dt, obj, dur, _, obs = v
                    nome_faz = obter_nome_usuario(foid_v) if foid_v else f"Fazenda {foid_v}"

                    # Se acabou de ser marcada realizada, mostrar form
                    if st.session_state.get(f"_lan_hon_{vid}"):
                        with st.expander(
                            f"✅ {_fmt_dt(dt)} - {nome_faz} — Lancar honorario",
                            expanded=True
                        ):
                            _foid_hon = foid_v
                            with st.form(f"form_hon_r_{vid}"):
                                h1, h2 = st.columns(2)
                                with h1:
                                    desc_h = st.text_input(
                                        "Descricao *",
                                        value=f"Visita tecnica - {obj or ''}",
                                        key=f"honr_desc_{vid}"
                                    )
                                    tipo_h = st.selectbox(
                                        "Tipo",
                                        ["consulta","vacinacao","cirurgia",
                                         "exame","procedimento","outros"],
                                        key=f"honr_tipo_{vid}"
                                    )
                                with h2:
                                    val_h = st.number_input(
                                        "Valor total (R$) *",
                                        min_value=0.0, value=0.0,
                                        step=50.0, format="%.2f",
                                        key=f"honr_val_{vid}"
                                    )
                                    obs_h = st.text_input(
                                        "Observacoes",
                                        key=f"honr_obs_{vid}"
                                    )
                                c_s1, c_s2 = st.columns(2)
                                with c_s1:
                                    if st.form_submit_button(
                                        "Confirmar lancamento",
                                        type="primary"
                                    ):
                                        if not desc_h or val_h <= 0:
                                            st.error("Informe descricao e valor.")
                                        else:
                                            lancar_honorario(
                                                vet_id=u["id"],
                                                fazenda_owner_id=_foid_hon,
                                                descricao=desc_h,
                                                valor=val_h,
                                                tipo=tipo_h,
                                                visita_id=vid,
                                                observacoes=obs_h or ""
                                            )
                                            st.session_state.pop(
                                                f"_lan_hon_{vid}", None
                                            )
                                            st.success(
                                                f"Honorario de R$ {val_h:.2f} lancado!"
                                            )
                                            st.rerun()
                                with c_s2:
                                    if st.form_submit_button("Pular"):
                                        st.session_state.pop(
                                            f"_lan_hon_{vid}", None
                                        )
                                        st.rerun()
                    else:
                        st.caption(
                            f"✅ {_fmt_dt(dt)} - {nome_faz} - {obj or '-'}"
                        )

    with t2:
        if not foid_a:
            st.warning("Selecione uma fazenda acima.")
        else:
            with st.form("form_agendar_visita"):
                data_v = st.date_input("Data da visita *",
                                      min_value=date.today())
                objetivo = st.text_input(
                    "Objetivo *",
                    placeholder="Ex: Vacinacao do lote Pasto Norte"
                )
                duracao = st.number_input(
                    "Duracao prevista (minutos)",
                    min_value=15, value=60, step=15
                )
                obs_v = st.text_area("Observacoes", height=80)

                if st.form_submit_button("Agendar Visita", type="primary"):
                    if not objetivo:
                        st.error("Informe o objetivo.")
                    else:
                        vid = adicionar_visita(
                            vet_id=u["id"],
                            fazenda_owner_id=foid_a,
                            data_visita=str(data_v),
                            objetivo=objetivo,
                            duracao_min=int(duracao),
                            observacoes=obs_v or ""
                        )
                        toast_ok(
                            f"Visita #{vid} agendada para "
                            f"{_fmt_dt(str(data_v))}!"
                        )
                        st.rerun()


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
            safe_bar_chart(df_tipos.set_index("Tipo"))
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
        st.info("Nenhum animal em periodo de carencia.")


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
                        except Exception as _e:
                            pass  # silenced
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
            st.info("Nenhum animal em carencia.")
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
                            value=res or "", height=68,
                            key=f"nres_{eid}")
                        novo_interp = st.text_area("Atualizar interpretacao",
                            value=interp or "", height=68,
                            key=f"nint_{eid}")
                        novo_alt = st.checkbox("Resultado alterado",
                            value=bool(alt), key=f"nalt_{eid}")
                        if st.form_submit_button("Atualizar"):
                            atualizar_exame(
                                eid, novo_res, novo_interp,
                                "concluido", 1 if novo_alt else 0
                            )
                            toast_ok("Exame atualizado!")
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
            st.info("Nenhum monitoramento ativo nesta fazenda.")
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
                            height=68,
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
                                toast_ok("Monitoramento encerrado.")
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


# ════════════════════════════════════════════════════════════════════════════
# TELA 11: GESTAO FINANCEIRA DO VET
# ════════════════════════════════════════════════════════════════════════════
def page_gestao_financeira_vet(u):
    _requer_vet()
    import pandas as pd
    hdr("Gestao Financeira", "Honorarios e Faturamento",
        "Controle de cobranças, recebimentos e extrato por fazenda")

    # ── Resumo do periodo selecionado ─────────────────────────────────────
    from datetime import date
    hoje = date.today()

    # Seletor de mes/ano (padrao: mes atual)
    _meses_nomes = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                    "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    sel1, sel2, _ = st.columns([1, 1, 2])
    with sel1:
        _mes_sel = st.selectbox(
            "Mês", range(1, 13),
            index=hoje.month - 1,
            format_func=lambda m: _meses_nomes[m - 1],
            key="fin_vet_mes"
        )
    with sel2:
        _anos = list(range(hoje.year - 2, hoje.year + 1))
        _ano_sel = st.selectbox(
            "Ano", _anos,
            index=len(_anos) - 1,
            key="fin_vet_ano"
        )

    res  = resumo_financeiro_vet(u["id"], mes=_mes_sel, ano=_ano_sel)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("A receber",
              fmt_brl(res['pendente']),
              delta=f"{res['n_pendente']} lançamento(s)")
    c2.metric("Recebido no mês",
              fmt_brl(res['pago']),
              delta=f"{res['n_pago']} pago(s)")
    c3.metric("Total lançado",
              fmt_brl(res['pendente']+res['pago']))
    c4.metric("Período", res["mes"])

    st.divider()
    t1, t2, t3 = st.tabs(["Honorários", "Lançar Avulso", "Faturamento"])

    # ── ABA 1: Lista de honorários ────────────────────────────────────────
    with t1:
        # Filtros
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            filtro_status = st.selectbox(
                "Status", ["todos","pendente","pago","cancelado"],
                key="fin_status"
            )
        with fc2:
            sel_fazenda_vet(key="vet_faz_fin")
            foid_fin = st.session_state.get("_vet_foid")
        with fc3:
            pass  # espaço

        hons = listar_honorarios(
            u["id"],
            fazenda_owner_id=foid_fin if foid_fin else None,
            status=filtro_status if filtro_status != "todos" else None
        )

        if not hons:
            st.info("Nenhum honorário encontrado.")
        else:
            # Totais filtrados
            _total_filt = sum(float(h[7]) for h in hons
                             if h[8] != "cancelado")
            st.caption(
                f"{len(hons)} lançamento(s) | "
                f"Total: R$ {_total_filt:,.2f}"
            )

            for h in hons:
                (hid, _, foid_h, vis_id, dt_lan, desc_h,
                 tipo_h, val_h, stat_h, dt_pag,
                 forma_pag, obs_h) = h

                nome_faz = obter_nome_usuario(foid_h) or f"#{foid_h}"
                ic = {"pendente": "🟡", "pago": "✅", "cancelado": "❌"}.get(
                    stat_h, "⚪"
                )
                dt_fmt = fmt_data(dt_lan)

                with st.expander(
                    f"{ic} {desc_h} | {nome_faz} | "
                    f"R$ {float(val_h):,.2f} | {dt_fmt}"
                ):
                    col_i, col_d = st.columns(2)
                    with col_i:
                        st.markdown(f"**Tipo:** {tipo_h}")
                        st.markdown(f"**Fazenda:** {nome_faz}")
                        st.markdown(f"**Status:** {stat_h.upper()}")
                        if vis_id:
                            st.caption(f"Vinculado à visita #{vis_id}")
                    with col_d:
                        st.markdown(f"**Valor:** R$ {float(val_h):,.2f}")
                        if dt_pag:
                            dp_fmt = fmt_data(dt_pag)
                            st.markdown(f"**Pago em:** {dp_fmt}")
                        if forma_pag:
                            st.markdown(f"**Forma:** {forma_pag}")
                        if obs_h:
                            st.caption(f"Obs: {obs_h}")

                    # Itens detalhados
                    itens_h = listar_itens_honorario(hid)
                    if itens_h:
                        st.markdown("**Itens:**")
                        import pandas as pd
                        df_i = pd.DataFrame(itens_h, columns=[
                            "ID","HonID","Descricao","Qtd",
                            "Valor Unit","Total"
                        ])
                        df_i["Valor Unit"] = df_i["Valor Unit"].apply(
                            lambda x: fmt_brl(float(x))
                        )
                        df_i["Total"] = df_i["Total"].apply(
                            lambda x: fmt_brl(float(x))
                        )
                        st.dataframe(
                            df_i[["Descricao","Qtd","Valor Unit","Total"]],
                            use_container_width=True,
                            hide_index=True
                        )

                    # Ações
                    if stat_h == "pendente":
                        ac1, ac2, ac3 = st.columns(3)
                        with ac1:
                            forma = st.selectbox(
                                "Forma de pagamento",
                                ["PIX","Transferência","Dinheiro",
                                 "Cheque","Boleto","Cartão"],
                                key=f"fin_forma_{hid}"
                            )
                        with ac2:
                            if st.button("Marcar como pago",
                                        key=f"fin_pago_{hid}",
                                        type="primary"):
                                registrar_pagamento_honorario(hid, forma)
                                limpar_cache()
                                toast_ok("Pagamento registrado!")
                                st.rerun()
                        with ac3:
                            if st.button("Cancelar lançamento",
                                        key=f"fin_canc_{hid}"):
                                cancelar_honorario(hid)
                                limpar_cache()
                                st.warning("Lançamento cancelado.")
                                st.rerun()

    # ── ABA 2: Lançar Avulso ──────────────────────────────────────────────
    with t2:
        st.caption(
            "Lance honorários não vinculados a visitas — "
            "teleconsultas, laudos, pareceres, etc."
        )
        sel_fazenda_vet(key="vet_faz_fin_av")
        foid_av = st.session_state.get("_vet_foid")
        if not foid_av:
            st.warning("Selecione uma fazenda.")
        else:
            with st.form("form_hon_avulso"):
                a1, a2 = st.columns(2)
                with a1:
                    desc_av = st.text_input(
                        "Descricao *",
                        placeholder="Ex: Teleconsulta, Laudo técnico"
                    )
                    tipo_av = st.selectbox(
                        "Tipo",
                        ["consulta","vacinacao","cirurgia",
                         "exame","procedimento","laudo",
                         "teleconsulta","outros"]
                    )
                with a2:
                    val_av  = st.number_input(
                        "Valor (R$) *",
                        min_value=0.0, value=0.0,
                        step=50.0, format="%.2f"
                    )
                    obs_av  = st.text_input("Observacoes")

                # Itens
                st.markdown("**Itens detalhados** (opcional):")
                n_av = st.number_input(
                    "Quantos procedimentos?",
                    min_value=0, max_value=10, value=0, step=1
                )
                itens_av = []
                for ii in range(int(n_av)):
                    iv1, iv2, iv3 = st.columns([3,1,1])
                    with iv1:
                        d_av = st.text_input(
                            f"Procedimento {ii+1}",
                            key=f"av_d_{ii}"
                        )
                    with iv2:
                        q_av = st.number_input(
                            "Qtd", min_value=1, value=1,
                            key=f"av_q_{ii}"
                        )
                    with iv3:
                        v_av = st.number_input(
                            "R$ unit", min_value=0.0,
                            value=0.0, step=10.0,
                            format="%.2f", key=f"av_v_{ii}"
                        )
                    if d_av:
                        itens_av.append({
                            "descricao": d_av,
                            "quantidade": q_av,
                            "valor_unitario": v_av
                        })

                if st.form_submit_button("Lançar Honorário", type="primary"):
                    if not desc_av or val_av <= 0:
                        st.error("Informe descrição e valor.")
                    else:
                        hid = lancar_honorario(
                            vet_id=u["id"],
                            fazenda_owner_id=foid_av,
                            descricao=desc_av,
                            valor=val_av,
                            tipo=tipo_av,
                            itens=itens_av or None,
                            observacoes=obs_av or ""
                        )
                        toast_ok(
                            f"Honorário #{hid} de R$ {val_av:.2f} lançado!"
                        )
                        st.rerun()

    # ── ABA 3: Faturamento ────────────────────────────────────────────────
    with t3:
        st.subheader("Faturamento Mensal")

        # Seletor de mês
        m1, m2 = st.columns(2)
        with m1:
            mes_sel = st.selectbox(
                "Mês",
                list(range(1, 13)),
                index=hoje.month - 1,
                format_func=lambda x: [
                    "Jan","Fev","Mar","Abr","Mai","Jun",
                    "Jul","Ago","Set","Out","Nov","Dez"
                ][x-1]
            )
        with m2:
            ano_sel = st.selectbox(
                "Ano",
                list(range(hoje.year - 2, hoje.year + 1)),
                index=2
            )

        res_sel = resumo_financeiro_vet(
            u["id"], mes=int(mes_sel), ano=int(ano_sel)
        )

        # Cards do período
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("A receber",   fmt_brl(res_sel['pendente']))
        mc2.metric("Recebido",    fmt_brl(res_sel['pago']))
        mc3.metric("Total",
                   fmt_brl(res_sel['pendente']+res_sel['pago']))

        # Por fazenda
        if res_sel["por_fazenda"]:
            st.divider()
            st.subheader("Por Fazenda")
            import pandas as pd
            df_faz = pd.DataFrame(
                [(obter_nome_usuario(r[0]) or f"#{r[0]}",
                  r[1],
                  fmt_brl(float(r[2])))
                 for r in res_sel["por_fazenda"]],
                columns=["Fazenda","Lançamentos","Total"]
            )
            st.dataframe(df_faz, use_container_width=True,
                        hide_index=True)

        # Gráfico últimos 12 meses
        if res_sel["mensal"]:
            st.divider()
            st.subheader("Últimos 12 meses")
            df_mensal = pd.DataFrame(
                res_sel["mensal"],
                columns=["Mês","Faturado"]
            )
            df_mensal["Faturado"] = df_mensal["Faturado"].apply(float)
            df_mensal = df_mensal.sort_values("Mês")
            safe_bar_chart(df_mensal.set_index("Mês"))

        # Extrato detalhado
        st.divider()
        st.subheader("Extrato Detalhado")
        hons_mes = listar_honorarios(u["id"])
        prefixo_sel = f"{int(ano_sel)}-{int(mes_sel):02d}"
        hons_filt = [
            h for h in hons_mes
            if str(h[4]).startswith(prefixo_sel)
            and h[8] != "cancelado"
        ]
        if hons_filt:
            df_ext = pd.DataFrame(
                [(h[4], obter_nome_usuario(h[2]) or f"#{h[2]}",
                  h[5], h[6],
                  fmt_brl(float(h[7])), h[8].upper())
                 for h in hons_filt],
                columns=["Data","Fazenda","Descricao",
                         "Tipo","Valor","Status"]
            )
            st.dataframe(df_ext, use_container_width=True,
                        hide_index=True)
        else:
            st.info("Nenhum lançamento neste período.")


# ════════════════════════════════════════════════════════════════════════════
# TELA 12: MAPA EPIDEMIOLOGICO
# ════════════════════════════════════════════════════════════════════════════
def page_mapa_epidemiologico(u):
    _requer_vet()
    hdr("Mapa Epidemiologico", "Visao Cruzada das Fazendas",
        "Distribuicao de doencas e saude do rebanho em todas as fazendas atendidas")

    dados_faz = epidemiologia_por_fazenda(u["id"])
    if not dados_faz:
        st.info("Nenhuma fazenda aprovada ainda.")
        return

    # ── Cards de resumo ───────────────────────────────────────────────────
    n_faz     = len(dados_faz)
    total_an  = sum(f["n_ativos"] for f in dados_faz)
    total_mort= sum(f["n_mortos"] for f in dados_faz)
    taxa_geral= round(100*total_mort/max(1,total_an+total_mort), 2)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Fazendas atendidas", n_faz)
    c2.metric("Animais ativos", total_an)
    c3.metric("Mortes acumuladas", total_mort)
    c4.metric("Taxa mortalidade geral", f"{taxa_geral}%",
             delta_color="inverse" if taxa_geral > 2 else "off")

    st.divider()
    t1, t2, t3 = st.tabs(["Comparativo", "Mapa", "Alertas Cruzados"])

    # ── ABA 1: Comparativo entre fazendas ─────────────────────────────────
    with t1:
        st.subheader("Ocorrencias por Fazenda")

        # Montar dataframe comparativo
        rows_comp = []
        for f in dados_faz:
            top_tipo = f["por_tipo"][0][0] if f["por_tipo"] else "-"
            n_oc     = sum(t[1] for t in f["por_tipo"])
            rows_comp.append({
                "Fazenda":       f["nome"],
                "Ativos":        f["n_ativos"],
                "Mortes":        f["n_mortos"],
                "Taxa Mort %":   f["taxa_mort"],
                "Ocorrencias":   n_oc,
                "Top Doenca":    top_tipo,
            })

        if rows_comp:
            df_comp = pd.DataFrame(rows_comp)
            st.dataframe(df_comp, use_container_width=True, hide_index=True)

            st.divider()
            st.subheader("Distribuicao de Ocorrencias por Tipo")
            # Grafico consolidado
            all_tipos = {}
            for f in dados_faz:
                for tipo, cnt in f["por_tipo"]:
                    all_tipos[tipo] = all_tipos.get(tipo, 0) + cnt
            if all_tipos:
                df_tipos = pd.DataFrame(
                    sorted(all_tipos.items(), key=lambda x: x[1], reverse=True),
                    columns=["Tipo", "Total"]
                )
                safe_bar_chart(df_tipos.set_index("Tipo"))

            # Detalhe por fazenda
            st.divider()
            st.subheader("Detalhe por Fazenda")
            for f in dados_faz:
                if f["por_tipo"]:
                    with st.expander(f["nome"]):
                        df_f = pd.DataFrame(
                            f["por_tipo"], columns=["Tipo","Ocorrencias"]
                        )
                        c_g, c_t = st.columns([2, 1])
                        with c_g:
                            safe_bar_chart(df_f.set_index("Tipo"))
                        with c_t:
                            st.dataframe(df_f, hide_index=True,
                                        use_container_width=True)

    # ── ABA 2: Mapa geografico ────────────────────────────────────────────
    with t2:
        st.subheader("Localizacao das Fazendas")

        foids = [f["owner_id"] for f in dados_faz]
        coords = listar_coords_fazendas(foids)
        coords_map = {c[0]: c for c in coords}

        # Fazendas sem coordenadas
        sem_coord = [f for f in dados_faz if f["owner_id"] not in coords_map]
        com_coord = [f for f in dados_faz if f["owner_id"] in coords_map]

        if sem_coord:
            st.info(
                f"{len(sem_coord)} fazenda(s) sem coordenadas cadastradas: "
                + ", ".join(f["nome"] for f in sem_coord)
            )

        if com_coord:
            # Montar dados para mapa
            import json
            map_data = []
            for f in com_coord:
                c = coords_map[f["owner_id"]]
                n_oc = sum(t[1] for t in f["por_tipo"])
                map_data.append({
                    "lat": c[1], "lon": c[2],
                    "nome": f["nome"],
                    "ativos": f["n_ativos"],
                    "ocorrencias": n_oc,
                    "taxa_mort": f["taxa_mort"],
                })
            df_map = pd.DataFrame(map_data)
            st.map(df_map, latitude="lat", longitude="lon",
                  size="ocorrencias", color="#FF4B4B")
            st.caption("Tamanho do ponto = numero de ocorrencias")
            st.dataframe(
                df_map[["nome","ativos","ocorrencias","taxa_mort"]].rename(
                    columns={"nome":"Fazenda","ativos":"Animais",
                             "ocorrencias":"Ocorrencias",
                             "taxa_mort":"Taxa Mort %"}
                ),
                use_container_width=True, hide_index=True
            )
        else:
            st.warning("Cadastre coordenadas das fazendas para ver o mapa.")

        # Form para cadastrar/atualizar coords
        st.divider()
        st.subheader("Cadastrar Coordenadas")
        faz_options = {f["nome"]: f["owner_id"] for f in dados_faz}
        with st.form("form_coords"):
            faz_sel = st.selectbox("Fazenda", list(faz_options.keys()))
            cc1, cc2 = st.columns(2)
            with cc1:
                lat = st.number_input("Latitude", value=-15.0,
                                     format="%.6f",
                                     help="Ex: -19.917 (negativo = Sul)")
                cidade = st.text_input("Cidade")
            with cc2:
                lon = st.number_input("Longitude", value=-47.0,
                                     format="%.6f",
                                     help="Ex: -43.934 (negativo = Oeste)")
                estado = st.text_input("Estado (UF)")
            if st.form_submit_button("Salvar Coordenadas", type="primary"):
                salvar_coords_fazenda(
                    faz_options[faz_sel], lat, lon, cidade, estado
                )
                st.success("Coordenadas salvas!")
                st.rerun()

    # ── ABA 3: Alertas cruzados ───────────────────────────────────────────
    with t3:
        st.subheader("Analise de Risco de Disseminacao")
        st.caption(
            "Doencas que aparecem em 2 ou mais fazendas "
            "simultaneamente indicam risco de disseminacao."
        )

        # Montar mapa de doencas por fazenda
        doencas_por_faz = {}
        for f in dados_faz:
            for tipo, cnt in f["por_tipo"]:
                if tipo not in doencas_por_faz:
                    doencas_por_faz[tipo] = []
                doencas_por_faz[tipo].append((f["nome"], cnt))

        alertas = {k: v for k, v in doencas_por_faz.items() if len(v) >= 2}
        sem_alerta = {k: v for k, v in doencas_por_faz.items() if len(v) < 2}

        if alertas:
            for tipo, fazendas in sorted(
                alertas.items(),
                key=lambda x: len(x[1]), reverse=True
            ):
                st.error(
                    f"⚠ **{tipo}** — presente em "
                    f"{len(fazendas)} fazendas: "
                    + ", ".join(f"{n} ({c} casos)" for n, c in fazendas)
                )
        else:
            st.info("Nenhuma doenca em comum entre fazendas. Bom sinal!")

        if sem_alerta:
            st.divider()
            st.caption("Ocorrencias isoladas (1 fazenda apenas):")
            for tipo, fazendas in sem_alerta.items():
                st.caption(f"• {tipo}: {fazendas[0][0]} ({fazendas[0][1]} casos)")


# ════════════════════════════════════════════════════════════════════════════
# TELA 13: INBOX — COMUNICACAO VET-FAZENDEIRO
# ════════════════════════════════════════════════════════════════════════════
def page_inbox(u):
    hdr("Mensagens", "Comunicacao",
        "Troca de mensagens entre veterinario e fazendeiro")

    # Contar nao lidas
    n_nl = contar_mensagens_nao_lidas(u["id"])
    if n_nl:
        st.warning(f"📬 {n_nl} mensagem(ns) nao lida(s)")

    t1, t2 = st.tabs([
        f"Caixa de Entrada ({n_nl} novas)" if n_nl else "Caixa de Entrada",
        "Enviar Mensagem"
    ])

    with t1:
        msgs = listar_mensagens(u["id"], caixa="entrada")
        if not msgs:
            st.info("Nenhuma mensagem recebida.")
        else:
            for msg in msgs[:30]:
                mid, rem_id, _, assunto, corpo, lida, dt, tipo = msg
                nome_rem = obter_nome_usuario(rem_id) or f"#{rem_id}"
                dt_fmt   = fmt_data(dt)
                icone    = "📬" if not lida else "📭"
                titulo   = f"{icone} {nome_rem} — {assunto or 'sem assunto'} | {dt_fmt}"

                with st.expander(titulo, expanded=not lida):
                    st.markdown(corpo)
                    if not lida:
                        marcar_mensagem_lida(mid)
                    # Responder
                    with st.form(f"form_resp_{mid}"):
                        resp = st.text_area(
                            "Responder", height=80,
                            key=f"resp_{mid}"
                        )
                        if st.form_submit_button("Enviar resposta"):
                            if resp:
                                enviar_mensagem(
                                    remetente_id=u["id"],
                                    destinatario_id=rem_id,
                                    corpo=resp,
                                    assunto=f"Re: {assunto or ''}",
                                    tipo="resposta"
                                )
                                st.success("Resposta enviada!")
                                st.rerun()

        st.divider()
        with st.expander("Mensagens enviadas"):
            enviadas = listar_mensagens(u["id"], caixa="enviadas")
            if not enviadas:
                st.info("Nenhuma mensagem enviada.")
            else:
                for msg in enviadas[:20]:
                    _, _, dest_id, assunto, corpo, _, dt, _ = msg
                    nome_dest = obter_nome_usuario(dest_id) or f"#{dest_id}"
                    dt_fmt    = fmt_data(dt)
                    st.caption(
                        f"📤 Para: {nome_dest} | "
                        f"{assunto or 'sem assunto'} | {dt_fmt}"
                    )

    with t2:
        st.caption(
            "Envie mensagens para fazendeiros ou veterinarios. "
            "Eles veem aqui e no painel de notificacoes."
        )

        # Montar lista de destinatarios
        if is_vet():
            # Vet envia para seus fazendeiros
            from database import listar_fazendas_do_vet
            foids = listar_fazendas_do_vet(u["id"])
            dest_opts = {
                obter_nome_usuario(fid) or f"#{fid}": fid
                for fid in foids
            }
        else:
            # Fazendeiro envia para vets que atendem sua fazenda
            oid = u.get("owner_id") or u["id"]
            dest_opts = {}
            try:
                with _conexao() as conn:
                    cur = conn.cursor()
                    p   = _ph()
                    cur.execute(
                        f"SELECT DISTINCT vet_id FROM visitas_tecnicas "
                        f"WHERE fazenda_owner_id={p}",
                        (oid,)
                    )
                    for row in cur.fetchall():
                        nome = obter_nome_usuario(row[0]) or f"#{row[0]}"
                        dest_opts[nome] = row[0]
            except Exception as _e:
                pass  # silenced

        if not dest_opts:
            st.warning(
                "Nenhum destinatario disponivel. "
                "O vet precisa ter agendado ao menos uma visita."
            )
        else:
            with st.form("form_nova_msg"):
                dest_sel = st.selectbox(
                    "Destinatario *", list(dest_opts.keys())
                )
                assunto_m = st.text_input(
                    "Assunto",
                    placeholder="Ex: Resultado do exame do BOI-001"
                )
                corpo_m = st.text_area(
                    "Mensagem *", height=150,
                    placeholder="Digite sua mensagem aqui..."
                )
                if st.form_submit_button("Enviar", type="primary"):
                    if not corpo_m:
                        st.error("Digite a mensagem.")
                    else:
                        enviar_mensagem(
                            remetente_id=u["id"],
                            destinatario_id=dest_opts[dest_sel],
                            corpo=corpo_m,
                            assunto=assunto_m or "",
                            tipo="mensagem"
                        )
                        st.success("Mensagem enviada!")
                        st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# TELA 14: CAMPANHAS DE VACINACAO
# ════════════════════════════════════════════════════════════════════════════
def page_campanhas_vacinacao(u):
    _requer_vet()
    hdr("Campanhas de Vacinacao", "Gestao por Safra",
        "Planeje e acompanhe campanhas de vacinacao em todas as fazendas")

    t1, t2, t3 = st.tabs(["Minhas Campanhas", "Criar Campanha", "Executar"])

    # ── ABA 1: Listar campanhas ───────────────────────────────────────────
    with t1:
        camps = listar_campanhas(u["id"])
        if not camps:
            st.info("Nenhuma campanha criada. Use a aba 'Criar Campanha'.")
        else:
            for camp in camps:
                (cid, _, nome_c, vacina_c, safra_c, dt_ini, dt_fim,
                 meta_c, stat_c, obs_c) = camp
                res = resumo_campanha(cid)
                pct = res["pct"]
                ic  = "✅" if stat_c == "encerrada"                       else "🟢" if pct >= meta_c                       else "🟡" if pct >= 50 else "🔴"
                with st.expander(
                    f"{ic} {nome_c} | {vacina_c} | Safra {safra_c} "
                    f"| {pct}% de cobertura"
                ):
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        st.markdown(f"**Vacina:** {vacina_c}")
                        st.markdown(f"**Safra:** {safra_c}")
                        st.markdown(
                            f"**Periodo:** "
                            f"{_fmt_dt(dt_ini)} a {_fmt_dt(dt_fim)}"
                        )
                        st.markdown(f"**Meta:** {meta_c}% de cobertura")
                    with cc2:
                        st.metric("Lotes", res["n_lotes"])
                        st.metric("Animais meta", res["meta"])
                        st.metric("Vacinados", res["vacinados"])
                        st.metric("Cobertura", f"{pct}%")

                    # Progress bar
                    st.progress(min(pct / 100, 1.0))

                    # Lotes da campanha
                    lotes_camp = listar_lotes_campanha(cid)
                    if lotes_camp:
                        df_lc = pd.DataFrame(lotes_camp, columns=[
                            "ID","CampID","LoteID","Nome",
                            "Meta","Vacinados","Status","Execucao"
                        ])
                        df_lc["Execucao"] = df_lc["Execucao"].apply(_fmt_dt)
                        df_lc["Cobertura %"] = df_lc.apply(
                            lambda r: f"{round(100*r['Vacinados']/max(1,r['Meta']),1)}%",
                            axis=1
                        )
                        st.dataframe(
                            df_lc[["Nome","Meta","Vacinados",
                                   "Cobertura %","Status","Execucao"]],
                            use_container_width=True, hide_index=True
                        )

                    if obs_c:
                        st.caption(f"Obs: {obs_c}")

    # ── ABA 2: Criar campanha ─────────────────────────────────────────────
    with t2:
        with st.form("form_criar_camp"):
            ca1, ca2 = st.columns(2)
            with ca1:
                nome_camp  = st.text_input(
                    "Nome da campanha *",
                    placeholder="Ex: Vacinacao Aftosa Safra 2026"
                )
                vacina_camp = st.text_input(
                    "Vacina *",
                    placeholder="Ex: Aftosa, Brucelose, Raiva"
                )
                safra_camp  = st.text_input(
                    "Safra *",
                    placeholder="Ex: 2026, 2025/2026"
                )
            with ca2:
                dt_ini_c = st.date_input("Data de inicio *",
                                        value=date.today())
                dt_fim_c = st.date_input("Data de termino *")
                meta_cob = st.number_input(
                    "Meta de cobertura (%)",
                    min_value=50, max_value=100,
                    value=100, step=5
                )
            obs_camp = st.text_area("Observacoes", height=68)

            if st.form_submit_button("Criar Campanha", type="primary"):
                if not nome_camp or not vacina_camp or not safra_camp:
                    st.error("Preencha nome, vacina e safra.")
                else:
                    cid = criar_campanha(
                        vet_id=u["id"],
                        nome=nome_camp, vacina=vacina_camp,
                        safra=safra_camp,
                        data_inicio=str(dt_ini_c),
                        data_fim=str(dt_fim_c),
                        meta_cobertura=float(meta_cob),
                        observacoes=obs_camp or ""
                    )
                    st.session_state["_camp_atual"] = cid
                    st.success(
                        f"Campanha #{cid} criada! "
                        f"Agora adicione os lotes na aba 'Executar'."
                    )
                    st.rerun()

    # ── ABA 3: Executar (adicionar lotes e registrar vacinados) ───────────
    with t3:
        camps_list = listar_campanhas(u["id"])
        if not camps_list:
            st.info("Crie uma campanha primeiro.")
            return

        dict_camps = {
            f"#{c[0]} - {c[2]} ({c[4]})": c[0]
            for c in camps_list
            if c[8] != "encerrada"
        }
        if not dict_camps:
            st.info("Nenhuma campanha ativa.")
            return

        camp_sel = st.selectbox(
            "Campanha", list(dict_camps.keys()), key="exec_camp"
        )
        cid_sel  = dict_camps[camp_sel]

        # Adicionar lote
        st.subheader("Adicionar Lote a Campanha")
        sel_fazenda_vet(key="vet_faz_camp")
        foid_c = st.session_state.get("_vet_foid")
        if foid_c:
            from database import listar_lotes
            lotes_c = listar_lotes(owner_id=foid_c)
            if lotes_c:
                dict_lc = {f"{l[1]}": l[0] for l in lotes_c}
                with st.form("form_add_lote_camp"):
                    lote_c_sel = st.selectbox(
                        "Lote", list(dict_lc.keys())
                    )
                    meta_c_an  = st.number_input(
                        "Meta de animais a vacinar",
                        min_value=1,
                        value=max(1, contar_animais_no_lote(dict_lc[lote_c_sel]))
                    )
                    if st.form_submit_button("Adicionar Lote"):
                        adicionar_lote_campanha(
                            cid_sel, dict_lc[lote_c_sel], int(meta_c_an)
                        )
                        toast_ok("Lote adicionado!")
                        st.rerun()

        # Registrar vacinados
        st.subheader("Registrar Vacinacao por Lote")
        lotes_camp = listar_lotes_campanha(cid_sel)
        pendentes  = [l for l in lotes_camp if l[6] == "pendente"]
        concluidos = [l for l in lotes_camp if l[6] == "concluido"]

        if not pendentes:
            toast_ok("Todos os lotes desta campanha estao concluidos!")

        # Botao de sincronizacao para lotes ja concluidos
        if concluidos:
            if st.button(
                "🔄 Sincronizar calendario e prontuarios",
                help="Garante que o calendario sanitario e os prontuarios "
                     "estejam atualizados para os lotes ja executados",
                type="secondary"
            ):
                total = 0
                for lc in concluidos:
                    dt_ex = str(lc[7]) if lc[7] and str(lc[7]) != "None" else None
                    n = sincronizar_campanha_executada(lc[0], dt_ex)
                    total += n
                if total:
                    st.success(
                        f"Sincronizado! {total} ocorrencia(s) criada(s) "
                        f"nos prontuarios. Calendário atualizado."
                    )
                else:
                    st.info("Calendario e prontuarios já estavam atualizados.")
                st.rerun()
        else:
            for lc in pendentes:
                (lcid, _, lid, nome_l, meta_l,
                 vac_l, stat_l, dt_ex) = lc
                with st.expander(
                    f"🔵 {nome_l} — Meta: {meta_l} animais"
                ):
                    with st.form(f"form_exec_{lcid}"):
                        n_vac = st.number_input(
                            "Animais vacinados *",
                            min_value=0, max_value=int(meta_l)*2,
                            value=int(meta_l), step=1
                        )
                        dt_ex_c = st.date_input(
                            "Data de execucao",
                            value=date.today()
                        )
                        if st.form_submit_button(
                            "Registrar", type="primary"
                        ):
                            registrar_vacinacao_campanha(
                                lcid, n_vac, str(dt_ex_c)
                            )
                            toast_ok(
                                f"{n_vac} animais vacinados em {nome_l}!"
                            )
                            st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# TELA 15: HISTORICO CLINICO PDF
# ════════════════════════════════════════════════════════════════════════════
def page_historico_clinico_pdf(u):
    _requer_vet()
    hdr("Historico Clinico PDF", "Documentacao",
        "Exporte o historico completo do animal em PDF com cabecalho veterinario")

    crmv = _crmv_atual(u)
    sel_fazenda_vet(key="vet_faz_hcpdf")
    foid = st.session_state.get("_vet_foid")
    if not foid:
        st.warning("Selecione uma fazenda.")
        return

    from database import listar_lotes
    lotes_pdf = listar_lotes(owner_id=foid)
    if not lotes_pdf:
        st.warning("Nenhum lote nesta fazenda.")
        return

    dict_lp = {f"{l[1]}": l[0] for l in lotes_pdf}
    lote_p  = st.selectbox("Lote", list(dict_lp.keys()), key="hc_lote")
    animais_p = listar_animais_por_lote(dict_lp[lote_p])

    if not animais_p:
        st.warning("Nenhum animal neste lote.")
        return

    dict_ap = {f"{a[1]}": a[0] for a in animais_p}
    an_p    = st.selectbox("Animal", list(dict_ap.keys()), key="hc_anim")
    aid     = dict_ap[an_p]

    # Preview dos dados
    dados = historico_clinico_animal(aid)
    animal = dados.get("animal", {})

    col_i, col_b = st.columns(2)
    with col_i:
        st.markdown(f"**Brinco:** {animal.get('brinco','-')}")
        st.markdown(f"**Raca:** {animal.get('raca','-')}")
        st.markdown(f"**Sexo:** {animal.get('sexo','-')}")
    with col_b:
        st.metric("Pesagens", len(dados.get("pesagens",[])))
        st.metric("Ocorrencias", len(dados.get("ocorrencias",[])))
        st.metric("Exames", len(dados.get("exames",[])))

    st.divider()
    if st.button("Gerar PDF do Historico Clinico",
                type="primary", use_container_width=True):
        try:
            from pdf_vet import gerar_pdf_historico_animal
            pdf_bytes = gerar_pdf_historico_animal(
                dados,
                nome_vet=u.get("nome",""),
                crmv=crmv
            )
            st.download_button(
                label=f"Baixar historico_{an_p}.pdf",
                data=pdf_bytes,
                file_name=f"historico_{an_p.replace(' ','_')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"Erro ao gerar PDF: {e}")


# ════════════════════════════════════════════════════════════════════════════
# TELA 16: DASHBOARD DE PRODUTIVIDADE DO VET
# ════════════════════════════════════════════════════════════════════════════
def page_dashboard_produtividade(u):
    _requer_vet()
    hdr("Meu Dashboard", "Produtividade Profissional",
        "Metricas de desempenho e resumo da sua atuacao")

    from datetime import date
    hoje  = date.today()
    p     = _ph()

    # Coletar metricas
    visitas  = listar_visitas(vet_id=u["id"])
    receitas = listar_receitas(vet_id=u["id"])
    mons_at  = listar_monitoramentos(vet_id=u["id"], apenas_ativos=True)
    mons_enc = listar_monitoramentos(vet_id=u["id"], apenas_ativos=False)
    res_fin  = resumo_financeiro_vet(u["id"])

    from database import listar_fazendas_do_vet
    n_faz    = len(listar_fazendas_do_vet(u["id"]))
    n_vis_r  = len([v for v in visitas if v[6] == "realizada"])
    n_vis_a  = len([v for v in visitas if v[6] == "agendada"])
    n_rec    = len(receitas)
    n_mon_at = len(mons_at)
    n_mon_enc = len([m for m in mons_enc if m["status"] == "encerrado"])
    taxa_res  = round(
        100 * n_mon_enc / max(1, n_mon_at + n_mon_enc), 1
    )

    # Cards principais
    st.subheader("Resumo Geral")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Fazendas atendidas",  n_faz)
    c2.metric("Visitas realizadas",  n_vis_r,
             delta=f"{n_vis_a} agendadas")
    c3.metric("Receitas emitidas",   n_rec)
    c4.metric("Taxa resolucao",      f"{taxa_res}%",
             help="Monitoramentos encerrados / total")

    st.divider()
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("A receber",       fmt_brl(res_fin['pendente']))
    c6.metric("Recebido no mes", fmt_brl(res_fin['pago']))
    c7.metric("Monitoramentos ativos", n_mon_at)
    c8.metric("CRMV", obter_crmv_usuario(u["id"]) or "Nao cadastrado")

    # Grafico de visitas por mes
    if visitas:
        st.divider()
        st.subheader("Visitas por Mes")
        from collections import Counter
        meses = Counter(
            str(v[3])[:7]
            for v in visitas if v[6] == "realizada"
        )
        if meses:
            df_vis = pd.DataFrame(
                sorted(meses.items()),
                columns=["Mes", "Visitas"]
            )
            safe_bar_chart(df_vis.set_index("Mes"))

    # Onboarding checklist
    st.divider()
    st.subheader("Checklist de Configuracao")
    checks = [
        ("CRMV cadastrado",          bool(obter_crmv_usuario(u["id"]))),
        ("Pelo menos 1 visita",       n_vis_r > 0),
        ("Protocolo criado",          len(listar_protocolos(u["id"])) > 0),
        ("Primeiro receituario",      n_rec > 0),
        ("Coordenadas de fazendas",   bool(listar_coords_fazendas(
            listar_fazendas_do_vet(u["id"])
        ))),
    ]
    for label, ok in checks:
        ic = "✅" if ok else "⬜"
        st.markdown(f"{ic} {label}")

    pct_conf = round(100 * sum(ok for _, ok in checks) / len(checks))
    st.progress(pct_conf / 100)
    st.caption(f"Configuracao: {pct_conf}% completa")
