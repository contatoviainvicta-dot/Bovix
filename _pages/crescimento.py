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
def page_dados_exemplo(u):
    """Tela para criar ou remover dados de demonstração."""
    from ux_helpers import toast_ok, toast_erro
    from database import criar_dados_demo, remover_dados_demo

    st.subheader("🎯 Dados de Exemplo")
    st.caption("Explore o Auroque com uma fazenda fictícia completa")

    _oid = u.get("owner_id") or u["id"]

    st.markdown("""
Crie uma **fazenda demo** com dados realistas para explorar todas as funcionalidades
antes de cadastrar seus dados reais:
- **8 animais** Nelore e Angus com histórico completo
- **4 pesagens** por animal ao longo de 90 dias
- **Custos variáveis** de ração, medicamentos e mão de obra
- **KPIs e gráficos** já preenchidos para você explorar
""")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🌱 Criar dados de exemplo", type="primary",
                     key="btn_criar_demo", use_container_width=True):
            with st.spinner("Criando fazenda demo..."):
                ok = criar_dados_demo(_oid)
            if ok:
                toast_ok("Dados demo criados! Explore o Dashboard.")
                st.balloons()
            else:
                toast_erro("Erro ao criar dados demo.")

    with c2:
        if st.button("🗑️ Remover dados de exemplo",
                     key="btn_remover_demo", use_container_width=True):
            from ux_helpers import confirmar_acao
            if confirmar_acao(
                "Isso removerá todos os lotes e animais com 'Demo' no nome.",
                "rm_demo", "Sim, remover"
            ):
                ok = remover_dados_demo(_oid)
                if ok:
                    toast_ok("Dados demo removidos.")
                else:
                    toast_erro("Erro ao remover.")

    st.divider()
    st.markdown("### 🗺️ Tour do sistema")
    st.caption("Clique nos botões abaixo para explorar cada módulo")

    tour_itens = [
        ("🏠", "1. Dashboard",      "Inicio",            "Veja os KPIs da sua fazenda"),
        ("🐄", "2. Workspace",      "Workspace do Lote", "Visão completa do lote"),
        ("💰", "3. Financeiro",     "Dashboard Financeiro","DRE e projeção de abate"),
        ("📊", "4. Análise IA",     "Risco Sanitario IA","Score de risco dos animais"),
        ("📋", "5. Prontuário",     "Prontuario Animal", "Histórico clínico"),
        ("⚙️", "6. Planos",         "Planos",            "Conheça os planos"),
    ]

    cols = st.columns(3)
    for i, (icone, titulo, destino, desc) in enumerate(tour_itens):
        with cols[i % 3]:
            st.markdown(f"""
<div style="border:1px solid #e5e7eb;border-radius:10px;padding:12px;
     margin-bottom:8px;text-align:center">
  <div style="font-size:24px">{icone}</div>
  <div style="font-weight:600;font-size:13px;color:#1B4332">{titulo}</div>
  <div style="font-size:11px;color:#6B7280;margin-top:2px">{desc}</div>
</div>
""", unsafe_allow_html=True)
            if st.button(f"Ir →", key=f"tour_{i}",
                         use_container_width=True):
                st.session_state.menu = destino
                st.rerun()


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
    try:
        oid = int(u.get("owner_id") or u["id"])
    except (TypeError, ValueError):
        oid = u.get("id", 1)
    try:
        plano_atual = obter_plano(oid) or {}
    except Exception:
        plano_atual = {}
    try:
        _lim = verificar_limite_animais(oid) or {}
        atual = int(_lim.get("atual", 0))
        lim   = int(_lim.get("limite", 50))
        _pode = bool(_lim.get("ok", True))
    except Exception:
        atual, lim, _pode = 0, 50, True

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

    st.progress(min(int(atual) / max(int(lim), 1), 1.0))
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
    plano_key_atual = (plano_atual or {}).get("plano_key","free")

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

    st.html(_html_full)

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
            st.info("Nenhum alerta ativo no momento.")

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

