"""
ux_helpers.py — Helpers de UX reutilizáveis para o Auroque
Toasts, empty states, confirmações, mensagens humanizadas
"""
import streamlit as st


# ── TOAST HELPERS ─────────────────────────────────────────────
def toast_ok(msg):
    """Toast de sucesso — desaparece sozinho."""
    st.toast(f"✅ {msg}", icon="✅")


def toast_erro(msg):
    """Toast de erro."""
    st.toast(f"❌ {msg}", icon="❌")


def toast_info(msg):
    """Toast informativo."""
    st.toast(f"ℹ {msg}", icon="ℹ️")


def toast_aviso(msg):
    """Toast de aviso."""
    st.toast(f"⚠ {msg}", icon="⚠️")


# ── MENSAGENS HUMANIZADAS ─────────────────────────────────────
_ERROS_HUMANOS = {
    "duplicate key":       "Esse registro já existe no sistema.",
    "not null":            "Preencha todos os campos obrigatórios.",
    "foreign key":         "Não é possível remover — há registros vinculados.",
    "connection":          "Problema de conexão. Tente novamente em instantes.",
    "timeout":             "A operação demorou demais. Tente novamente.",
    "permission":          "Você não tem permissão para essa ação.",
    "unique":              "Já existe um registro com esse valor.",
    "syntax":              "Erro interno. Contate o suporte.",
    "operational":         "Banco de dados indisponível. Tente em instantes.",
}


def humanizar_erro(e):
    """Converte exceções técnicas em mensagens amigáveis."""
    msg = str(e).lower()
    for chave, texto in _ERROS_HUMANOS.items():
        if chave in msg:
            return texto
    return "Ocorreu um erro inesperado. Tente novamente."


def erro_com_acao(msg_tecnica, acao_sugerida=""):
    """Exibe erro humanizado com ação sugerida."""
    msg = humanizar_erro(msg_tecnica)
    if acao_sugerida:
        st.error(f"{msg}\n\n💡 **O que fazer:** {acao_sugerida}")
    else:
        st.error(msg)


# ── EMPTY STATES ─────────────────────────────────────────────
def empty_state(titulo, descricao, label_cta=None, key_cta=None,
                icone="📋", destino=None):
    """Estado vazio padronizado com call-to-action opcional."""
    st.markdown(
        f"""
        <div style="text-align:center;padding:40px 20px;
             background:var(--color-background-secondary,#f9f9f9);
             border-radius:12px;margin:16px 0;
             border:1px dashed var(--color-border-secondary,#ddd)">
          <div style="font-size:40px;margin-bottom:12px">{icone}</div>
          <div style="font-size:16px;font-weight:600;
               color:var(--color-text-primary,#111);
               margin-bottom:6px">{titulo}</div>
          <div style="font-size:13px;color:var(--color-text-secondary,#666);
               max-width:300px;margin:0 auto">{descricao}</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    if label_cta and key_cta:
        col = st.columns([1, 2, 1])[1]
        if col.button(label_cta, type="primary", key=key_cta):
            if destino:
                st.session_state.menu = destino
                st.rerun()
            return True
    return False


# ── CONFIRMAÇÃO DE AÇÕES DESTRUTIVAS ─────────────────────────
def confirmar_acao(msg, key_prefix, label_confirmar="Confirmar",
                   label_cancelar="Cancelar"):
    """Popup de confirmação para ações destrutivas.
    Retorna True quando confirmado."""
    key_estado  = f"_conf_{key_prefix}"
    key_ok      = f"_conf_ok_{key_prefix}"
    key_cancel  = f"_conf_cancel_{key_prefix}"

    if key_estado not in st.session_state:
        st.session_state[key_estado] = False

    if not st.session_state[key_estado]:
        if st.button(label_confirmar, key=key_ok, type="primary"):
            st.session_state[key_estado] = True
            st.rerun()
        return False

    # Estado de confirmação pendente
    st.warning(f"⚠ {msg}")
    c1, c2 = st.columns(2)
    if c1.button("✅ Sim, confirmar", key=f"{key_ok}_sim",
                type="primary"):
        st.session_state[key_estado] = False
        return True
    if c2.button(f"↩ {label_cancelar}", key=key_cancel):
        st.session_state[key_estado] = False
        st.rerun()
    return False


# ── LOADING SKELETON ─────────────────────────────────────────
def skeleton_linhas(n=3, altura=16):
    """Exibe linhas de skeleton enquanto carrega."""
    html = ""
    for i in range(n):
        w = [90, 70, 80, 60, 85][i % 5]
        html += (
            f"<div style='height:{altura}px;background:#e8e8e8;"
            f"border-radius:4px;margin-bottom:8px;width:{w}%;"
            f"animation:pulse 1.5s infinite'></div>"
        )
    st.markdown(
        f"<style>@keyframes pulse{{0%,100%{{opacity:1}}"
        f"50%{{opacity:0.4}}}}</style>{html}",
        unsafe_allow_html=True
    )


def skeleton_cards(n=4):
    """Exibe cards de skeleton enquanto carrega."""
    cols = st.columns(n)
    for col in cols:
        col.markdown(
            "<div style='height:80px;background:"
            "linear-gradient(90deg,#e8e8e8 25%,#f0f0f0 50%,#e8e8e8 75%);"
            "background-size:200% 100%;border-radius:8px;"
            "animation:shimmer 1.5s infinite'></div>"
            "<style>@keyframes shimmer{0%{background-position:200% 0}"
            "100%{background-position:-200% 0}}</style>",
            unsafe_allow_html=True
        )


# ── CSS GLOBAL AUROQUE ────────────────────────────────────────
_CSS_AUROQUE = """
<style>
/* Tipografia global */
[data-testid="stAppViewContainer"] {
    font-family: system-ui, -apple-system, sans-serif;
}

/* Cabeçalhos h2 — linha verde Auroque (apenas um seletor para evitar duplicata) */
[data-testid="stHeadingWithActionElements"] h2 {
    color: #1B4332 !important;
    font-size: 18px !important;
    font-weight: 600 !important;
    border-bottom: 2px solid #40916C !important;
    padding-bottom: 4px !important;
    margin-bottom: 12px !important;
}
[data-testid="stHeadingWithActionElements"] h3 {
    color: #1B4332 !important;
    font-size: 15px !important;
    font-weight: 600 !important;
}
[data-testid="stMarkdownContainer"] h2 {
    color: #1B4332 !important;
    font-size: 18px !important;
    font-weight: 600 !important;
    border-bottom: 2px solid #40916C !important;
    padding-bottom: 4px !important;
    margin-bottom: 12px !important;
}
[data-testid="stMarkdownContainer"] h3 {
    color: #1B4332 !important;
    font-size: 15px !important;
    font-weight: 600 !important;
}

/* Remover linhas duplicadas do st.divider perto dos títulos */
[data-testid="stHeadingWithActionElements"] + hr,
[data-testid="stHeadingWithActionElements"] hr {
    display: none !important;
}

/* Botão primário — verde Auroque */
[data-testid="baseButton-primary"] {
    background-color: #1B4332 !important;
    border-color: #1B4332 !important;
}
[data-testid="baseButton-primary"]:hover {
    background-color: #40916C !important;
    border-color: #40916C !important;
}

/* Métricas — valor em verde escuro */
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #1B4332 !important;
    font-size: 22px !important;
    font-weight: 700 !important;
}

