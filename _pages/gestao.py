# pages/gestao.py -- Telas: Calendario Sanitario, Estoque Medicamentos, Controle Reprodutivo, Mapa Piquetes, Workspace do Lote, Prontuario Animal

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
        import streamlit as _st, pandas as _pd
        try: _st.bar_chart(_pd.DataFrame(df))
        except: pass
    def safe_line_chart(df, **k):
        import streamlit as _st, pandas as _pd
        try: _st.line_chart(_pd.DataFrame(df))
        except: pass
    def toast_ok(m): import streamlit as _st; _st.success(f"✅ {m}")
    def toast_erro(m): import streamlit as _st; _st.error(f"❌ {m}")
    def empty_state(m, **k): import streamlit as _st; _st.info(m)
try:
    from ux_helpers import (aplicar_css_global, toast_ok, toast_erro,
                            toast_aviso, empty_state, confirmar_acao,
                            erro_com_acao, fmt_brl, fmt_data, fmt_data_hora,
                            tabela_paginada, paginar_dataframe,
                            safe_line_chart, safe_bar_chart)
except ImportError:
    def aplicar_css_global(): pass
    def toast_ok(m): st.success(m)
    def toast_erro(m): st.error(m)
    def toast_aviso(m): st.warning(m)
    def empty_state(t, d, **k): st.info(f"{t} — {d}"); return False
    def confirmar_acao(m, k, **kw): return st.button("Confirmar", key=k)
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
from datetime import datetime, date, timedelta
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
    sel_fazenda_vet,
    listar_lotes_vet_filtrado,
)

def hdr(titulo, sub="", desc=""):
    st.title(titulo)
    if sub: st.caption(f"{sub} - {desc}" if desc else sub)
    st.divider()

def page_calendario_sanitario(
u):
    aplicar_css_global()
    hdr("Calendario Sanitario", "Vacinas e Medicacoes", "Agenda de vacinas e alertas")

    if is_vet():
        sel_fazenda_vet(key="vet_faz_cal")

    lotes = listar_lotes_usuario()
    if not lotes:
        st.warning("Nenhum lote cadastrado.")
        return

    t1, t2, t3 = st.tabs(["Agenda", "Agendar", "Confirmar"])

    # ── ABA 1: Agenda ─────────────────────────────────────────────────────────
    with t1:
        st.caption("Vacinas agendadas por fazendeiro e veterinario aparecem aqui.")
        d = {"Todos": None, **{f"{l[1]} (ID {l[0]})": l[0] for l in lotes}}
        f_sel = st.selectbox("Filtrar por lote", list(d.keys()), key="cal_f")

        if d[f_sel] is None:
            vs = []
            for lote in lotes:
                vs.extend(listar_vacinas_agenda(lote[0]))
        else:
            vs = listar_vacinas_agenda(d[f_sel])

        if vs:
            import pandas as pd
            df_v = pd.DataFrame(vs, columns=[
                "ID","Lote","Vacina","Previsto","Realizado","Status","Obs"
            ])
            for col in ["Previsto","Realizado"]:
                df_v[col] = df_v[col].apply(lambda x:
                    fmt_data(x)
                    if x and str(x) not in ("None","") else ""
                )
            df_v[""] = df_v["Status"].apply(
                lambda s: "✅" if s == "realizado" else "⏳"
            )
            st.dataframe(
                df_v[["","Lote","Vacina","Previsto","Realizado","Status","Obs"]],
                use_container_width=True, hide_index=True
            )
        else:
            st.info("Nenhuma vacina agendada.")

    # ── ABA 2: Agendar ────────────────────────────────────────────────────────
    with t2:
        dict_l2 = {f"{l[1]}": l[0] for l in lotes}
        lote_ag    = st.selectbox("Lote", list(dict_l2.keys()), key="cal_ag_lote")
        lote_id_ag = dict_l2[lote_ag]

        # Alvo: lote todo ou animal especifico
        alvo = st.radio(
            "Aplicar em:",
            ["Lote inteiro", "Animal especifico"],
            horizontal=True, key="cal_ag_alvo"
        )
        animal_id_ag = None
        if alvo == "Animal especifico":
            animais_ag = listar_animais_por_lote(lote_id_ag)
            if not animais_ag:
                st.warning("Nenhum animal neste lote.")
            else:
                dict_an = {f"{a[1]}": a[0] for a in animais_ag}
                an_sel  = st.selectbox("Animal", list(dict_an.keys()), key="cal_ag_animal")
                animal_id_ag = dict_an[an_sel]

        # Medicamentos disponiveis do usuario logado
        _oid_med  = u.get("owner_id") or u["id"]
        meds_disp = listar_medicamentos(owner_id=_oid_med)
        dict_meds = {"-- Sem vinculo de estoque --": None}
        dict_meds.update({f"{m[1]} ({m[3]:.0f} {m[2]})": m[0] for m in meds_disp})

        with st.form("form_agendar_vac"):
            c1, c2 = st.columns(2)
            with c1:
                nome_vac  = st.text_input("Nome da vacina *",
                                          placeholder="Ex: Aftosa, Brucelose")
                data_prev = st.date_input("Data prevista *")
                med_sel   = st.selectbox(
                    "Vincular ao medicamento/estoque",
                    list(dict_meds.keys()),
                    help="Ao confirmar, da baixa automatica neste estoque"
                )
            with c2:
                qtd_dose = st.number_input(
                    "Dose por animal (unidade/mL)", min_value=0.0,
                    value=0.0, step=0.5,
                    help="Quantidade descontada do estoque ao confirmar"
                )
                obs_vac = st.text_area("Observacoes", height=80)

            if st.form_submit_button("Agendar vacina", type="primary"):
                if not nome_vac:
                    st.error("Informe o nome da vacina.")
                elif alvo == "Animal especifico" and not animal_id_ag:
                    st.error("Selecione o animal.")
                else:
                    med_id_sel = dict_meds[med_sel]
                    adicionar_vacina_agenda(
                        lote_id_ag, nome_vac, str(data_prev), obs_vac,
                        medicamento_id=med_id_sel,
                        quantidade_dose=qtd_dose,
                        agendado_por=u["id"],
                        animal_id=animal_id_ag
                    )
                    registrar_auditoria(u["id"], "agendar_vacina",
                                       "vacinas_agenda", lote_id_ag, nome_vac)
                    limpar_cache()
                    _alvo_str = "lote inteiro" if not animal_id_ag else "animal especifico"
                    _est_str  = f"vinculada a {med_sel}" if med_id_sel else "sem vinculo de estoque"
                    st.success(
                        f"Vacina **{nome_vac}** agendada para "
                        f"{data_prev} "
                        f"({_alvo_str} | {_est_str})!"
                    )
                    st.rerun()

    # ── ABA 3: Confirmar ──────────────────────────────────────────────────────
    with t3:
        st.caption("Qualquer vacina pendente pode ser confirmada aqui, "
                   "independente de quem agendou.")
        dict_l3    = {f"{l[1]}": l[0] for l in lotes}
        lote_cf    = st.selectbox("Lote", list(dict_l3.keys()), key="cal_cf_lote")
        lote_id_cf = dict_l3[lote_cf]

        pendentes = [v for v in listar_vacinas_agenda(lote_id_cf)
                     if v[5] == "pendente"]

        if not pendentes:
            empty_state("Vacinas em dia", "Nenhuma vacina pendente no momento.", icone="✅")
        else:
            st.warning(f"{len(pendentes)} vacina(s) pendente(s)")
            for vac in pendentes:
                vid, _, nome_v, prev_v, _, _, obs_v = vac
                _prev_fmt = fmt_data(prev_v)

                # Descobrir se a vacina foi agendada para animal especifico
                # (buscar animal_id da vacina, se existir a coluna)
                _animal_orig = None
                try:
                    from database import _conexao as _cx, _ph as _pp, _usar_postgres as _up
                    _p2 = _pp()
                    with _cx() as _conn:
                        _cur = _conn.cursor()
                        if _up():
                            _cur.execute(
                                f"SELECT animal_id FROM vacinas_agenda WHERE id={_p2}",
                                (vid,)
                            )
                            _row = _cur.fetchone()
                            _animal_orig = _row[0] if _row else None
                except Exception:
                    _animal_orig = None

                with st.expander(
                    f"💉 {nome_v} — prevista {_prev_fmt}"
                    + (" 🐄 animal específico" if _animal_orig else " 🐄 lote inteiro")
                ):
                    # Alvo da confirmacao
                    animais_lote_cf = listar_animais_por_lote(lote_id_cf)

                    if _animal_orig:
                        # Ja tem animal definido — mostrar info
                        _an_nome = next(
                            (a[1] for a in animais_lote_cf if a[0] == _animal_orig),
                            f"Animal #{_animal_orig}"
                        )
                        st.info(f"Agendada para: **{_an_nome}**")
                        alvo_cf      = "Animal especifico"
                        animal_id_cf = _animal_orig
                    else:
                        # Permite redefinir o alvo na confirmacao
                        alvo_cf = st.radio(
                            "Confirmar aplicacao em:",
                            ["Lote inteiro", "Animal especifico"],
                            horizontal=True, key=f"cf_alvo_{vid}"
                        )
                        animal_id_cf = None
                        if alvo_cf == "Animal especifico":
                            if not animais_lote_cf:
                                st.warning("Nenhum animal no lote.")
                            else:
                                dict_an_cf = {f"{a[1]}": a[0] for a in animais_lote_cf}
                                an_cf_sel  = st.selectbox(
                                    "Animal", list(dict_an_cf.keys()),
                                    key=f"cf_animal_{vid}"
                                )
                                animal_id_cf = dict_an_cf[an_cf_sel]

                    cf1, cf2 = st.columns(2)
                    with cf1:
                        from datetime import date as _date
                        data_real = st.date_input(
                            "Data de aplicacao",
                            value=_date.today(),
                            key=f"cf_data_{vid}"
                        )
                    with cf2:
                        obs_real = st.text_input(
                            "Observacoes adicionais",
                            value=obs_v or "",
                            key=f"cf_obs_{vid}"
                        )

                    _alvo_desc = (
                        f"animal especifico" if alvo_cf == "Animal especifico"
                        else "lote inteiro"
                    )
                    st.caption(
                        f"Confirmar para: **{_alvo_desc}** — "
                        f"baixa no estoque vinculado + vacinacao no prontuario."
                    )

                    if st.button(
                        f"Confirmar aplicacao de {nome_v}",
                        key=f"cf_btn_{vid}", type="primary"
                    ):
                        if alvo_cf == "Animal especifico" and not animal_id_cf:
                            st.error("Selecione o animal.")
                        else:
                            # Passar animal_id_cf para registrar_vacina_realizada
                            # sobrescreve o animal_id original se usuario redefiniu
                            registrar_vacina_realizada(
                                vid, str(data_real),
                                confirmado_por=u["id"],
                                obs_extra=obs_real,
                                animal_id_override=animal_id_cf
                            )
                            registrar_auditoria(
                                u["id"], "confirmar_vacina",
                                "vacinas_agenda", vid, nome_v
                            )
                            limpar_cache()
                            st.success(
                                f"**{nome_v}** confirmada para {_alvo_desc}! "
                                f"Prontuario atualizado e estoque descontado."
                            )
                            st.rerun()


