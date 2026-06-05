"""
_pages/admin_painel.py — Painel Admin Completo Auroque
MRR, Usuários Ativos, Churn, Erros
"""
import streamlit as st
try:
    from ux_helpers import (aplicar_css_global, toast_ok, toast_erro,
                            toast_aviso, empty_state, erro_com_acao,
                            fmt_brl, fmt_data, fmt_data_hora)
except ImportError:
    def aplicar_css_global(): pass
    def toast_ok(m): st.success(m)
    def toast_erro(m): st.error(m)
    def toast_aviso(m): st.warning(m)
    def empty_state(t, d, **k): st.info(f"{t} — {d}"); return False
    def erro_com_acao(e, a=""): st.error(str(e))
import pandas as pd
from datetime import date, datetime

from database import (
    admin_metricas_usuarios,
    admin_calcular_mrr,
    admin_adicionar_ajuste_mrr,
    admin_listar_usuarios,
    admin_historico_acessos,
    admin_listar_erros,
    admin_erros_email_log,
    admin_metricas_produto,
    atualizar_plano,
    buscar_usuario_por_email,
    _PLANOS,
)
from rules import is_admin


def fmt_brl(v):
    try:
        v = float(v)
        neg = v < 0
        s = fmt_brl(abs(v)).replace(",","X").replace(".",",").replace("X",".")
        return f"-{s}" if neg else s
    except Exception:
        return "R$ 0"


def _fmt_dt(dt):
    if not dt or str(dt) in ("None","nunca",""):
        return "Nunca"
    try:
        return str(dt)[:16].replace("T"," ")
    except Exception:
        return str(dt)[:16]


