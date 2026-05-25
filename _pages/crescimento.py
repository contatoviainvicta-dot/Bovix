"""
_pages/crescimento.py — Sprint B: Importacao CSV, Onboarding, Planos
"""
import streamlit as st
import io
import csv
from datetime import date, datetime

from database import (
    # CSV
    importar_animais_csv, importar_pesagens_csv,
    listar_lotes, listar_animais_por_lote,
    # Onboarding
    obter_progresso_onboarding, marcar_passo_onboarding,
    onboarding_completo, _PASSOS_ONBOARDING,
    # Planos
    obter_plano, atualizar_plano, verificar_limite_animais,
    _PLANOS,
    # Email
    enviar_email_boas_vindas, enviar_email_alerta_diario,
    listar_vacinas_pendentes, listar_medicamentos_criticos,
    # Utils
    obter_nome_usuario,
)
from rules import owner_id, is_vet, is_fazendeiro, usuario_atual


# ════════════════════════════════════════════════════════════════════════════
# IMPORTACAO CSV
# ════════════════════════════════════════════════════════════════════════════
def _template_animais_csv():
    """Retorna bytes do template CSV de animais."""
    linhas = [
        ["identificacao","raca","sexo","idade","peso_entrada","peso_alvo","observacoes"],
        ["BOI-001","Nelore","M","18","320","480",""],
        ["BOI-002","Angus","M","24","380","500","Vacinado"],
        ["NOV-001","Nelore","F","14","240","380",""],
    ]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerows(linhas)
    return buf.getvalue().encode("utf-8")


def _template_pesagens_csv():
    """Retorna bytes do template CSV de pesagens."""
    linhas = [
        ["identificacao","data","peso"],
        ["BOI-001","2026-01-15","310"],
        ["BOI-001","2026-03-15","345"],
        ["BOI-002","2026-01-15","370"],
    ]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerows(linhas)
    return buf.getvalue().encode("utf-8")