def page_estoque_medicamentos(u):
    hdr("Estoque Medicamentos", "Controle de Medicamentos", "Estoque, validade e uso")
    # Isolamento: cada usuario ve somente seus proprios medicamentos
    # Para vet: usa o id do proprio vet (medicamentos dele)
    # Para fazendeiro: usa owner_id (que e igual ao id)
    _oid = u.get("owner_id") or u["id"]
    if not _oid:
        _oid = u["id"]

    if is_vet():
        sel_fazenda_vet(key="vet_faz_est")

    t1, t2, t3, t4 = st.tabs(["Estoque", "Cadastrar", "Registrar Uso", "Historico de Uso"])

    # ── ABA 1: Estoque ────────────────────────────────────────────────────────
    with t1:
        meds  = listar_medicamentos(owner_id=_oid)
        crits = listar_medicamentos_criticos(owner_id=_oid)

        def _fmt_data_med(d):
            if not d: return "—"
            try:
                from datetime import datetime as _dtm
                meses = {1:"Jan",2:"Fev",3:"Mar",4:"Abr",5:"Mai",6:"Jun",
                         7:"Jul",8:"Ago",9:"Set",10:"Out",11:"Nov",12:"Dez"}
                if isinstance(d, str): d = _dtm.strptime(str(d)[:10], "%Y-%m-%d").date()
                return f"{d.day:02d} {meses[d.month]} {d.year}"
            except: return str(d)

        def _fmt_brl_med(v):
            if not v: return "—"
            try:
                i, dec = f"{float(v):,.2f}".split(".")
                return f"R$ {i.replace(',','.')},{dec}"
            except: return "—"

        if meds:
            _valor_total = sum((m[3] or 0) * (m[6] or 0) for m in meds)
            c1, c2, c3 = st.columns(3)
            c1.metric("Itens no estoque", len(meds))
            c2.metric("Valor total",      _fmt_brl_med(_valor_total))
            c3.metric("Itens criticos",   len(crits))

            if crits:
                st.divider()
                st.markdown("**Alertas de estoque:**")
                for m in crits:
                    mot = "estoque baixo" if (m[3] or 0) <= (m[4] or 0) else f"vence em {_fmt_data_med(m[5])}"
                    st.error(f"⚠ **{m[1]}** — {m[3]:.1f} {m[2]} ({mot})")

            st.divider()
            for med in meds:
                mid, mnome, munid = med[0], med[1], med[2]
                mestq, mmin, mval, mcusto = med[3], med[4], med[5], med[6]
                _status_icon = "🔴" if (mestq or 0) <= (mmin or 0) else "🟢"
                with st.expander(f"{_status_icon} {mnome} — {mestq:.1f} {munid}"):
                    e1, e2, e3, e4 = st.columns(4)
                    e1.metric("Estoque atual",  f"{mestq:.1f} {munid}".replace(".",","))
                    e2.metric("Estoque minimo", f"{(mmin or 0):.1f} {munid}".replace(".",","))
                    e3.metric("Validade",       _fmt_data_med(mval))
                    e4.metric("Custo/unidade",  _fmt_brl_med(mcusto))
        else:
            empty_state("Estoque limpo", "Nenhum medicamento em alerta no momento.", icone="💊")

    # ── ABA 2: Cadastrar ─────────────────────────────────────────────────────
    with t2:
        st.subheader("Cadastrar medicamento")
        with st.form("form_med"):
            mn1, mn2 = st.columns(2)
            with mn1:
                nome_md = st.text_input("Nome *", placeholder="Ex: Ivermectina 1%")
                unid_md = st.selectbox("Unidade", ["dose","mL","g","comprimido","frasco","kg","L"])
                estq_md = st.number_input("Estoque inicial", 0.0, step=1.0)
            with mn2:
                emin_md = st.number_input("Estoque minimo (alerta)", 0.0, step=1.0)
                val_md  = st.date_input("Validade")
                cust_md = st.number_input("Custo unitario (R$)", 0.0, step=0.01)
            obs_md = st.text_area("Observacao (opcional)")
            if st.form_submit_button("Cadastrar medicamento", type="primary"):
                if nome_md:
                    adicionar_medicamento(nome_md, unid_md, estq_md, emin_md,
                                         str(val_md), cust_md, owner_id=_oid)
                    registrar_auditoria(u["id"], "cad_medicamento", "medicamentos", 0, nome_md)
                    toast_ok("Medicamento '{nome_md}' cadastrado!")
                    st.rerun()
                else:
                    st.error("Informe o nome do medicamento.")

    # ── ABA 3: Registrar Uso ─────────────────────────────────────────────────
    with t3:
        st.subheader("Registrar uso de medicamento")
        st.caption("O estoque sera automaticamente descontado apos o registro.")
        meds_uso = listar_medicamentos(owner_id=_oid)
        lotes    = listar_lotes_usuario()
        if not meds_uso:
            st.warning("Cadastre medicamentos primeiro (aba Cadastrar).")
        elif not lotes:
            st.warning("Cadastre lotes e animais primeiro.")
        else:
            dict_md = {f"{m[1]} — {m[3]:.1f} {m[2]} disponiveis": m[0] for m in meds_uso}
            dict_l  = {f"{l[1]}": l[0] for l in lotes}

            col_l, col_a = st.columns(2)
            with col_l:
                lote_sel = st.selectbox("Lote", list(dict_l.keys()), key="uso_lote")
            animais_u = listar_animais_por_lote(dict_l[lote_sel])
            dict_au   = {f"{a[1]}": a[0] for a in animais_u}
            with col_a:
                anim_sel = st.selectbox("Animal", list(dict_au.keys()) if dict_au else ["--"], key="uso_anim")

            with st.form("form_uso_md"):
                u1, u2 = st.columns(2)
                with u1:
                    med_s = st.selectbox("Medicamento", list(dict_md.keys()))
                    qtd_u = st.number_input("Quantidade aplicada", 0.01, step=0.5)
                with u2:
                    data_u = st.date_input("Data de aplicacao")
                    obs_u  = st.text_input("Observacao (lote, dose, via)", placeholder="Ex: dose unica, IM")

                if st.form_submit_button("Registrar uso e dar baixa no estoque", type="primary"):
                    if dict_au and anim_sel != "--":
                        _mid_sel = dict_md[med_s]
                        # Verificar estoque suficiente
                        _med_info = next((m for m in meds_uso if m[0] == _mid_sel), None)
                        if _med_info and _med_info[3] < qtd_u:
                            st.error(f"Estoque insuficiente: {_med_info[3]:.1f} {_med_info[2]} disponivel, "
                                     f"tentou usar {qtd_u:.1f}.")
                        else:
                            registrar_uso_medicamento(_mid_sel, dict_au[anim_sel], str(data_u), qtd_u)
                            registrar_auditoria(u["id"], "uso_medicamento", "medicamentos",
                                               _mid_sel, f"{qtd_u} unidades")
                            toast_ok(f"Uso registrado! Estoque de '{med_s.split(' — ')[0]}' "
                                      f"atualizado: -{qtd_u:.1f} unidades.")
                            st.rerun()
                    else:
                        st.error("Selecione um animal valido.")

    # ── ABA 4: Historico ─────────────────────────────────────────────────────
    with t4:
        st.subheader("Historico de uso")
        meds_hist = listar_medicamentos(owner_id=_oid)
        if not meds_hist:
            empty_state("Estoque limpo", "Nenhum medicamento em alerta no momento.", icone="💊")
        else:
            _ids_meds = [m[0] for m in meds_hist]
            # Buscar usos recentes via query direta
            try:
                from database import _conexao as _cn, _ph as _phf
                with _cn() as conn:
                    cur = conn.cursor()
                    _placeholders = ','.join([_phf()]*len(_ids_meds))
                    cur.execute(
                        f"SELECT m.nome, a.identificacao, mu.data_uso, mu.quantidade "
                        f"FROM medicamentos_uso mu "
                        f"JOIN medicamentos m ON m.id=mu.medicamento_id "
                        f"JOIN animais a ON a.id=mu.animal_id "
                        f"WHERE m.owner_id={_phf()} "
                        f"ORDER BY mu.data_uso DESC LIMIT 100",
                        (_oid,)
                    )
                    usos = cur.fetchall()
                if usos:
                    _rows_hist = []
                    for _uh in usos:
                        _rows_hist.append({
                            "Medicamento": _uh[0],
                            "Animal":      _uh[1],
                            "Data":        _fmt_data_med(_uh[2]),
                            "Quantidade":  f"{float(_uh[3]):.1f}".replace('.',','),
                        })
                    st.dataframe(pd.DataFrame(_rows_hist), use_container_width=True, hide_index=True)
                else:
                    st.info("Nenhum uso registrado ainda.")
            except Exception as e:
                st.warning(f"Erro ao carregar historico: {e}")

    # ============================================================
    # CONTROLE REPRODUTIVO
    # ============================================================


