"""
_pages/crescimento.py — Sprint B: Importacao CSV, Onboarding, Planos
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
            _lim_res = verificar_limite_animais(oid)
            atual  = _lim_res["atual"]
            limite = _lim_res["limite"]
            pode   = _lim_res["ok"]
            vagos  = _lim_res["disponiveis"]
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
                _sep_a = ";" if conteudo[:200].count(";") > conteudo[:200].count(",") else ","
                reader   = csv.DictReader(io.StringIO(conteudo), delimiter=_sep_a)
                linhas   = [{k.strip().lower(): v for k, v in l.items()}
                            for l in reader]

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
                            toast_ok("{n_ok} animal(is) importado(s) com sucesso!")
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

                # Detectar separador automaticamente (virgula ou ponto-e-virgula)
                _sep = ";" if conteudo_p[:200].count(";") > conteudo_p[:200].count(",") else ","
                reader_p = csv.DictReader(io.StringIO(conteudo_p),
                                         delimiter=_sep)
                linhas_p = list(reader_p)

                if not linhas_p:
                    st.warning("Arquivo vazio.")
                else:
                    # Normalizar nomes de colunas (remover espaços, lowercase)
                    linhas_p = [
                        {k.strip().lower(): v for k, v in l.items()}
                        for l in linhas_p
                    ]
                    colunas = list(linhas_p[0].keys()) if linhas_p else []
                    st.caption(
                        f"{len(linhas_p)} linha(s) | "
                        f"Separador: '{_sep}' | "
                        f"Colunas: {', '.join(colunas)}"
                    )

                    # Verificar colunas obrigatórias
                    faltam = [c for c in ['identificacao','data','peso']
                              if c not in colunas]
                    if faltam:
                        st.error(
                            f"Colunas obrigatórias faltando: "
                            f"{', '.join(faltam)}. "
                            f"Colunas encontradas: {', '.join(colunas)}"
                        )
                    else:
                        import pandas as pd
                        df_prev_p = pd.DataFrame(linhas_p[:5])
                        st.dataframe(df_prev_p, hide_index=True)

                        # Mostrar animais disponíveis para cruzamento
                        _lotes_disp = listar_lotes(owner_id=oid)
                        _animais_disp = []
                        for _l in _lotes_disp:
                            _animais_disp += [
                                a[1] for a in listar_animais_por_lote(_l[0])
                            ]
                        if _animais_disp:
                            st.caption(
                                f"Animais disponíveis no sistema "
                                f"({len(_animais_disp)}): "
                                f"{', '.join(_animais_disp[:10])}"
                                f"{'...' if len(_animais_disp) > 10 else ''}"
                            )
                        else:
                            st.error(
                                "Nenhum animal encontrado para este usuário. "
                                "Cadastre os animais antes de importar pesagens."
                            )

                        if st.button("Confirmar importacao", type="primary",
                                    key="btn_imp_pesagens"):
                            with st.spinner("Importando..."):
                                n_ok, n_err, erros = importar_pesagens_csv(
                                    linhas_p, oid
                                )
                            if n_ok:
                                st.success(
                                    f"{n_ok} pesagem(ns) importada(s) com sucesso!"
                                )
                            if n_err:
                                st.warning(f"{n_err} linha(s) com erro:")
                                for e in erros[:15]:
                                    st.caption(f"  ⚠ {e}")
                            if not n_ok and not n_err:
                                st.error("Nenhuma pesagem importada. Verifique o arquivo.")

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

    st.title("Configure o Auroque")
    st.caption("Complete os passos abaixo para aproveitar tudo que o Auroque oferece")
    st.progress(pct / 100)
    st.caption(f"{concluidos} de {total} passos concluidos ({pct}%)")

    if concluidos == total:
        st.success(
            "Configuracao completa! Voce ja pode usar todos os recursos do Auroque."
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
                    toast_ok("Perfil salvo!")
                    st.rerun()
    else:
        st.caption("Perfil configurado")

    # PASSO 2: Fazenda
    _passo_header(2, "Configure sua fazenda", prog["fazenda"])
    if not prog["fazenda"]:
        with st.expander("Configurar agora", expanded=True):
            st.info(
                "Sua conta ja representa sua fazenda no Auroque. "
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
                "Os alertas do Auroque funcionam automaticamente: "
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
                    st.success("Configuracao concluida! Bem-vindo ao Auroque!")
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
    _lim = verificar_limite_animais(oid)
    atual = _lim["atual"]
    lim   = _lim["limite"]
    _pode = _lim["ok"]

    st.title("Planos Auroque")
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

    # Cards de planos — design moderno
    planos_order = ["free","pro","vet","enterprise"]
    _icones = {
        "free":       ("ti-seedling",       "#F1EFE8", "#5F5E5A"),
        "pro":        ("ti-chart-line",     "#E1F5EE", "#0F6E56"),
        "vet":        ("ti-stethoscope",    "#E6F1FB", "#185FA5"),
        "enterprise": ("ti-building-estate","#FAEEDA", "#854F0B"),
    }

    # Cards via components para renderizar HTML/CSS completo
    import streamlit.components.v1 as _components

    _feats_map = {
        "free":       [("ok","Ate 50 animais"),("ok","1 fazenda"),("ok","Calendario sanitario"),("no","Modulo veterinario"),("no","Relatorios avancados")],
        "pro":        [("ok","Ate 500 animais"),("ok","3 fazendas"),("ok","Calendario sanitario"),("ok","Relatorios avancados"),("no","Modulo veterinario")],
        "vet":        [("ok","Ate 2.000 animais"),("ok","10 fazendas"),("ok","Modulo veterinario"),("ok","Relatorios avancados"),("ok","Mapa epidemiologico")],
        "enterprise": [("ok","Animais ilimitados"),("ok","Fazendas ilimitadas"),("ok","Tudo do plano Vet"),("ok","Suporte dedicado"),("ok","API personalizada")],
    }
    _icones = {
        "free":       ("🌱", "#F1EFE8"),
        "pro":        ("📈", "#E1F5EE"),
        "vet":        ("🩺", "#E6F1FB"),
        "enterprise": ("🏢", "#FAEEDA"),
    }
    _popular    = "pro"
    plano_key_atual = plano_atual.get("plano_key","free")

    _cards_html = ""
    for plano_key in ["free","pro","vet","enterprise"]:
        info     = _PLANOS[plano_key]
        is_atual = (plano_key == plano_key_atual)
        icone_emoji, bg_ico = _icones[plano_key]

        # Preco
        if plano_key == "free":
            preco_str = "Gratis"
            periodo_str = ""
        elif plano_key == "enterprise":
            preco_str = "Sob consulta"
            periodo_str = ""
        else:
            preco_str = f"R${info['preco']}"
            periodo_str = "/mes"

        # Features
        feats_html = ""
        for cls, txt in _feats_map[plano_key]:
            cor  = "#1D9E75" if cls == "ok" else "#aaa"
            simb = "&#10003;" if cls == "ok" else "&#8722;"
            feats_html += (
                f'<div style="display:flex;align-items:center;gap:8px;'
                f'font-size:12px;color:#555;margin:3px 0">'
                f'<span style="color:{cor};font-weight:700;font-size:13px">'
                f'{simb}</span>{txt}</div>'
            )

        # Barra de uso
        barra_html = ""
        if is_atual:
            pct_uso = int(100 * atual / max(lim, 1))
            barra_html = f"""
            <div style="margin-top:6px">
                <div style="display:flex;justify-content:space-between;
                    font-size:10px;color:#888;margin-bottom:3px">
                    <span>Animais usados</span><span>{atual}/{lim}</span>
                </div>
                <div style="height:4px;background:#e0e0e0;border-radius:2px;overflow:hidden">
                    <div style="height:100%;width:{pct_uso}%;
                        background:#1D9E75;border-radius:2px"></div>
                </div>
            </div>"""

        # Badge popular
        badge_html = ""
        if plano_key == _popular:
            badge_html = """
            <div style="position:absolute;top:-12px;left:50%;
                transform:translateX(-50%);background:#1D9E75;
                color:#fff;font-size:11px;font-weight:600;
                padding:3px 14px;border-radius:20px;white-space:nowrap">
                Mais popular
            </div>"""

        # Borda
        borda = "2px solid #1D9E75" if plano_key == _popular else "1px solid #e0e0e0"
        bg_card = "#fff"

        # Badge plano atual
        atual_badge = ""
        if is_atual:
            atual_badge = (
                '<span style="display:inline-block;background:#f0f0f0;'
                'color:#666;font-size:10px;padding:1px 8px;border-radius:20px;'
                'margin-top:2px">plano atual</span>'
            )

        # CTA
        if is_atual:
            cta_html = (
                '<button disabled style="width:100%;margin-top:auto;'
                'padding:8px;border-radius:8px;border:1px solid #ddd;'
                'background:#f5f5f5;color:#aaa;font-size:12px;cursor:default">'
                'Plano atual</button>'
            )
        elif plano_key == "enterprise":
            cta_html = (
                '<button style="width:100%;margin-top:auto;padding:8px;'
                'border-radius:8px;border:1px solid #ccc;background:#fff;'
                'color:#333;font-size:12px;cursor:pointer">'
                'Falar com vendas</button>'
            )
        else:
            cta_html = (
                '<button style="width:100%;margin-top:auto;padding:8px;'
                'border-radius:8px;border:none;background:#1D9E75;'
                'color:#fff;font-size:12px;font-weight:600;cursor:pointer">'
                'Fazer upgrade</button>'
            )

        _cards_html += f"""
        <div style="position:relative;background:{bg_card};
            border:{borda};border-radius:14px;padding:18px 14px;
            display:flex;flex-direction:column;gap:8px">
            {badge_html}
            <div style="width:40px;height:40px;border-radius:10px;
                background:{bg_ico};display:flex;align-items:center;
                justify-content:center;font-size:20px">{icone_emoji}</div>
            <div>
                <div style="font-size:15px;font-weight:600;color:#1a1a1a">
                    {info['nome']}</div>
                {atual_badge}
            </div>
            <div style="display:flex;align-items:baseline;gap:4px">
                <span style="font-size:{'22px' if len(preco_str)<8 else '16px'};
                    font-weight:700;color:#1a1a1a">{preco_str}</span>
                <span style="font-size:11px;color:#888">{periodo_str}</span>
            </div>
            <div style="font-size:11px;color:#666;line-height:1.4">
                {info['descricao']}</div>
            <div style="height:1px;background:#f0f0f0;margin:2px 0"></div>
            <div style="flex:1">{feats_html}</div>
            {barra_html}
            {cta_html}
        </div>"""

    _html_full = f"""
    <div style="display:grid;
        grid-template-columns:repeat(4,1fr);gap:16px;padding:8px 4px">
        {_cards_html}
    </div>"""

    _components.html(_html_full, height=480, scrolling=False)

    st.divider()

    # Contato para upgrade
    st.subheader("Fazer upgrade")
    st.info(
        "Para fazer upgrade ou downgrade do seu plano, "
        "entre em contato pelo WhatsApp ou email abaixo."
    )
    cc1, cc2 = st.columns(2)
    with cc1:
        st.markdown("📧 **contato@auroque.com.br**")
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
                        toast_ok("Email enviado!")
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
                toast_ok("Email enviado para {email}!")
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
                "Auroque — Teste de configuracao SMTP",
                "<h2>Funcionou!</h2><p>Seu SMTP esta configurado corretamente.</p>",
                "Auroque: SMTP configurado corretamente."
            )
            if ok:
                toast_ok("Email de teste enviado com sucesso!")
            else:
                st.error(f"Falha: {msg}")