def page_ferramentas_publicas(u=None):
    """Página pública de ferramentas — sem necessidade de login."""
    from datetime import date, timedelta
    import math

    # ── CSS da página pública ─────────────────────────────────────────
    st.markdown("""
<style>
.ferr-hero{
  background:linear-gradient(135deg,#1B4332 0%,#2D6A4F 50%,#40916C 100%);
  border-radius:16px;padding:32px 36px;margin-bottom:24px;color:white;
}
.ferr-titulo{font-family:Georgia,serif;font-size:28px;font-weight:700;
  margin:0 0 6px}
.ferr-sub{font-size:15px;opacity:.85;margin:0 0 20px}
.ferr-cta-btn{
  display:inline-block;background:#F5F0E8;color:#1B4332;
  font-weight:700;font-size:14px;padding:10px 24px;border-radius:8px;
  text-decoration:none;letter-spacing:.3px;
}
.ferr-card{
  background:white;border:1px solid #E5E7EB;border-radius:12px;
  padding:20px 24px;margin-bottom:16px;
}
.ferr-card-titulo{font-size:16px;font-weight:700;color:#1B4332;
  margin-bottom:4px}
.ferr-card-sub{font-size:12px;color:#6B7280;margin-bottom:16px}
.ferr-resultado{
  background:#E8F5EE;border:2px solid #40916C;border-radius:10px;
  padding:16px 20px;margin-top:12px;
}
.ferr-res-label{font-size:11px;color:#40916C;letter-spacing:1px;
  text-transform:uppercase;margin-bottom:4px}
.ferr-res-valor{font-size:28px;font-weight:700;color:#1B4332}
.ferr-res-detalhe{font-size:12px;color:#6B7280;margin-top:4px}
.ferr-cta-inline{
  background:#1B4332;border-radius:10px;padding:16px 20px;
  margin-top:16px;display:flex;align-items:center;justify-content:space-between;
  flex-wrap:wrap;gap:12px;
}
.ferr-cta-texto{color:white;font-size:13px;font-weight:500}
.ferr-cta-link{
  background:#40916C;color:white;padding:8px 18px;border-radius:6px;
  font-size:12px;font-weight:700;text-decoration:none;white-space:nowrap;
}
</style>
""", unsafe_allow_html=True)

    # ── Hero com CTA ──────────────────────────────────────────────────
    st.markdown("""
<div class="ferr-hero">
  <div class="ferr-titulo">🐄 Ferramentas Gratuitas para Pecuária</div>
  <div class="ferr-sub">
    Calcule GMD, previsão de abate, custo por arroba e muito mais.<br>
    Sem cadastro. Sem limite. 100% gratuito.
  </div>
  <a class="ferr-cta-btn" href="https://2qemgappujzfxkzrbez75v7.streamlit.app"
     target="_blank">
    🚀 Gerenciar meu rebanho no Auroque →
  </a>
</div>
""", unsafe_allow_html=True)

    # ── Abas das ferramentas ──────────────────────────────────────────
    _t1, _t2, _t3, _t4, _t5 = st.tabs([
        "⚡ GMD",
        "🔪 Previsão de Abate",
        "💰 Custo / Arroba",
        "📅 Calendário Sanitário",
        "🌿 Lotação de Pastagem",
    ])

    # ── FERRAMENTA 1: GMD ─────────────────────────────────────────────
    with _t1:
        st.markdown("""<div class="ferr-card">
<div class="ferr-card-titulo">⚡ Calculadora de GMD</div>
<div class="ferr-card-sub">Ganho Médio Diário de peso do animal</div>
</div>""", unsafe_allow_html=True)

        _c1, _c2, _c3 = st.columns(3)
        with _c1:
            _pi = st.number_input("Peso inicial (kg)", min_value=100.0,
                                  max_value=800.0, value=300.0, step=5.0,
                                  key="gmd_pi")
        with _c2:
            _pf = st.number_input("Peso final (kg)", min_value=100.0,
                                  max_value=800.0, value=420.0, step=5.0,
                                  key="gmd_pf")
        with _c3:
            _dias = st.number_input("Dias no período", min_value=1,
                                    max_value=730, value=90, key="gmd_dias")

        if _pf > _pi and _dias > 0:
            _gmd = (_pf - _pi) / _dias
            _class = ("Excelente 🟢" if _gmd >= 1.2
                      else "Bom 🟡" if _gmd >= 0.8
                      else "Abaixo do esperado 🔴")
            st.markdown(f"""
<div class="ferr-resultado">
  <div class="ferr-res-label">GMD calculado</div>
  <div class="ferr-res-valor">{_gmd:.3f} kg/dia</div>
  <div class="ferr-res-detalhe">
    Ganho total: {_pf-_pi:.0f} kg em {_dias} dias · Classificação: {_class}
  </div>
</div>
<div class="ferr-cta-inline">
  <div class="ferr-cta-texto">
    💡 No Auroque, o GMD é calculado automaticamente para cada animal do seu lote
  </div>
  <a class="ferr-cta-link"
     href="https://2qemgappujzfxkzrbez75v7.streamlit.app" target="_blank">
    Ver no meu rebanho →
  </a>
</div>
""", unsafe_allow_html=True)
        elif _pf <= _pi:
            st.warning("O peso final deve ser maior que o peso inicial.")

    # ── FERRAMENTA 2: PREVISÃO DE ABATE ───────────────────────────────
    with _t2:
        st.markdown("""<div class="ferr-card">
<div class="ferr-card-titulo">🔪 Previsão de Abate</div>
<div class="ferr-card-sub">Quando o animal atingirá o peso ideal de abate</div>
</div>""", unsafe_allow_html=True)

        _c1, _c2, _c3 = st.columns(3)
        with _c1:
            _pa_atual = st.number_input("Peso atual (kg)", min_value=100.0,
                                        max_value=800.0, value=380.0, step=5.0,
                                        key="abate_pa")
        with _c2:
            _pa_alvo  = st.number_input("Peso alvo de abate (kg)", min_value=100.0,
                                        max_value=800.0, value=500.0, step=5.0,
                                        key="abate_alvo")
        with _c3:
            _pa_gmd   = st.number_input("GMD esperado (kg/dia)", min_value=0.1,
                                        max_value=3.0, value=1.0, step=0.05,
                                        key="abate_gmd")

        if _pa_alvo > _pa_atual and _pa_gmd > 0:
            _dias_abate = math.ceil((_pa_alvo - _pa_atual) / _pa_gmd)
            _data_abate = date.today() + timedelta(days=_dias_abate)
            _arrobas    = _pa_alvo * 0.5 / 15
            st.markdown(f"""
<div class="ferr-resultado">
  <div class="ferr-res-label">Previsão de abate</div>
  <div class="ferr-res-valor">{_data_abate.strftime('%d/%m/%Y')}</div>
  <div class="ferr-res-detalhe">
    {_dias_abate} dias restantes ·
    Peso faltando: {_pa_alvo-_pa_atual:.0f} kg ·
    Rendimento estimado: {_arrobas:.1f} @
  </div>
</div>
<div class="ferr-cta-inline">
  <div class="ferr-cta-texto">
    💡 O Auroque calcula isso automaticamente para todos os animais do lote
  </div>
  <a class="ferr-cta-link"
     href="https://2qemgappujzfxkzrbez75v7.streamlit.app" target="_blank">
    Testar grátis →
  </a>
</div>
""", unsafe_allow_html=True)

    # ── FERRAMENTA 3: CUSTO / ARROBA ──────────────────────────────────
    with _t3:
        st.markdown("""<div class="ferr-card">
<div class="ferr-card-titulo">💰 Custo e Margem por Arroba</div>
<div class="ferr-card-sub">
  Calcule o custo de produção e a margem esperada na venda
</div>
</div>""", unsafe_allow_html=True)

        _c1, _c2 = st.columns(2)
        with _c1:
            _cv_compra  = st.number_input("Custo de compra (R$)", min_value=0.0,
                                           value=3000.0, step=100.0, key="arr_compra")
            _cv_racao   = st.number_input("Ração e suplementos (R$)", min_value=0.0,
                                           value=800.0, step=50.0, key="arr_racao")
            _cv_sanit   = st.number_input("Sanidade/veterinário (R$)", min_value=0.0,
                                           value=150.0, step=10.0, key="arr_sanit")
        with _c2:
            _cv_outros  = st.number_input("Outros custos (R$)", min_value=0.0,
                                           value=200.0, step=10.0, key="arr_outros")
            _cv_peso_v  = st.number_input("Peso de venda (kg)", min_value=100.0,
                                           value=500.0, step=10.0, key="arr_peso")
            _cv_preco_a = st.number_input("Preço da arroba (R$)", min_value=0.0,
                                           value=320.0, step=5.0, key="arr_preco")

        _custo_total = _cv_compra + _cv_racao + _cv_sanit + _cv_outros
        _arrobas_v   = _cv_peso_v * 0.5 / 15
        _receita     = _arrobas_v * _cv_preco_a
        _margem      = _receita - _custo_total
        _custo_at    = _custo_total / _arrobas_v if _arrobas_v > 0 else 0
        _margem_pct  = (_margem / _custo_total * 100) if _custo_total > 0 else 0
        _cor_m       = "#1B4332" if _margem >= 0 else "#E24B4A"

        st.markdown(f"""
<div class="ferr-resultado">
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">
    <div>
      <div class="ferr-res-label">Custo total</div>
      <div class="ferr-res-valor" style="font-size:22px">
        R$ {_custo_total:,.0f}</div>
    </div>
    <div>
      <div class="ferr-res-label">Receita estimada</div>
      <div class="ferr-res-valor" style="font-size:22px">
        R$ {_receita:,.0f}</div>
    </div>
    <div>
      <div class="ferr-res-label">Margem</div>
      <div class="ferr-res-valor" style="font-size:22px;color:{_cor_m}">
        R$ {_margem:,.0f}</div>
    </div>
  </div>
  <div class="ferr-res-detalhe" style="margin-top:8px">
    Custo/@ R$ {_custo_at:.0f} ·
    {_arrobas_v:.1f} arrobas ·
    Margem {_margem_pct:.1f}%
  </div>
</div>
<div class="ferr-cta-inline">
  <div class="ferr-cta-texto">
    💡 No Auroque, o DRE completo é gerado automaticamente por lote
  </div>
  <a class="ferr-cta-link"
     href="https://2qemgappujzfxkzrbez75v7.streamlit.app" target="_blank">
    Ver DRE completo →
  </a>
</div>
""", unsafe_allow_html=True)

    # ── FERRAMENTA 4: CALENDÁRIO SANITÁRIO ───────────────────────────
    with _t4:
        st.markdown("""<div class="ferr-card">
<div class="ferr-card-titulo">📅 Calendário Sanitário</div>
<div class="ferr-card-sub">
  Vacinas e procedimentos recomendados por fase do lote
</div>
</div>""", unsafe_allow_html=True)

        _fase = st.selectbox("Fase / categoria do lote", [
            "Cria (0-6 meses)",
            "Recria (7-18 meses)",
            "Engorda (19-30 meses)",
            "Vacas em produção",
            "Touros",
        ], key="cal_fase")

        _calendario = {
            "Cria (0-6 meses)": [
                ("Brucelose (fêmeas 3-8 meses)", "Obrigatória", "3-8 meses"),
                ("Febre Aftosa", "Obrigatória", "Campanhas oficiais"),
                ("Clostridioses (polivalente)", "Recomendada", "2-3 meses"),
                ("Raiva", "Recomendada", "Regiões de risco"),
                ("Vermifugação estratégica", "Recomendada", "A cada 90 dias"),
            ],
            "Recria (7-18 meses)": [
                ("Febre Aftosa", "Obrigatória", "Campanhas oficiais"),
                ("Raiva", "Recomendada", "Anual"),
                ("Clostridioses (polivalente)", "Recomendada", "Anual"),
                ("Vermifugação", "Recomendada", "A cada 90 dias"),
                ("Carrapatos (banho/pour-on)", "Recomendada", "Monitorar"),
            ],
            "Engorda (19-30 meses)": [
                ("Febre Aftosa", "Obrigatória", "Campanhas oficiais"),
                ("Clostridioses (polivalente)", "Recomendada", "Entrada no confinamento"),
                ("Vermifugação estratégica", "Recomendada", "Entrada + 60 dias"),
                ("Controle de carrapatos", "Recomendada", "Monitorar"),
                ("IBR / BVD", "Recomendada", "Entrada no confinamento"),
            ],
            "Vacas em produção": [
                ("Brucelose (não vacinadas)", "Obrigatória", "Verificar status"),
                ("Febre Aftosa", "Obrigatória", "Campanhas oficiais"),
                ("Clostridioses", "Recomendada", "Anual — pré-parto"),
                ("Leptospirose", "Recomendada", "Anual"),
                ("Vermifugação pós-parto", "Recomendada", "30 dias pós-parto"),
            ],
            "Touros": [
                ("Febre Aftosa", "Obrigatória", "Campanhas oficiais"),
                ("Brucelose (exame)", "Obrigatória", "Anual"),
                ("Clostridioses", "Recomendada", "Anual"),
                ("Leptospirose", "Recomendada", "Antes da estação"),
                ("Exame andrológico", "Recomendada", "Anual — pré-estação"),
            ],
        }

        import pandas as _pd_cal
        _df_cal = _pd_cal.DataFrame(
            _calendario[_fase],
            columns=["Procedimento", "Tipo", "Frequência / Quando"]
        )
        st.dataframe(_df_cal, hide_index=True, use_container_width=True)

        st.markdown(f"""
<div class="ferr-cta-inline">
  <div class="ferr-cta-texto">
    💡 No Auroque, o calendário sanitário é gerado automaticamente
    com alertas no celular via WhatsApp
  </div>
  <a class="ferr-cta-link"
     href="https://2qemgappujzfxkzrbez75v7.streamlit.app" target="_blank">
    Criar meu calendário →
  </a>
</div>
""", unsafe_allow_html=True)

    # ── FERRAMENTA 5: LOTAÇÃO DE PASTAGEM ─────────────────────────────
    with _t5:
        st.markdown("""<div class="ferr-card">
<div class="ferr-card-titulo">🌿 Calculadora de Lotação de Pastagem</div>
<div class="ferr-card-sub">
  Quantos animais sua área suporta com segurança
</div>
</div>""", unsafe_allow_html=True)

        _c1, _c2 = st.columns(2)
        with _c1:
            _area_ha  = st.number_input("Área total (hectares)", min_value=1.0,
                                         value=50.0, step=1.0, key="lot_area")
            _capac_ua = st.number_input("Capacidade de suporte (UA/ha)", min_value=0.1,
                                         max_value=10.0, value=1.5, step=0.1,
                                         key="lot_capac",
                                         help="Brachiaria: 1-2 UA/ha · Panicum: 2-4 UA/ha · Intensivo: 4-8 UA/ha")
        with _c2:
            _peso_med = st.number_input("Peso médio dos animais (kg)", min_value=100.0,
                                         value=400.0, step=10.0, key="lot_peso")
            _tipo_past = st.selectbox("Tipo de pastagem", [
                "Brachiaria brizantha",
                "Brachiaria decumbens",
                "Panicum maximum (Mombaça)",
                "Panicum maximum (Tanzânia)",
                "Tifton 85 (irrigado)",
                "Outro",
            ], key="lot_tipo")

        # 1 UA = 450 kg de peso vivo
        _ua_por_animal = _peso_med / 450
        _ua_total      = _area_ha * _capac_ua
        _n_animais     = math.floor(_ua_total / _ua_por_animal)
        _ua_usada_pct  = (_ua_por_animal * _n_animais / _ua_total * 100)

        _refs_capac = {
            "Brachiaria brizantha":         "1,5 – 2,5 UA/ha",
            "Brachiaria decumbens":          "1,0 – 1,8 UA/ha",
            "Panicum maximum (Mombaça)":     "2,5 – 4,0 UA/ha",
            "Panicum maximum (Tanzânia)":    "2,0 – 3,5 UA/ha",
            "Tifton 85 (irrigado)":          "4,0 – 8,0 UA/ha",
            "Outro":                         "Consulte um agrônomo",
        }

        st.markdown(f"""
<div class="ferr-resultado">
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">
    <div>
      <div class="ferr-res-label">Animais suportados</div>
      <div class="ferr-res-valor">{_n_animais}</div>
    </div>
    <div>
      <div class="ferr-res-label">UA total da área</div>
      <div class="ferr-res-valor">{_ua_total:.1f} UA</div>
    </div>
    <div>
      <div class="ferr-res-label">UA por animal</div>
      <div class="ferr-res-valor">{_ua_por_animal:.2f} UA</div>
    </div>
  </div>
  <div class="ferr-res-detalhe" style="margin-top:8px">
    Referência {_tipo_past}: {_refs_capac[_tipo_past]} ·
    Ocupação: {_ua_usada_pct:.0f}% da capacidade
  </div>
</div>
<div class="ferr-cta-inline">
  <div class="ferr-cta-texto">
    💡 No Auroque você monitora piquetes e rotação de pastagem em tempo real
  </div>
  <a class="ferr-cta-link"
     href="https://2qemgappujzfxkzrbez75v7.streamlit.app" target="_blank">
    Conhecer o Auroque →
  </a>
</div>
""", unsafe_allow_html=True)

    # ── Rodapé CTA ────────────────────────────────────────────────────
    st.divider()
    st.markdown("""
<div style="text-align:center;padding:24px 16px">
  <div style="font-size:22px;font-weight:700;color:#1B4332;margin-bottom:8px">
    Gostou das ferramentas?
  </div>
  <div style="font-size:14px;color:#6B7280;margin-bottom:16px">
    No Auroque, tudo isso é automático — GMD, previsão de abate, DRE,
    calendário sanitário e muito mais. Gerencie seu rebanho com inteligência.
  </div>
  <a href="https://2qemgappujzfxkzrbez75v7.streamlit.app" target="_blank"
     style="background:#1B4332;color:white;font-size:15px;font-weight:700;
            padding:14px 32px;border-radius:10px;text-decoration:none;
            display:inline-block">
    🚀 Criar conta gratuita no Auroque
  </a>
  <div style="font-size:12px;color:#9CA3AF;margin-top:12px">
    Grátis para até 50 animais · Sem cartão de crédito
  </div>
</div>
""", unsafe_allow_html=True)