def page_controle_reprodutivo(u):
    parto = listar_partos_previstos(owner_id=owner_id())
    hdr("Controle Reprodutivo", "Reproducao", "IATF, diagnostico, prenhez e partos")
    t1,t2,t3,t4 = st.tabs(["Indicadores","Registrar","Diagnostico","Partos"])
    with t1:
        if is_vet():
            sel_fazenda_vet(key="vet_faz_reprod")
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
                    toast_ok("Cobertura registrada!"); st.rerun()
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
                            toast_ok("Atualizado!"); st.rerun()
                else: st.info("Sem registros reprodutivos.")
    with t4:
        partos = listar_partos_previstos()
        if partos:
            df_p = pd.DataFrame(partos, columns=["ID","Animal","Lote","Parto Previsto","Tipo"])
            st.dataframe(df_p, use_container_width=True)
        else: st.info("Nenhum parto previsto nos proximos 30 dias.")

    # ============================================================
    # MAPA PIQUETES
    # ============================================================


def page_mapa_piquetes(u):
    hdr("Mapa Piquetes", "Pastagens e Piquetes", "Alocacao de lotes e historico")
    if is_vet():
        sel_fazenda_vet(key="vet_faz_piq")
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
                    toast_ok("Piquete cadastrado!"); st.rerun()
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