def page_importar_csv(u):
    st.title("Importacao de Dados")
    st.caption("Importe animais e pesagens em massa via planilha CSV")

    oid   = u.get("owner_id") or u["id"]
    lotes = listar_lotes(owner_id=oid)

    if not lotes:
        st.warning("Crie pelo menos um lote antes de importar animais.")
        return

    t1, t2 = st.tabs(["Importar Animais", "Importar Pesagens"])

    # ── ABA 1: Animais ────────────────────────────────────────────────────
    with t1:
        st.subheader("Importar Animais")

        # Download do template
        col_t, col_i = st.columns([1, 2])
        with col_t:
            st.download_button(
                label="Baixar template CSV",
                data=_template_animais_csv(),
                file_name="template_animais.csv",
                mime="text/csv",
                help="Baixe e preencha o template, depois carregue aqui"
            )

        with col_i:
            # Verificar limite
            atual, limite, pode = verificar_limite_animais(oid)
            vagos = limite - atual
            if not pode:
                st.error(
                    f"Limite de animais atingido ({atual}/{limite}). "
                    "Atualize seu plano para importar mais."
                )
                return
            st.info(f"Voce pode adicionar ate **{vagos}** animais (limite: {limite})")

        # Selecionar lote destino
        dict_lotes = {f"{l[1]}": l[0] for l in lotes}
        lote_sel   = st.selectbox("Lote de destino *", list(dict_lotes.keys()))
        lote_id    = dict_lotes[lote_sel]

        # Upload do arquivo
        arquivo = st.file_uploader(
            "Selecione o arquivo CSV",
            type=["csv"],
            key="csv_animais"
        )

        if arquivo:
            try:
                conteudo = arquivo.read().decode("utf-8-sig")
                reader   = csv.DictReader(io.StringIO(conteudo))
                linhas   = list(reader)

                if not linhas:
                    st.warning("Arquivo vazio.")
                else:
                    # Preview
                    st.caption(f"{len(linhas)} linha(s) encontrada(s)")
                    import pandas as pd
                    df_prev = pd.DataFrame(linhas[:5])
                    st.dataframe(df_prev, hide_index=True)

                    if len(linhas) > vagos:
                        st.warning(
                            f"O arquivo tem {len(linhas)} animais mas voce so pode "
                            f"adicionar {vagos}. Apenas os primeiros {vagos} serao importados."
                        )
                        linhas = linhas[:vagos]

                    if st.button("Confirmar importacao", type="primary",
                                key="btn_imp_animais"):
                        with st.spinner("Importando..."):
                            n_ok, n_err, erros = importar_animais_csv(
                                lote_id, linhas
                            )
                        if n_ok:
                            st.success(f"{n_ok} animal(is) importado(s) com sucesso!")
                            marcar_passo_onboarding(oid, "animais")
                        if n_err:
                            st.warning(f"{n_err} linha(s) com erro:")
                            for e in erros[:10]:
                                st.caption(f"  - {e}")

            except Exception as e:
                st.error(f"Erro ao ler arquivo: {e}")

        # Instrucoes
        with st.expander("Como preencher o CSV"):
            st.markdown("""
**Colunas obrigatorias:** `identificacao`

**Colunas opcionais:** `raca`, `sexo` (M ou F), `idade` (meses),
`peso_entrada` (kg), `peso_alvo` (kg), `observacoes`

**Exemplo:**
```
identificacao,raca,sexo,idade,peso_entrada
BOI-001,Nelore,M,18,320
BOI-002,Angus,F,14,240
```
- Codificacao: UTF-8 ou UTF-8-BOM
- Separador: virgula
- Data: nao necessaria para animais
            """)

    # ── ABA 2: Pesagens ───────────────────────────────────────────────────
    with t2:
        st.subheader("Importar Pesagens Historicas")

        col_t2, _ = st.columns([1, 2])
        with col_t2:
            st.download_button(
                label="Baixar template CSV",
                data=_template_pesagens_csv(),
                file_name="template_pesagens.csv",
                mime="text/csv"
            )

        arquivo_p = st.file_uploader(
            "Selecione o arquivo CSV de pesagens",
            type=["csv"],
            key="csv_pesagens"
        )

        if arquivo_p:
            try:
                conteudo_p = arquivo_p.read().decode("utf-8-sig")
                reader_p   = csv.DictReader(io.StringIO(conteudo_p))
                linhas_p   = list(reader_p)

                if not linhas_p:
                    st.warning("Arquivo vazio.")
                else:
                    st.caption(f"{len(linhas_p)} pesagem(ns) encontrada(s)")
                    import pandas as pd
                    df_prev_p = pd.DataFrame(linhas_p[:5])
                    st.dataframe(df_prev_p, hide_index=True)

                    if st.button("Confirmar importacao", type="primary",
                                key="btn_imp_pesagens"):
                        with st.spinner("Importando..."):
                            n_ok, n_err, erros = importar_pesagens_csv(
                                linhas_p, oid
                            )
                        if n_ok:
                            st.success(f"{n_ok} pesagem(ns) importada(s)!")
                        if n_err:
                            st.warning(f"{n_err} linha(s) com erro:")
                            for e in erros[:10]:
                                st.caption(f"  - {e}")

            except Exception as e:
                st.error(f"Erro ao ler arquivo: {e}")

        with st.expander("Como preencher o CSV de pesagens"):
            st.markdown("""
**Colunas obrigatorias:** `identificacao` (brinco do animal), `data`, `peso`

**Formatos de data aceitos:** `2026-01-15`, `15/01/2026`, `15-01-2026`

**Exemplo:**
```
identificacao,data,peso
BOI-001,2026-01-15,310
BOI-001,2026-03-15,345
```
O animal precisa ja estar cadastrado no sistema.
            """)


# ════════════════════════════════════════════════════════════════════════════
# ONBOARDING — 6 PASSOS
# ════════════════════════════════════════════════════════════════════════════
def page_onboarding(u):
    """Wizard de onboarding de 6 passos."""
    oid  = u.get("owner_id") or u["id"]
    prog = obter_progresso_onboarding(oid)
    concluidos = sum(1 for v in prog.values() if v)
    total      = len(_PASSOS_ONBOARDING)
    pct        = int(100 * concluidos / total)

    st.title("Configure o BOVIX")
    st.caption("Complete os passos abaixo para aproveitar tudo que o BOVIX oferece")
    st.progress(pct / 100)
    st.caption(f"{concluidos} de {total} passos concluidos ({pct}%)")

    if concluidos == total:
        st.success(
            "Configuracao completa! Voce ja pode usar todos os recursos do BOVIX."
        )
        if st.button("Ir para o inicio", type="primary"):
            st.session_state["_page"] = "Inicio"
            st.rerun()
        return

    st.divider()

    # Renderizar cada passo
    _passos_ui(u, oid, prog)