/* Tabs — ativa em verde */
[data-testid="stTab"][aria-selected="true"] {
    color: #1B4332 !important;
    border-bottom-color: #40916C !important;
    font-weight: 600 !important;
}

/* Dataframe — header verde escuro */
[data-testid="stDataFrame"] th {
    background-color: #1B4332 !important;
    color: white !important;
}

/* Sidebar — fundo verde escuro */
[data-testid="stSidebar"] {
    background-color: #1B4332 !important;
}
/* Todos os textos da sidebar em bege */
[data-testid="stSidebar"],
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] div {
    color: #F5F0E8 !important;
}
/* Botões do menu — tamanho normal, sempre legível */
[data-testid="stSidebar"] button {
    color: #F5F0E8 !important;
    background-color: transparent !important;
    border-color: rgba(255,255,255,0.15) !important;
    text-align: left !important;
    width: 100% !important;
}
[data-testid="stSidebar"] button p,
[data-testid="stSidebar"] button span {
    color: #F5F0E8 !important;
    font-size: 14px !important;
}
[data-testid="stSidebar"] button:hover {
    background-color: rgba(64,145,108,0.35) !important;
    border-color: rgba(64,145,108,0.6) !important;
}
[data-testid="stSidebar"] button:hover p,
[data-testid="stSidebar"] button:hover span {
    color: #ffffff !important;
}
/* Expander na sidebar */
[data-testid="stSidebar"] summary p,
[data-testid="stSidebar"] summary span {
    color: #F5F0E8 !important;
    font-size: 14px !important;
    font-weight: 600 !important;
}

/* Expander geral — borda sutil */
[data-testid="stExpander"] {
    border: 0.5px solid #e0e0e0 !important;
    border-radius: 8px !important;
}

/* Input focus — verde */
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus {
    border-color: #40916C !important;
    box-shadow: 0 0 0 2px rgba(64,145,108,0.15) !important;
}

/* Divider sutil */
hr {
    border-color: #e8e8e8 !important;
    margin: 8px 0 !important;
}
</style>
"""


def aplicar_css_global():
    """Aplica o CSS global do Auroque. Chamar uma vez no início de cada página."""
    st.markdown(_CSS_AUROQUE, unsafe_allow_html=True)