# Cache de sessão para dados do workspace (evita re-queries a cada rerender)
def _ws_cache_key(lote_id, fn_name):
    """Chave de cache por lote + função."""
    return f"_ws_cache_{lote_id}_{fn_name}"

def _ws_get(lote_id, fn_name, fn_call, ttl=30):
    """Busca do cache de sessão ou executa a query."""
    import time
    key     = _ws_cache_key(lote_id, fn_name)
    key_ts  = key + "_ts"
    now     = time.time()
    if (key in st.session_state
            and key_ts in st.session_state
            and now - st.session_state[key_ts] < ttl):
        return st.session_state[key]
    result = fn_call()
    st.session_state[key]    = result
    st.session_state[key_ts] = now
    return result


def page_workspace_do_lote(u):
    _h1, _h2 = st.columns([3,1])
    with _h1:
        hdr("Workspace do Lote", "Visao Completa", "Tudo sobre o lote em um lugar so")
    with _h2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🖨️ Imprimir relatório",
                     key="btn_print_ws",
                     help="Ctrl+P ou ⌘+P para imprimir esta tela"):
            st.info("Use **Ctrl+P** (Windows) ou **⌘+P** (Mac) "
                    "para imprimir ou salvar como PDF.")

    if is_vet():
        sel_fazenda_vet(key="vet_faz_ws")

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
            animais     = _ws_get(lid, "animais_lote", lambda: listar_animais_por_lote(lid), ttl=30),
            mort        = taxa_mortalidade_lote(lid),
            gmds_map    = _ws_get(lid, "gmds_lote", lambda: calcular_gmds_lote(lid), ttl=120),
            insights    = gerar_insights_lote(lid),
            gtas        = listar_gta(lid),
            movs        = listar_movimentacoes(lote_id=lid),
            vacs        = listar_vacinas_agenda(lid),
            plote       = _ws_get(lid, "pesagens_lote", lambda: listar_pesagens_lote(lid), ttl=60),
            todas_ocs   = _ws_get(lid, "ocorrencias_todos", lambda: listar_ocorrencias_todos_animais(lid), ttl=60),
            vendas      = listar_vendas_lote(lid),
            scores      = _ws_get(lid, "scores_lote", lambda: calcular_scores_lote(lid), ttl=120),
            cont_status = contagem_status_animais(lid),
        )

    try:
        _ws = _ws_dados(lote_ws_id)
        lote_ws        = _ws['lote']
        lote_ws_status = _ws['status']
        rs_ws          = _ws['rs']
        animais_ws     = _ws['animais']
        mort_ws        = _ws['mort']
    except Exception as _e_ws:
        st.error("⚠️ Erro temporário ao carregar os dados do lote. "
                 "Aguarde alguns segundos e tente novamente.")
        st.caption(f"Detalhe técnico: {_e_ws}")
        st.stop()
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
        dict(titulo="Custo Sanitario",   valor=fmt_brl(rs_ws['custo_sanitario']),
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
                # Formatar data: 2026-05-31 → 31 de maio de 2026
                _dt_ent = lote_ws[3] or ""
                try:
                    from datetime import date as _dt_cls
                    _meses_pt = {1:"janeiro",2:"fevereiro",3:"março",
                                 4:"abril",5:"maio",6:"junho",
                                 7:"julho",8:"agosto",9:"setembro",
                                 10:"outubro",11:"novembro",12:"dezembro"}
                    _d = _dt_cls.fromisoformat(str(_dt_ent)[:10])
                    _dt_fmt = f"{_d.day} de {_meses_pt[_d.month]} de {_d.year}"
                except Exception:
                    _dt_fmt = str(_dt_ent)

                # Formatar preço: 1250.0 → R$ 1.250,00
                _preco_raw = lote_ws[9] if len(lote_ws) > 9 else 0
                try:
                    _preco_fmt = f"R$ {float(_preco_raw or 0):,.2f}".replace(",","X").replace(".",",").replace("X",".")
                except Exception:
                    _preco_fmt = "R$ 0,00"

                st.markdown(f"**Data de entrada:** {_dt_fmt}")
                st.write(f"**Transportadora:** {lote_ws[6] or 'Nao informada'}")
                st.write(f"**Descricao:** {lote_ws[2] or 'Sem descricao'}")
                st.markdown(f"**Preço por animal:** {_preco_fmt}")

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
        # ── PESAGEM POR VOZ ───────────────────────────────────────────────
        _animais_lote_voz = listar_animais_por_lote(lote_ws_id)
        _mapa_voz = {
            a[1].upper(): a[0]
            for a in (_animais_lote_voz or [])
        }

        # Parser
        def _parse_voz(texto):
            import re as _r
            t = _r.sub(
                r'(peso|kg|quilo[sg]?|quilograma[sg]?)',
                ' ', texto.lower()
            )
            t = _r.sub(r'\s+', ' ', t).strip()
            nums = _r.findall(r'\d+(?:[.,]\d+)?', t)
            floats = [float(n.replace(',', '.')) for n in nums]
            grandes = [v for v in floats if v >= 50]
            peso = grandes[-1] if grandes else (floats[-1] if floats else None)
            pequenos = [n for n, v in zip(nums, floats)
                        if v != peso and v < 50]
            animal = pequenos[0].zfill(2) if pequenos else None
            if animal and _mapa_voz:
                _id = animal.upper()
                if _id not in _mapa_voz:
                    for _v in [_id, _id.zfill(2), _id.lstrip('0') or _id]:
                        if _v in _mapa_voz:
                            animal = _v
                            break
                    else:
                        for _k in _mapa_voz:
                            if _id in _k or _k in _id:
                                animal = _k
                                break
            return {"animal": animal, "peso": peso}

        # Componente de voz com botão "Confirmar transcrição"
        import streamlit.components.v1 as _stc

        _html_voz = """
<style>
#bv{display:flex;align-items:center;justify-content:center;gap:12px;
  background:#1B4332;color:#F5F0E8;border:none;border-radius:12px;
  padding:14px 24px;font-size:16px;font-weight:600;cursor:pointer;
  width:100%;margin-bottom:8px;transition:all .2s;
  box-shadow:0 4px 12px rgba(27,67,50,.35);}
#bv:hover{background:#2D6A4F;transform:translateY(-1px)}
#bv.g{background:#E24B4A;animation:pu 1.1s infinite}
@keyframes pu{0%,100%{box-shadow:0 4px 12px rgba(226,75,74,.4)}
  50%{box-shadow:0 8px 28px rgba(226,75,74,.75)}}
#sv{font-size:12px;color:#6B7280;text-align:center;min-height:16px;margin-bottom:6px}
#rv{display:none;background:#E8F5EE;border:2px solid #40916C;border-radius:8px;
  padding:12px 14px;font-size:15px;font-weight:600;color:#1B4332;margin-bottom:8px;
  word-break:break-word}
#bc{display:none;background:#40916C;color:white;border:none;border-radius:8px;
  padding:10px 20px;font-size:14px;font-weight:600;cursor:pointer;width:100%;
  margin-top:4px}
#bc:hover{background:#2D6A4F}
</style>

<button id="bv" onclick="tv()">🎤&nbsp;&nbsp;Registrar pesagem por voz</button>
<div id="sv">Clique e fale o número do animal e o peso</div>
<div id="rv"></div>
<button id="bc" onclick="confirmar()">✅ Usar esta transcrição</button>

<script>
var rc=null,at=false,txt='';
function tv(){at?pa():ini();}

function ini(){
  var SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SR){document.getElementById('sv').textContent='⚠️ Use Chrome ou Edge';return;}
  rc=new SR();rc.lang='pt-BR';rc.continuous=false;rc.interimResults=true;
  rc.onstart=function(){
    at=true;
    document.getElementById('bv').className='g';
    document.getElementById('bv').innerHTML='⏹&nbsp;&nbsp;Parar';
    document.getElementById('sv').textContent='🎙️ Ouvindo...';
    document.getElementById('bc').style.display='none';
  };
  rc.onresult=function(e){
    txt='';
    for(var i=e.resultIndex;i<e.results.length;i++) txt+=e.results[i][0].transcript;
    document.getElementById('rv').style.display='block';
    document.getElementById('rv').textContent='📝 '+txt;
    if(e.results[e.results.length-1].isFinal){
      document.getElementById('sv').textContent='✅ Transcrição concluída';
      document.getElementById('bc').style.display='block';
      pa();
    }
  };
  rc.onerror=function(e){
    var m={'not-allowed':'❌ Permissão negada','no-speech':'⚠️ Sem fala detectada'};
    document.getElementById('sv').textContent=m[e.error]||'❌ Erro: '+e.error;
    pa();
  };
  rc.onend=function(){pa();};
  rc.start();
}

function pa(){
  at=false;
  document.getElementById('bv').className='';
  document.getElementById('bv').innerHTML='🎤&nbsp;&nbsp;Registrar pesagem por voz';
  if(rc){try{rc.stop();}catch(e){} rc=null;}
}

function confirmar(){
  try{
    // Gravar na URL via replaceState (sem reload)
    var url=new URL(window.parent.location.href);
    url.searchParams.set('_voz_txt', encodeURIComponent(txt));
    window.parent.history.replaceState({},'',url.toString());

    // Clicar no botão ↺ para forçar rerun sem perder sessão
    var btns = window.parent.document.querySelectorAll('button');
    for(var i=0;i<btns.length;i++){
      if(btns[i].textContent.trim() === '↺'){
        btns[i].click();
        return;
      }
    }
    // Fallback: disparar evento de mudança no input de texto
    var inputs = window.parent.document.querySelectorAll('input[type="text"]');
    for(var j=0;j<inputs.length;j++){
      var ph = inputs[j].placeholder || '';
      if(ph.indexOf('01') >= 0 || ph.indexOf('peso') >= 0 || ph.indexOf('350') >= 0){
        var nv = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value');
        nv.set.call(inputs[j], txt);
        inputs[j].dispatchEvent(new Event('input',{bubbles:true}));
        inputs[j].dispatchEvent(new Event('change',{bubbles:true}));
        return;
      }
    }
  }catch(e){
    // Fallback final: mostrar texto para copiar
    document.getElementById('sv').textContent=
      'Cole no campo abaixo: ' + txt;
  }
}
</script>
"""
        _stc.html(_html_voz, height=200)

        # Botão rerun — visível mas pequeno, clicado pelo JS
        # CSS o torna quase invisível sem remover do DOM
        st.markdown("""<style>
button[kind="secondary"][data-testid*="voz_rerun"]{
  opacity:0;height:1px;padding:0;margin:0;min-height:0;
  pointer-events:none;overflow:hidden;}
</style>""", unsafe_allow_html=True)
        if st.button("↺", key="_btn_voz_rerun", type="secondary"):
            pass  # dispara rerun

        # Ler transcrição do query param — disparado pelo botão "Usar esta transcrição"
        _voz_param = st.query_params.get("_voz_txt", "")
        if _voz_param:
            st.session_state["_voz_texto"] = _voz_param
            st.query_params.clear()

        # Campo de texto editável
        _key_campo = f"_voz_inp_{st.session_state.get('_voz_key', 0)}"
        _transcricao = st.text_input(
            "✏️ Transcrição — edite se necessário:",
            value=st.session_state.get("_voz_texto", ""),
            placeholder='Ex: "01 350" ou "01 peso 340"',
            key=_key_campo,
        )

        # Mostrar cards se há texto
        _texto = _transcricao or st.session_state.get("_voz_texto", "")

        if _texto and len(_texto.strip()) > 1:
            _p = _parse_voz(_texto)

            st.markdown("**🔍 Confirme antes de salvar:**")
            _c1, _c2, _c3 = st.columns(3)
            with _c1:
                st.markdown(f"""
<div style="background:#E8F5EE;border:2px solid #1B4332;
     border-radius:10px;padding:14px;text-align:center">
  <div style="font-size:10px;color:#40916C;letter-spacing:1px;
       margin-bottom:4px">ANIMAL</div>
  <div style="font-size:24px;font-weight:700;color:#1B4332">
    {_p['animal'] or '?'}</div>
</div>""", unsafe_allow_html=True)
            with _c2:
                st.markdown(f"""
<div style="background:#E8F5EE;border:2px solid #1B4332;
     border-radius:10px;padding:14px;text-align:center">
  <div style="font-size:10px;color:#40916C;letter-spacing:1px;
       margin-bottom:4px">PESO (kg)</div>
  <div style="font-size:24px;font-weight:700;color:#1B4332">
    {_p['peso'] or '?'}</div>
</div>""", unsafe_allow_html=True)
            with _c3:
                from datetime import date as _date
                _data_v = st.date_input(
                    "Data", value=_date.today(),
                    key="_voz_dt", label_visibility="collapsed"
                )

            _aid = _mapa_voz.get((_p["animal"] or "").upper())
            if not _aid and _p["animal"]:
                for _k, _v in _mapa_voz.items():
                    if _p["animal"] in _k or _k in _p["animal"]:
                        _aid = _v
                        break

            if _p["animal"] and not _aid:
                st.warning(
                    f"⚠️ **{_p['animal']}** não encontrado. "
                    f"Disponíveis: {', '.join(list(_mapa_voz.keys())[:8])}"
                )

            _b1, _b2 = st.columns([2, 1])
            _pode = bool(_aid and _p["peso"] and _p["peso"] > 0)
            with _b1:
                if st.button("✅ Confirmar e salvar pesagem",
                             type="primary", key="btn_voz_ok",
                             disabled=not _pode,
                             use_container_width=True):
                    try:
                        adicionar_pesagem(_aid, _p["peso"], str(_data_v))
                        toast_ok(
                            f"✅ {_p['animal']} — "
                            f"{_p['peso']} kg em {fmt_data(str(_data_v))}"
                        )
                        st.session_state["_voz_texto"] = ""
                        st.session_state["_voz_key"] =                             st.session_state.get("_voz_key", 0) + 1
                        st.rerun()
                    except Exception as _ev:
                        toast_erro(f"Erro: {_ev}")
            with _b2:
                if st.button("🔄 Limpar", key="btn_voz_limpar",
                             use_container_width=True):
                    st.session_state["_voz_texto"] = ""
                    st.session_state["_voz_key"] =                         st.session_state.get("_voz_key", 0) + 1
                    st.rerun()

        st.divider()
        # ── FIM PESAGEM POR VOZ ───────────────────────────────────────────

        try:
            plote_ws = listar_pesagens_lote(lote_ws_id)
        except Exception:
            plote_ws = []
            st.warning("⚠️ Erro ao carregar pesagens. Tente recarregar a página.")
        if plote_ws:
            df_p_ws = pd.DataFrame(plote_ws,
                columns=["ID","LoteID","Peso","Data","Animal","AnimalID"])
            df_p_ws["Data"] = pd.to_datetime(df_p_ws["Data"])
            df_p_ws = df_p_ws.sort_values("Data")

            # Gráfico: peso médio do lote por período
            # Estratégia: para cada animal, pegar o peso mais recente
            # até cada data — depois calcular a média entre animais
            # Isso produz uma linha suave mesmo com datas diferentes

            # 1. Pivotar: cada animal vira coluna, cada data vira linha
            _df_pivot = df_p_ws.pivot_table(
                index="Data", columns="Animal",
                values="Peso", aggfunc="mean"
            )
            # 2. Forward-fill: propagar último peso conhecido p/ datas sem pesagem
            _df_pivot = _df_pivot.sort_index().ffill()
            # 3. Média diária entre todos os animais com dados
            _df_media = _df_pivot.mean(axis=1).reset_index()
            _df_media.columns = ["Data", "Peso Médio (kg)"]
            st.caption("Peso médio do lote — evolução ao longo do tempo")
            safe_line_chart(_df_media.set_index("Data")["Peso Médio (kg)"])

            st.subheader("Todas as pesagens")
            # Exibir com data formatada
            df_exib = df_p_ws[["Animal","Peso","Data"]].copy()
            df_exib["Data"] = df_exib["Data"].apply(
                lambda x: fmt_data(str(x)[:10])
            )
            st.dataframe(
                df_exib.rename(columns={"Peso":"Peso (kg)"}),
                use_container_width=True
            )
            st.caption(f"Total: {len(plote_ws)} pesagens | {df_p_ws['Animal'].nunique()} animais")
        else:
            empty_state("Sem pesagens registradas", "Registre pesagens para acompanhar o desenvolvimento do rebanho.", icone="⚖️")
            if st.button("Ir para Registrar Pesagem", type="primary"):
                st.session_state.menu = "Registrar Pesagem"
                st.rerun()

    # ── ABA SANIDADE ──────────────────────────────────────────────────────────
    with aba_san:
        c1_s, c2_s = st.columns(2)

        with c1_s:
            st.subheader("Ocorrencias")
            todas_ocs_raw = _ws['todas_ocs']
            todas_ocs = [{"Animal": r[9], "Data": fmt_data(r[2]), "Tipo": r[3],
                          "Gravidade": r[5], "Custo": r[6], "Status": r[8]}
                         for r in todas_ocs_raw]
            if todas_ocs:
                df_oc_ws = pd.DataFrame(todas_ocs)
                # Contagem por tipo
                por_tipo = df_oc_ws.groupby("Tipo").size().reset_index(name="Qtd")
                safe_bar_chart(por_tipo.set_index("Tipo")["Qtd"])
                em_trat = df_oc_ws[df_oc_ws["Status"]=="Em tratamento"]
                if len(em_trat) > 0:
                    st.warning(f"{len(em_trat)} ocorrencia(s) em tratamento")
                    st.dataframe(em_trat[["Animal","Data","Tipo","Gravidade"]], use_container_width=True)
            else:
                st.info("Nenhuma ocorrencia registrada.")

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
            _oid_ws = u.get("owner_id") or u["id"]
            meds_ws = listar_medicamentos_criticos(owner_id=_oid_ws)
            if meds_ws:
                for m in meds_ws[:3]:
                    st.warning(f"{m[1]}: {m[3]} {m[2]} (min: {m[4]})")
            else:
                toast_ok("Estoque OK")

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
                    st.metric("Custo total de compra", fmt_brl(custo_aq))
                    st.metric("Preco por animal", fmt_brl(preco_u))
                except Exception as _e:
                    pass  # silenced

            st.metric("Custo sanitario", fmt_brl(rs_ws['custo_sanitario']))
            custo_total = custo_aq + rs_ws['custo_sanitario']
            st.metric("Custo total estimado", fmt_brl(custo_total))

        with col_f2:
            st.subheader("Venda e margem")
            vendas_ws = _ws['vendas']
            if vendas_ws:
                v = vendas_ws[0]
                receita = v[3] * v[4]
                margem = receita - custo_aq - rs_ws['custo_sanitario']
                st.metric("Receita", fmt_brl(receita))
                st.metric("Margem", fmt_brl(margem),
                          delta=f"{(margem/custo_aq*100 if custo_aq else 0):.1f}%")
                st.caption(f"Venda em {v[2]} | {v[3]} kg | {v[5]}")
            else:
                st.info("Nenhuma venda registrada.")
                custo_diar = st.number_input("Custo diario/animal (R$)", 0.0, value=8.0, key="ws_cd")
                dias_ws2 = (date.today() - pd.to_datetime(lote_ws[3] if lote_ws else date.today()).date()).days
                custo_op = custo_diar * rs_ws['ativos'] * max(dias_ws2, 1)
                st.metric("Custo operacional estimado", fmt_brl(custo_op),
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

    if is_vet():
        sel_fazenda_vet(key="vet_faz_pron")
        st.divider()


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
        except Exception as _e:
            pass  # silenced

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
            data_str = fmt_data(ev.get("data",""))
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
                        toast_ok("Prontuario atualizado!"); st.rerun()
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
                    safe_line_chart(df_p.set_index("Data")["Peso"])
                    st.dataframe(df_p[["Data","Peso"]].rename(columns={"Peso":"Peso (kg)"}), use_container_width=True)
                else: st.info("Sem pesagens.")

            with t4:
                ocs = listar_ocorrencias(animal_id)
                if ocs:
                    df_oc = pd.DataFrame(ocs, columns=["ID","Animal","Data","Tipo","Desc","Grav","Custo","Dias","Status"])
                    df_oc["Data"] = pd.to_datetime(df_oc["Data"])
                    st.dataframe(df_oc[["Data","Tipo","Grav","Desc","Custo","Status"]], use_container_width=True)
                    st.metric("Custo total tratamentos", fmt_brl(sum(o[6] for o in ocs if o[6])))
                else: st.info("Nenhuma ocorrencia registrada.")
                repros = listar_reproducao(animal_id)
                if repros:
                    st.subheader("Historico Reprodutivo")
                    df_r = pd.DataFrame(repros, columns=["ID","Animal","Cio","Tipo","Diag","Result","Parto Prev","Parto Real","Obs"])
                    st.dataframe(df_r[["Cio","Tipo","Result","Parto Prev","Parto Real"]], use_container_width=True)

    # ── Monitoramentos pos-tratamento ────────────────────────────────────────
    try:
        mons_anim = listar_monitoramentos(animal_id=animal_id, apenas_ativos=False)
    except Exception:
        mons_anim = []

    if mons_anim:
        st.divider()
        st.subheader("Monitoramentos Pos-Tratamento")
        for m in mons_anim:
            venc_ic = "🔴" if (m["vencido"] and m["status"]=="ativo") else ("✅" if m["status"]=="encerrado" else "🟢")
            dt_ret = fmt_data(m["data_retorno"])
            with st.expander(
                f"{venc_ic} {m['descricao'][:60]} | Retorno: {dt_ret} | {m['status'].upper()}"
            ):
                for ev in (m["evolucoes"] or []):
                    quem_ic = "🩺" if ev.get("quem")=="vet" else "🌾"
                    dt_ev = fmt_data(ev.get("data",""))
                    st.caption(f"{quem_ic} {dt_ev} — {ev.get('texto','')}")
                if m["status"] == "ativo":
                    with st.form(f"form_ev_faz_{m['id']}"):
                        ev_txt = st.text_area(
                            "Registrar evolucao do animal",
                            height=60, key=f"evfaz_{m['id']}"
                        )
                        if st.form_submit_button("Salvar evolucao", type="primary"):
                            if ev_txt:
                                registrar_evolucao(m["id"], ev_txt, str(date.today()), "fazendeiro")
                                st.success("Evolucao registrada!")
                                st.rerun()

    # ============================================================
    # MARGEM REAL
    # ============================================================




def page_vender_lote(u):
    """Tela para registrar a venda de um lote — ciclo ATIVO → VENDIDO."""
    from ux_helpers import toast_ok, toast_erro, fmt_brl, fmt_data
    from database import (listar_lotes, registrar_venda_lote,
                          marcar_em_venda, cancelar_venda_lote,
                          obter_resumo_venda_lote)
    from datetime import date

    st.subheader("💰 Registrar Venda de Lote")
    st.caption("Registre a venda para encerrar o ciclo e gerar o DRE automático")

    _oid = owner_id() or u["id"]
    lotes = listar_lotes(owner_id=_oid) or []

    # Separar por status
    ativos    = [l for l in lotes if (l[12] if len(l)>12 else "ATIVO") == "ATIVO"]
    em_venda  = [l for l in lotes if (l[12] if len(l)>12 else "") == "EM_VENDA"]

    if not ativos and not em_venda:
        st.info("Nenhum lote ativo para registrar venda.")
        return

    # Tabs: Registrar venda | Lotes em negociação
    _tv, _tn = st.tabs(["📝 Nova venda", "🤝 Em negociação"])

    # ── ABA 1: NOVA VENDA ─────────────────────────────────────────────
    with _tv:
        _todos_disponiveis = ativos + em_venda
        if not _todos_disponiveis:
            st.info("Nenhum lote disponível.")
        else:
            _opts = {f"{l[1]} ({(l[12] if len(l)>12 else 'ATIVO')})": l[0]
                     for l in _todos_disponiveis}
            _sel = st.selectbox("Selecione o lote", list(_opts.keys()),
                                key="venda_lote_sel")
            _lid = _opts[_sel]

            # Dados do lote selecionado
            _lote_sel = next((l for l in _todos_disponiveis if l[0] == _lid), None)
            if _lote_sel:
                _c1, _c2, _c3 = st.columns(3)
                _c1.metric("Animais", _lote_sel[5] if len(_lote_sel)>5 else "—")
                _c2.metric("Data entrada", fmt_data(str(_lote_sel[3])[:10]))
                _preco_compra = _lote_sel[9] if len(_lote_sel)>9 else 0
                _c3.metric("Custo/animal", fmt_brl(_preco_compra))

            st.divider()
            st.markdown("**Dados da venda:**")

            with st.form("form_venda_lote"):
                _c1, _c2 = st.columns(2)
                with _c1:
                    _data_v    = st.date_input("Data da venda", value=date.today(),
                                               key="venda_data")
                    _preco_arr = st.number_input("Preço da arroba (R$)", min_value=0.0,
                                                  value=320.0, step=5.0,
                                                  key="venda_preco_arr")
                with _c2:
                    _peso_tot  = st.number_input("Peso total vendido (kg)", min_value=0.0,
                                                  value=0.0, step=100.0,
                                                  key="venda_peso")
                    _frigorifico = st.text_input("Frigorífico / Comprador",
                                                  placeholder="Ex: Friboi, JBS, Minerva...",
                                                  key="venda_frig")

                _gta = st.text_input("Número do GTA (opcional)",
                                      placeholder="Ex: SP-12345/2025",
                                      key="venda_gta")
                _obs = st.text_area("Observações", height=80, key="venda_obs",
                                    placeholder="Notas sobre a negociação, desconto, etc.")

                # Preview do DRE em tempo real
                if _peso_tot > 0 and _preco_arr > 0:
                    _arrobas_prev = _peso_tot * 0.5 / 15
                    _receita_prev = _arrobas_prev * _preco_arr
                    st.markdown("**Preview da receita:**")
                    _pc1, _pc2, _pc3 = st.columns(3)
                    _pc1.metric("Arrobas", f"{_arrobas_prev:.1f} @")
                    _pc2.metric("Receita estimada", fmt_brl(_receita_prev))
                    _pc3.metric("R$/arroba", fmt_brl(_preco_arr))

                _c_reg, _c_em = st.columns(2)
                with _c_reg:
                    _submit = st.form_submit_button(
                        "✅ Registrar venda definitiva",
                        type="primary", use_container_width=True
                    )
                with _c_em:
                    _em_venda_btn = st.form_submit_button(
                        "🤝 Marcar como Em Negociação",
                        use_container_width=True
                    )

                if _submit:
                    if _peso_tot <= 0:
                        st.error("Informe o peso total vendido.")
                    elif _preco_arr <= 0:
                        st.error("Informe o preço da arroba.")
                    else:
                        ok, receita, arrobas = registrar_venda_lote(
                            _lid, str(_data_v), _preco_arr,
                            _peso_tot, _frigorifico, _gta, _obs
                        )
                        if ok:
                            toast_ok(
                                f"Venda registrada! {arrobas:.1f}@ · "
                                f"Receita: {fmt_brl(receita)}"
                            )
                            st.balloons()
                            st.rerun()
                        else:
                            toast_erro("Erro ao registrar a venda.")

                if _em_venda_btn:
                    if marcar_em_venda(_lid):
                        toast_ok("Lote marcado como Em Negociação.")
                        st.rerun()

    # ── ABA 2: EM NEGOCIAÇÃO ──────────────────────────────────────────
    with _tn:
        if not em_venda:
            st.info("Nenhum lote em negociação no momento.")
        else:
            for lote in em_venda:
                with st.expander(f"🤝 {lote[1]}", expanded=True):
                    _cc1, _cc2, _cc3 = st.columns(3)
                    _cc1.metric("Animais", lote[5] if len(lote)>5 else "—")
                    _cc2.metric("Entrada", fmt_data(str(lote[3])[:10]))
                    _cc3.metric("Status",
                                "🟡 Em negociação",
                                label_visibility="collapsed")
                    _b1, _b2 = st.columns(2)
                    with _b1:
                        if st.button("↩️ Voltar para ATIVO",
                                     key=f"cancel_venda_{lote[0]}",
                                     use_container_width=True):
                            if cancelar_venda_lote(lote[0]):
                                toast_ok("Lote voltou para ATIVO.")
                                st.rerun()
                    with _b2:
                        if st.button("✅ Finalizar venda agora",
                                     key=f"finalizar_{lote[0]}",
                                     type="primary",
                                     use_container_width=True):
                            st.session_state["_venda_lote_id"] = lote[0]
                            st.session_state.menu = "Vender Lote"
                            st.rerun()


def page_historico_lotes(u):
    """Histórico de lotes vendidos com DRE automático por lote."""
    from ux_helpers import fmt_brl, fmt_data
    from database import listar_lotes_historico, obter_resumo_venda_lote

    st.subheader("📚 Histórico de Lotes")
    st.caption("Lotes vendidos e arquivados — dados preservados para sempre")

    _oid = owner_id() or u["id"]
    historico = listar_lotes_historico(_oid) or []

    if not historico:
        st.info("Nenhum lote vendido ainda. Os lotes vendidos aparecerão aqui.")
        return

    # Filtros
    _c1, _c2 = st.columns(2)
    with _c1:
        _filtro_status = st.selectbox(
            "Status", ["Todos", "VENDIDO", "ARQUIVADO"], key="hist_status"
        )
    with _c2:
        _busca = st.text_input("Buscar por nome", placeholder="Nome do lote...",
                               key="hist_busca")

    if _filtro_status != "Todos":
        historico = [l for l in historico if l[12] == _filtro_status]
    if _busca:
        historico = [l for l in historico if _busca.lower() in l[1].lower()]

    st.markdown(f"**{len(historico)} lote(s) encontrado(s)**")
    st.divider()

    for lote in historico:
        _lid    = lote[0]
        _nome   = lote[1]
        _status = lote[12] if len(lote)>12 else "VENDIDO"
        _data_v = lote[10] if len(lote)>10 else ""
        _receita = lote[17] if len(lote)>17 else 0

        _icone = "✅" if _status == "VENDIDO" else "📦"
        _data_fmt = fmt_data(str(_data_v)[:10]) if _data_v else "—"

        with st.expander(
            f"{_icone} {_nome} · Vendido em {_data_fmt} · {fmt_brl(_receita)}",
            expanded=False
        ):
            resumo = obter_resumo_venda_lote(_lid)
            if not resumo:
                st.info("Detalhes não disponíveis.")
                continue

            # KPIs principais
            _k1, _k2, _k3, _k4 = st.columns(4)
            _k1.metric("Receita total", fmt_brl(resumo["receita"]))
            _k2.metric("Custo total",   fmt_brl(resumo["custo_total"]))
            _margem_delta = f"{resumo['margem_pct']:+.1f}%"
            _k3.metric("Margem", fmt_brl(resumo["margem"]),
                       delta=_margem_delta,
                       delta_color="normal")
            _k4.metric("Custo/@", fmt_brl(resumo["custo_arroba"]))

            # DRE detalhado
            st.markdown("**DRE — Demonstrativo do Resultado:**")
            _dre_items = [
                ("(+) Receita de vendas",
                 resumo["receita"], True, True),
                ("(-) Custo de aquisição",
                 resumo["custo_compra"], False, False),
                ("(-) Custos operacionais",
                 resumo["custo_operacional"], False, False),
                ("(=) Margem bruta",
                 resumo["margem"], True, resumo["margem"] >= 0),
            ]
            _dre_html = """<table style='width:100%;border-collapse:collapse;
                font-size:13px'>"""
            for label, val, negrito, positivo in _dre_items:
                _fw  = "600" if negrito else "400"
                _cor = ("#1B4332" if positivo else "#E24B4A") if negrito else "#374151"
                _sinal = "" if val >= 0 else "-"
                _dre_html += f"""<tr style='border-bottom:.5px solid #f0f0f0'>
                    <td style='padding:8px 4px;font-weight:{_fw};color:#374151'>
                        {label}</td>
                    <td style='padding:8px 4px;text-align:right;
                        font-weight:{_fw};color:{_cor}'>
                        {_sinal}{fmt_brl(abs(val))}</td>
                </tr>"""
            _dre_html += "</table>"
            st.html(_dre_html)

            # Custos por categoria
            if resumo["custos_cats"]:
                with st.expander("Ver custos por categoria", expanded=False):
                    for cat, val in sorted(resumo["custos_cats"].items(),
                                            key=lambda x: -x[1]):
                        _pct = val/resumo["custo_operacional"]*100                                if resumo["custo_operacional"] else 0
                        st.markdown(
                            f"**{cat.capitalize()}**: {fmt_brl(val)} "
                            f"({_pct:.1f}%)"
                        )

            # Dados da venda
            st.divider()
            _ci1, _ci2, _ci3 = st.columns(3)
            _ci1.metric("Arrobas vendidas", f"{resumo['arrobas']:.1f} @")
            _ci2.metric("Frigorífico",
                        resumo["frigorifico"] or "Não informado")
            _ci3.metric("GTA", resumo["gta"] or "Não informado")
            if resumo["obs"]:
                st.caption(f"Obs: {resumo['obs']}")