def page_painel_admin(u):
    if not is_admin():
        st.error("Acesso restrito ao administrador.")
        return

    st.title("Painel Admin")
    st.caption("Visão operacional completa do Auroque")

    # Carregar dados
    with st.spinner("Carregando métricas..."):
        metr_u   = admin_metricas_usuarios()
        mrr_data = admin_calcular_mrr()
        metr_p   = admin_metricas_produto()

    # ── KPIs PRINCIPAIS ──────────────────────────────────────────────────
    k1,k2,k3,k4,k5,k6 = st.columns(6)
    k1.metric("Usuários totais",   metr_u["total"])
    k2.metric("Ativos 30d",        metr_u["ativos_30d"],
             delta=f"{metr_u['ativos_7d']} últimos 7d")
    k3.metric("Novos 30d",         metr_u["novos_30d"])
    k4.metric("Churn 30d",         metr_u["churn_30d"],
             delta=f"{metr_u['churn_rate']}%",
             delta_color="inverse" if metr_u["churn_rate"] > 5 else "off")
    k5.metric("MRR",               fmt_brl(mrr_data["mrr_total"]))
    k6.metric("ARR",               fmt_brl(mrr_data["arr"]))

    st.divider()

    # ── ABAS ─────────────────────────────────────────────────────────────
    t1,t2,t3,t4,t5 = st.tabs([
        "MRR & Receita", "Usuários", "Produto", "Erros", "Ações Admin"
    ])

    # ── ABA 1: MRR ───────────────────────────────────────────────────────
    with t1:
        st.subheader("MRR — Receita Mensal Recorrente")

        # Cards MRR
        mc1,mc2,mc3,mc4 = st.columns(4)
        mc1.metric("MRR automático",  fmt_brl(mrr_data["mrr_auto"]),
                  help="Calculado pelos planos dos usuários")
        mc2.metric("MRR ajustes",     fmt_brl(mrr_data["mrr_ajuste"]),
                  help="Ajustes manuais do mês")
        mc3.metric("MRR total",       fmt_brl(mrr_data["mrr_total"]))
        mc4.metric("ARR projetado",   fmt_brl(mrr_data["arr"]))

        # Breakdown por plano
        if mrr_data["por_plano"]:
            st.divider()
            st.subheader("Breakdown por Plano")
            df_plano = pd.DataFrame([{
                "Plano":    p,
                "Usuários": d["qtd"],
                "Preço":    fmt_brl(d["preco"]),
                "MRR":      fmt_brl(d["total"]),
            } for p, d in mrr_data["por_plano"].items()
              if d["qtd"] > 0])
            if not df_plano.empty:
                st.dataframe(df_plano, hide_index=True,
                           use_container_width=True)

            # Gráfico pizza por plano
            por_plano_vals = {
                p: d["qtd"]
                for p,d in mrr_data["por_plano"].items()
                if d["qtd"] > 0
            }
            if por_plano_vals:
                df_pizza = pd.DataFrame(
                    list(por_plano_vals.items()),
                    columns=["Plano","Usuários"]
                )
                st.bar_chart(df_pizza.set_index("Plano"))

        # Ajustes manuais
        st.divider()
        st.subheader("Ajustes Manuais de MRR")

        if mrr_data["ajustes"]:
            df_adj = pd.DataFrame([{
                "Mês":       a["mes_ref"],
                "Valor":     fmt_brl(a["valor"]),
                "Descrição": a["descricao"],
            } for a in mrr_data["ajustes"]])
            st.dataframe(df_adj, hide_index=True, use_container_width=True)

        with st.form("form_ajuste_mrr"):
            aj1,aj2 = st.columns(2)
            with aj1:
                mes_aj = st.text_input(
                    "Mês de referência (YYYY-MM)",
                    value=mrr_data["mes_ref"]
                )
                val_aj = st.number_input(
                    "Valor (R$) — negativo para desconto",
                    value=0.0, step=50.0, format="%.2f"
                )
            with aj2:
                desc_aj = st.text_input(
                    "Descrição",
                    placeholder="Ex: Enterprise manual, desconto comercial"
                )
            if st.form_submit_button("Adicionar ajuste", type="primary"):
                if val_aj != 0 and mes_aj:
                    admin_adicionar_ajuste_mrr(mes_aj, val_aj, desc_aj)
                    st.success(
                        f"Ajuste de {fmt_brl(val_aj)} adicionado para {mes_aj}!"
                    )
                    st.rerun()
                else:
                    st.error("Informe mês e valor diferente de zero.")

    # ── ABA 2: USUÁRIOS ──────────────────────────────────────────────────
    with t2:
        st.subheader("Gestão de Usuários")

        # Filtros
        uf1,uf2,uf3 = st.columns(3)
        with uf1:
            filtro_perfil = st.selectbox(
                "Perfil", ["todos","fazendeiro","veterinario","admin"],
                key="filt_perfil"
            )
        with uf2:
            filtro_plano = st.selectbox(
                "Plano", ["todos","free","pro","vet","enterprise"],
                key="filt_plano"
            )
        with uf3:
            filtro_ativos = st.checkbox("Apenas ativos 30d",
                                       key="filt_ativos")

        usuarios = admin_listar_usuarios(
            perfil=filtro_perfil if filtro_perfil != "todos" else None,
            plano=filtro_plano if filtro_plano != "todos" else None,
            ativos_30d=filtro_ativos
        )

        st.caption(f"{len(usuarios)} usuário(s) encontrado(s)")

        if usuarios:
            df_u = pd.DataFrame([{
                "Nome":       r[1],
                "Email":      r[2],
                "Perfil":     r[3],
                "Plano":      r[4].upper(),
                "Status":     r[5],
                "Último login":_fmt_dt(r[6]),
                "Trial início":str(r[7])[:10] if r[7] else "-",
                "Lim. animais":r[8],
            } for r in usuarios])
            st.dataframe(df_u, hide_index=True, use_container_width=True)

        # Gráfico ativos por dia (access_log)
        st.divider()
        st.subheader("Atividade Recente (últimos 7 dias)")
        acessos = admin_historico_acessos(dias=7)
        if acessos:
            from collections import Counter
            por_dia = Counter(
                str(a[3])[:10] for a in acessos
            )
            df_ac = pd.DataFrame(
                sorted(por_dia.items()),
                columns=["Data","Acessos"]
            )
            st.bar_chart(df_ac.set_index("Data"))
            st.caption(
                f"Total: {len(acessos)} acessos | "
                f"{len(set(a[0] for a in acessos))} usuários únicos"
            )
        else:
            st.info("Nenhum acesso registrado nos últimos 7 dias.")

    # ── ABA 3: PRODUTO ───────────────────────────────────────────────────
    with t3:
        st.subheader("Métricas de Uso do Produto")

        pm = metr_p
        p1,p2,p3 = st.columns(3)
        p1.metric("Animais cadastrados", pm["total_animais"])
        p2.metric("Lotes cadastrados",   pm["total_lotes"])
        p3.metric("Pesagens registradas",pm["total_pesagens"])

        p4,p5,p6 = st.columns(3)
        p4.metric("Ocorrências clínicas", pm["total_ocorrencias"])
        p5.metric("Receitas emitidas",    pm["total_receitas"])
        p6.metric("Emails enviados",      pm["emails_enviados"])

        # Distribuição de usuários por perfil
        st.divider()
        st.subheader("Distribuição de Usuários")
        df_dist = pd.DataFrame([{
            "Perfil":     "Fazendeiros",
            "Quantidade": metr_u["fazendeiros"],
        },{
            "Perfil":     "Veterinários",
            "Quantidade": metr_u["vets"],
        },{
            "Perfil":     "Admins",
            "Quantidade": metr_u["admins"],
        }])
        st.bar_chart(df_dist.set_index("Perfil"))

        # Distribuição por plano
        if metr_u["por_plano"]:
            st.divider()
            st.subheader("Distribuição por Plano")
            df_pp = pd.DataFrame([
                {"Plano": k.upper(), "Usuários": v}
                for k,v in metr_u["por_plano"].items()
            ])
            st.bar_chart(df_pp.set_index("Plano"))

    # ── ABA 4: ERROS ─────────────────────────────────────────────────────
    with t4:
        st.subheader("Log de Erros")

        ec1,ec2 = st.columns(2)
        with ec1:
            dias_erro = st.selectbox(
                "Período", [1,7,14,30], index=1,
                format_func=lambda x: f"Últimos {x} dias",
                key="dias_erro"
            )

        # Erros da aplicacao
        erros = admin_listar_erros(dias=dias_erro)
        erros_email = admin_erros_email_log(dias=dias_erro)

        ce1,ce2 = st.columns(2)
        ce1.metric("Erros da aplicação", len(erros))
        ce2.metric("Erros de email",     len(erros_email))

        if erros:
            st.divider()
            st.subheader("Erros da Aplicação")
            for e in erros[:20]:
                eid, uid, nome, rota, msg, stack, dt = e
                dt_fmt = _fmt_dt(dt)
                with st.expander(
                    f"🔴 {dt_fmt} | {nome} | {msg[:60]}..."
                    if len(msg) > 60 else f"🔴 {dt_fmt} | {nome} | {msg}"
                ):
                    st.markdown(f"**Usuário:** {nome} (ID: {uid})")
                    st.markdown(f"**Rota:** {rota or '-'}")
                    st.markdown(f"**Mensagem:** {msg}")
                    if stack:
                        st.code(stack, language="python")
        else:
            st.info(f"Nenhum erro nos últimos {dias_erro} dia(s).")

        if erros_email:
            st.divider()
            st.subheader("Erros de Email")
            df_email_err = pd.DataFrame([{
                "Destinatário": e[1],
                "Assunto":      e[2][:40],
                "Erro":         str(e[4])[:60] if e[4] else "-",
                "Data":         _fmt_dt(e[5]),
            } for e in erros_email])
            st.dataframe(df_email_err, hide_index=True,
                        use_container_width=True)

    # ── ABA 5: AÇÕES ADMIN ───────────────────────────────────────────────
    with t5:
        st.subheader("Ações Administrativas")

        # Alterar plano de usuário
        st.markdown("**Alterar plano de usuário**")
        with st.form("form_admin_plano"):
            aa1,aa2,aa3 = st.columns(3)
            with aa1:
                email_alvo = st.text_input("Email do usuário")
            with aa2:
                novo_plano = st.selectbox(
                    "Novo plano",
                    list(_PLANOS.keys()),
                    format_func=lambda k: _PLANOS[k]["nome"]
                )
            with aa3:
                expira_plan = st.date_input(
                    "Expira em (opcional)",
                    value=None
                )
            if st.form_submit_button("Aplicar plano", type="primary"):
                if email_alvo:
                    usr = buscar_usuario_por_email(email_alvo)
                    if usr:
                        atualizar_plano(
                            usr["id"], novo_plano,
                            str(expira_plan) if expira_plan else None
                        )
                        st.success(
                            f"Plano de **{email_alvo}** atualizado para "
                            f"**{_PLANOS[novo_plano]['nome']}**!"
                        )
                    else:
                        st.error("Usuário não encontrado.")
                else:
                    st.error("Informe o email.")

        st.divider()

        # Lista de todos os usuários para gestão rápida
        st.markdown("**Visão rápida de todos os usuários**")
        todos = admin_listar_usuarios()
        if todos:
            df_todos = pd.DataFrame([{
                "ID":    r[0],
                "Nome":  r[1],
                "Email": r[2],
                "Perfil":r[3],
                "Plano": r[4].upper(),
                "Login": _fmt_dt(r[6]),
            } for r in todos])
            st.dataframe(df_todos, hide_index=True, use_container_width=True)