def _passos_ui(u, oid, prog):
    """Renderiza os 6 passos do onboarding."""
    from database import (
        listar_lotes, listar_animais_por_lote,
        obter_crmv_usuario, adicionar_vacina_agenda,
    )

    # PASSO 1: Perfil
    _passo_header(1, "Complete seu perfil", prog["perfil"])
    if not prog["perfil"]:
        with st.expander("Configurar agora", expanded=True):
            with st.form("ob_perfil"):
                nome_p = st.text_input("Nome completo", value=u.get("nome",""))
                if is_vet():
                    crmv_p = st.text_input(
                        "CRMV",
                        value=obter_crmv_usuario(u["id"]) or "",
                        placeholder="CRMV-SP 12345"
                    )
                if st.form_submit_button("Salvar perfil", type="primary"):
                    from database import atualizar_crmv
                    if is_vet() and crmv_p:
                        atualizar_crmv(u["id"], crmv_p)
                    marcar_passo_onboarding(oid, "perfil")
                    st.success("Perfil salvo!")
                    st.rerun()
    else:
        st.caption("Perfil configurado")

    # PASSO 2: Fazenda
    _passo_header(2, "Configure sua fazenda", prog["fazenda"])
    if not prog["fazenda"]:
        with st.expander("Configurar agora", expanded=True):
            st.info(
                "Sua conta ja representa sua fazenda no BOVIX. "
                "Verifique se os dados de cadastro estao corretos."
            )
            if st.button("Confirmar e continuar", key="ob_faz"):
                marcar_passo_onboarding(oid, "fazenda")
                st.rerun()
    else:
        st.caption("Fazenda configurada")

    # PASSO 3: Lote
    _passo_header(3, "Crie seu primeiro lote", prog["lote"])
    lotes = listar_lotes(owner_id=oid)
    if not prog["lote"]:
        if lotes:
            marcar_passo_onboarding(oid, "lote")
            st.rerun()
        else:
            with st.expander("Criar lote agora", expanded=True):
                st.info("Va em **Gestao → Lotes** para criar seu primeiro lote.")
                if st.button("Abrir Lotes", key="ob_lote"):
                    st.session_state["_page"] = "Lote"
                    st.rerun()
    else:
        st.caption(f"{len(lotes)} lote(s) cadastrado(s)")

    # PASSO 4: Animais
    _passo_header(4, "Cadastre seus animais", prog["animais"])
    total_an = sum(
        len(listar_animais_por_lote(l[0])) for l in lotes
    ) if lotes else 0
    if not prog["animais"]:
        if total_an > 0:
            marcar_passo_onboarding(oid, "animais")
            st.rerun()
        else:
            with st.expander("Cadastrar agora", expanded=True):
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Cadastrar manualmente", key="ob_an_man"):
                        st.session_state["_page"] = "Animal"
                        st.rerun()
                with c2:
                    if st.button("Importar CSV", key="ob_an_csv"):
                        st.session_state["_page"] = "Importar CSV"
                        st.rerun()
    else:
        st.caption(f"{total_an} animal(is) cadastrado(s)")

    # PASSO 5: Calendario
    _passo_header(5, "Configure o calendario sanitario", prog["calendario"])
    if not prog["calendario"]:
        with st.expander("Configurar agora", expanded=True):
            st.info(
                "Va em **Financeiro & Saude → Calendario Sanitario** "
                "para agendar suas primeiras vacinas."
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Abrir Calendario", key="ob_cal"):
                    st.session_state["_page"] = "Calendario Sanitario"
                    st.rerun()
            with c2:
                if st.button("Pular por agora", key="ob_cal_skip"):
                    marcar_passo_onboarding(oid, "calendario")
                    st.rerun()
    else:
        st.caption("Calendario configurado")

    # PASSO 6: Alertas
    _passo_header(6, "Configure seus alertas", prog["alertas"])
    if not prog["alertas"]:
        with st.expander("Configurar agora", expanded=True):
            st.info(
                "Os alertas do BOVIX funcionam automaticamente: "
                "vacinas pendentes, medicamentos em baixo estoque "
                "e partos previstos aparecem na sua tela inicial."
            )
            email_al = st.text_input(
                "Email para alertas diarios (opcional)",
                placeholder="seuemail@gmail.com"
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Salvar e concluir", type="primary", key="ob_alerta"):
                    marcar_passo_onboarding(oid, "alertas")
                    if email_al:
                        from database import enviar_email_boas_vindas
                        enviar_email_boas_vindas(u.get("nome",""), email_al)
                    st.balloons()
                    st.success("Configuracao concluida! Bem-vindo ao BOVIX!")
                    st.rerun()
            with c2:
                if st.button("Pular", key="ob_alerta_skip"):
                    marcar_passo_onboarding(oid, "alertas")
                    st.rerun()
    else:
        st.caption("Alertas configurados")


def _passo_header(num, titulo, completo):
    """Renderiza cabecalho de passo com status."""
    ic = "✅" if completo else f"**{num}.**"
    cor = "#1B4332" if completo else "#333"
    st.markdown(
        f"<div style='padding:8px 0;border-bottom:1px solid #eee'>"
        f"{ic} <span style='color:{cor};font-size:16px'>{titulo}</span>"
        f"</div>",
        unsafe_allow_html=True
    )


# ════════════════════════════════════════════════════════════════════════════
# PLANOS E ASSINATURAS
# ════════════════════════════════════════════════════════════════════════════
def page_planos(u):
    """Tela de planos e assinaturas."""
    oid         = u.get("owner_id") or u["id"]
    plano_atual = obter_plano(oid)
    atual, lim, _pode = verificar_limite_animais(oid)

    st.title("Planos BOVIX")
    st.caption("Escolha o plano ideal para sua operacao")

    # Status atual
    st.subheader("Seu plano atual")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Plano", plano_atual.get("nome","Free"))
    c2.metric("Animais", f"{atual}/{lim}")
    c3.metric(
        "Expira",
        plano_atual.get("plano_expira") or "Nao expira"
    )
    c4.metric(
        "Status",
        plano_atual.get("status_conta","ativo").upper()
    )

    st.progress(min(atual / max(lim, 1), 1.0))
    if atual >= lim * 0.9:
        st.warning(
            f"Voce esta usando {atual}/{lim} animais ({int(100*atual/lim)}%). "
            "Considere fazer upgrade."
        )

    st.divider()
    st.subheader("Todos os planos")

    # Cards de planos
    cols = st.columns(4)
    planos_order = ["free","pro","vet","enterprise"]

    for i, plano_key in enumerate(planos_order):
        info = _PLANOS[plano_key]
        is_atual = (plano_key == plano_atual.get("plano_key","free"))

        with cols[i]:
            borda = "border:2px solid #1B4332" if is_atual else "border:1px solid #ddd"
            st.markdown(
                f"<div style='{borda};border-radius:12px;padding:16px;"
                f"text-align:center;min-height:280px'>"
                f"<h3 style='color:#1B4332;margin:0'>{info['nome']}</h3>"
                f"<div style='font-size:28px;font-weight:bold;margin:10px 0'>"
                f"{'Gratis' if info['preco']==0 and plano_key=='free' else 'Consulte' if plano_key=='enterprise' else f'R${info["preco"]}'}"
                f"{'<small>/mes</small>' if info['preco']>0 and plano_key!='enterprise' else ''}"
                f"</div>"
                f"<p style='color:#666;font-size:13px'>{info['descricao']}</p>"
                f"<p><b>{info['limite_animais'] if info['limite_animais']<9999 else 'Ilimitado'}</b> animais</p>"
                f"<p><b>{info['limite_fazendas'] if info['limite_fazendas']<999 else 'Ilimitadas'}</b> fazenda(s)</p>"
                f"{'<p style="color:#1B4332"><b>Modulo Vet</b></p>' if info['modulo_vet'] else ''}"
                f"{'<p style="background:#1B4332;color:white;border-radius:6px;padding:4px">PLANO ATUAL</p>' if is_atual else ''}"
                f"</div>",
                unsafe_allow_html=True
            )

    st.divider()

    # Contato para upgrade
    st.subheader("Fazer upgrade")
    st.info(
        "Para fazer upgrade ou downgrade do seu plano, "
        "entre em contato pelo WhatsApp ou email abaixo."
    )
    cc1, cc2 = st.columns(2)
    with cc1:
        st.markdown("📧 **contato@bovix.com.br**")
    with cc2:
        st.markdown("📱 **WhatsApp: (11) 99999-9999**")

    # Painel admin — alterar plano manualmente
    if u.get("perfil") == "admin":
        st.divider()
        st.subheader("Admin — Alterar Plano")
        with st.form("form_plano_admin"):
            email_alvo = st.text_input("Email do usuario")
            novo_plano = st.selectbox(
                "Novo plano", list(_PLANOS.keys()),
                format_func=lambda k: _PLANOS[k]["nome"]
            )
            expira_em  = st.date_input(
                "Expira em (opcional)",
                value=None
            )
            if st.form_submit_button("Aplicar", type="primary"):
                from database import buscar_usuario_por_email
                try:
                    usr = buscar_usuario_por_email(email_alvo)
                    if usr:
                        atualizar_plano(
                            usr["id"], novo_plano,
                            str(expira_em) if expira_em else None
                        )
                        st.success(
                            f"Plano de {email_alvo} atualizado "
                            f"para {_PLANOS[novo_plano]['nome']}!"
                        )
                    else:
                        st.error("Usuario nao encontrado.")
                except Exception as e:
                    st.error(f"Erro: {e}")


# ════════════════════════════════════════════════════════════════════════════
# NOTIFICACOES EMAIL — PAINEL
# ════════════════════════════════════════════════════════════════════════════
def page_notificacoes_email(u):
    """Painel de configuracao e teste de notificacoes email."""
    st.title("Notificacoes por Email")

    oid   = u.get("owner_id") or u["id"]
    email = u.get("email","")

    t1, t2 = st.tabs(["Enviar Alerta", "Configurar SMTP"])

    with t1:
        st.subheader("Alertas disponíveis")

        # Coletar alertas atuais
        pendo = listar_vacinas_pendentes(owner_id=oid)
        crit  = listar_medicamentos_criticos(owner_id=oid)

        alertas_lista = []
        for v in pendo[:5]:
            alertas_lista.append(f"Vacina pendente: {v[3]} | Lote {v[1]}")
        for m in crit[:5]:
            alertas_lista.append(
                f"Medicamento critico: {m[1]} ({m[3]:.0f} {m[2]} em estoque)"
            )

        if alertas_lista:
            st.info(f"{len(alertas_lista)} alerta(s) ativos")
            for a in alertas_lista:
                st.caption(f"  • {a}")

            dest_email = st.text_input(
                "Enviar para", value=email,
                placeholder="seuemail@gmail.com"
            )
            if st.button("Enviar resumo por email", type="primary"):
                if dest_email:
                    with st.spinner("Enviando..."):
                        ok, msg = enviar_email_alerta_diario(
                            u.get("nome",""), dest_email, alertas_lista
                        )
                    if ok:
                        st.success("Email enviado!")
                    else:
                        st.error(f"Erro: {msg}")
                        st.info(
                            "Verifique a configuracao SMTP na aba "
                            "'Configurar SMTP'."
                        )
        else:
            st.success("Nenhum alerta ativo no momento.")

        # Email de boas-vindas
        st.divider()
        if st.button("Reenviar email de boas-vindas"):
            with st.spinner("Enviando..."):
                ok, msg = enviar_email_boas_vindas(
                    u.get("nome",""), email,
                    obter_plano(oid).get("plano_key","free")
                )
            if ok:
                st.success(f"Email enviado para {email}!")
            else:
                st.error(f"Falha: {msg}")

    with t2:
        st.subheader("Configuracao SMTP")
        st.info(
            "Configure as credenciais SMTP nos **Secrets** do Streamlit Cloud. "
            "Va em **Manage App → Secrets** e adicione:"
        )
        st.code("""
[smtp]
host        = "smtp.gmail.com"
port        = 587
user        = "seuemail@gmail.com"
password    = "sua_senha_de_app"
from_email  = "seuemail@gmail.com"
        """, language="toml")

        st.markdown("""
**Para Gmail:**
1. Ative a verificacao em 2 etapas na conta Google
2. Va em **Conta Google → Seguranca → Senhas de app**
3. Gere uma senha de app para "Email"
4. Use essa senha no campo `password` acima
        """)

        # Teste de envio
        st.divider()
        st.subheader("Testar configuracao")
        test_email = st.text_input(
            "Email de destino para teste", value=email
        )
        if st.button("Enviar email de teste"):
            from database import enviar_email
            ok, msg = enviar_email(
                test_email,
                "BOVIX — Teste de configuracao SMTP",
                "<h2>Funcionou!</h2><p>Seu SMTP esta configurado corretamente.</p>",
                "BOVIX: SMTP configurado corretamente."
            )
            if ok:
                st.success("Email de teste enviado com sucesso!")
            else:
                st.error(f"Falha: {msg}")
