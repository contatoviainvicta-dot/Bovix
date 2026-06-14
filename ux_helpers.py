"""
ux_helpers.py — Helpers de UX reutilizáveis para o Auroque
Toasts, empty states, confirmações, mensagens humanizadas
"""
import streamlit as st


# ── FORMATAÇÃO GLOBAL ────────────────────────────────────────
_MESES_ABR = {
    1:"jan", 2:"fev", 3:"mar", 4:"abr", 5:"mai", 6:"jun",
    7:"jul", 8:"ago", 9:"set", 10:"out", 11:"nov", 12:"dez"
}

def fmt_brl(valor):
    """Formata valor monetário: R$ 1.250,00"""
    try:
        v = float(valor)
        neg = v < 0
        # Separar inteiro e centavos
        inteiro = int(abs(v))
        centavos = round((abs(v) - inteiro) * 100)
        # Formatar inteiro com ponto de milhar
        s_int = f"{inteiro:,}".replace(",", ".")
        s = f"R$ {s_int},{centavos:02d}"
        return f"-{s}" if neg else s
    except Exception:
        return "R$ 0,00"


def fmt_data(data, hora=False):
    """Formata data: 12 jan 2025. Aceita str YYYY-MM-DD, date ou datetime."""
    try:
        from datetime import date, datetime
        if not data or str(data) in ("None", "", "nan"):
            return "—"
        if isinstance(data, str):
            data = data[:10]  # pegar só a parte de data
            ano, mes, dia = int(data[:4]), int(data[5:7]), int(data[8:10])
        elif isinstance(data, (date, datetime)):
            ano, mes, dia = data.year, data.month, data.day
        else:
            return str(data)[:10]
        s = f"{dia:02d} {_MESES_ABR[mes]} {ano}"
        if hora and hasattr(data, 'hour'):
            s += f" {data.hour:02d}:{data.minute:02d}"
        return s
    except Exception:
        return str(data)[:10] if data else "—"


def fmt_data_hora(data):
    """Formata data e hora: 12 jan 2025 14:30"""
    try:
        from datetime import datetime
        if isinstance(data, str):
            # Tentar parsear ISO
            dt = datetime.fromisoformat(data[:19])
            return f"{dt.day:02d} {_MESES_ABR[dt.month]} {dt.year} {dt.hour:02d}:{dt.minute:02d}"
        return fmt_data(data, hora=True)
    except Exception:
        return str(data)[:16] if data else "—"


# ── GRÁFICOS SEGUROS (protegidos contra df vazio/NaN) ───────────
def safe_line_chart(df, titulo=None, empty_msg="Dados insuficientes para o gráfico."):
    """st.line_chart protegido contra df vazio, None e NaN.
    Usa matplotlib como fallback para compatibilidade com Python 3.14+.
    """
    import streamlit as st
    import pandas as pd

    if df is None or (hasattr(df, 'empty') and df.empty):
        if titulo: st.caption(titulo)
        st.info(empty_msg)
        return

    try:
        df = pd.DataFrame(df).replace([float('inf'), float('-inf')], None)
        df = df.dropna(how='all')
        if df.empty:
            st.info(empty_msg)
            return
        if titulo:
            st.caption(titulo)
        # Tentar st.line_chart nativo
        st.line_chart(df)
    except Exception:
        # Fallback: matplotlib (compatível com Python 3.14+)
        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates

            fig, ax = plt.subplots(figsize=(10, 3))
            fig.patch.set_facecolor('#FAFAFA')
            ax.set_facecolor('#FAFAFA')

            df_plot = pd.DataFrame(df)
            for col in df_plot.columns:
                ax.plot(df_plot.index, df_plot[col],
                        color='#1B4332', linewidth=2, marker='o',
                        markersize=4, label=str(col))

            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color('#E5E7EB')
            ax.spines['bottom'].set_color('#E5E7EB')
            ax.tick_params(colors='#6B7280', labelsize=9)
            ax.grid(axis='y', color='#F3F4F6', linewidth=0.8)

            # Formatar eixo X se for datas
            if hasattr(df_plot.index, 'dtype') and 'datetime' in str(df_plot.index.dtype):
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
                fig.autofmt_xdate(rotation=30)

            if len(df_plot.columns) > 1:
                ax.legend(fontsize=8)

            plt.tight_layout()
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)
        except Exception as e2:
            st.info(f"Gráfico indisponível: {e2}")


def safe_bar_chart(df, titulo=None, empty_msg="Dados insuficientes para o gráfico."):
    """st.bar_chart protegido contra df vazio, None e NaN.
    Usa matplotlib como fallback para compatibilidade com Python 3.14+.
    """
    import streamlit as st
    import pandas as pd

    if df is None or (hasattr(df, 'empty') and df.empty):
        if titulo: st.caption(titulo)
        st.info(empty_msg)
        return

    try:
        df = pd.DataFrame(df).replace([float('inf'), float('-inf')], None)
        df = df.dropna(how='all')
        if df.empty:
            st.info(empty_msg)
            return
        if titulo:
            st.caption(titulo)
        st.bar_chart(df)
    except Exception:
        try:
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(10, 3))
            fig.patch.set_facecolor('#FAFAFA')
            ax.set_facecolor('#FAFAFA')

            df_plot = pd.DataFrame(df)
            x = range(len(df_plot))
            for i, col in enumerate(df_plot.columns):
                offset = i * 0.8 / max(len(df_plot.columns), 1)
                ax.bar([xi + offset for xi in x], df_plot[col],
                       width=0.8 / max(len(df_plot.columns), 1),
                       color='#1B4332', alpha=0.85, label=str(col))

            ax.set_xticks(list(x))
            ax.set_xticklabels([str(i) for i in df_plot.index],
                               rotation=30, fontsize=9)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.tick_params(colors='#6B7280', labelsize=9)
            ax.grid(axis='y', color='#F3F4F6', linewidth=0.8)

            if len(df_plot.columns) > 1:
                ax.legend(fontsize=8)

            plt.tight_layout()
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)
        except Exception as e2:
            st.info(f"Gráfico indisponível: {e2}")


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


def skeleton_cards(n=4, altura=80):
    """Exibe cards skeleton com animação shimmer enquanto carrega."""
    shimmer_css = """<style>
@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
.sk{background:linear-gradient(90deg,#e8e8e8 25%,#f5f5f5 50%,#e8e8e8 75%);
    background-size:200% 100%;animation:shimmer 1.4s infinite;border-radius:8px}
.sk-line{border-radius:4px;margin-bottom:8px}
</style>"""
    cols = st.columns(n)
    for col in cols:
        col.markdown(
            f"{shimmer_css}"
            f"<div class='sk' style='height:{altura}px;margin-bottom:8px'></div>"
            f"<div class='sk sk-line' style='height:12px;width:70%'></div>"
            f"<div class='sk sk-line' style='height:10px;width:45%'></div>",
            unsafe_allow_html=True
        )


def skeleton_tabela(linhas=5, colunas=4):
    """Exibe skeleton de tabela enquanto dados carregam."""
    shimmer_css = """<style>
@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
.sk{background:linear-gradient(90deg,#e8e8e8 25%,#f5f5f5 50%,#e8e8e8 75%);
    background-size:200% 100%;animation:shimmer 1.4s infinite;
    border-radius:4px;height:12px;margin:2px 0}
</style>"""
    # Header
    widths = [90, 70, 80, 60]
    header = "".join(
        f"<div style='flex:1;padding:8px 4px'>"
        f"<div class='sk' style='width:{widths[i%4]}%'></div></div>"
        for i in range(colunas)
    )
    rows = ""
    for r in range(linhas):
        cols_html = "".join(
            f"<div style='flex:1;padding:8px 4px'>"
            f"<div class='sk' style='width:{[85,65,75,55][i%4]}%'></div></div>"
            for i in range(colunas)
        )
        bg = "#fafafa" if r % 2 else "white"
        rows += (
            f"<div style='display:flex;background:{bg};"
            f"border-bottom:1px solid #f0f0f0'>{cols_html}</div>"
        )
    st.markdown(
        f"{shimmer_css}"
        f"<div style='border:1px solid #e5e7eb;border-radius:8px;overflow:hidden'>"
        f"<div style='display:flex;background:#f9fafb;border-bottom:2px solid #e5e7eb'>"
        f"{header}</div>{rows}</div>",
        unsafe_allow_html=True
    )


# ── PAGINAÇÃO DE TABELAS ─────────────────────────────────────
def paginar_dataframe(df, key, page_size=20, label="registros"):
    """Exibe DataFrame com paginação. Retorna o slice da página atual."""
    import streamlit as st
    import math

    if df is None or (hasattr(df, 'empty') and df.empty):
        return df

    total  = len(df)
    if total <= page_size:
        return df  # sem paginação necessária

    n_pages = math.ceil(total / page_size)

    # Controles de paginação
    _c1, _c2, _c3 = st.columns([1, 2, 1])
    with _c1:
        st.caption(f"{total} {label} · {n_pages} páginas")
    with _c2:
        pagina = st.number_input(
            "Página", min_value=1, max_value=n_pages,
            value=st.session_state.get(f"_pag_{key}", 1),
            step=1, key=f"_pag_inp_{key}", label_visibility="collapsed"
        )
        st.session_state[f"_pag_{key}"] = pagina
    with _c3:
        ini = (pagina - 1) * page_size + 1
        fim = min(pagina * page_size, total)
        st.caption(f"{ini}–{fim}")

    start = (pagina - 1) * page_size
    return df.iloc[start:start + page_size]


def tabela_paginada(df, key, page_size=20, label="registros", **kwargs):
    """Exibe DataFrame paginado com st.dataframe."""
    import streamlit as st
    df_page = paginar_dataframe(df, key, page_size, label)
    if df_page is not None and not (hasattr(df_page, 'empty') and df_page.empty):
        st.dataframe(df_page, hide_index=True, **kwargs)


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

/* ── SIDEBAR AUROQUE ───────────────────────────────────── */

/* 1. Fundo verde */
[data-testid="stSidebar"] { background-color: #1B4332 !important; }
[data-testid="stSidebar"] > div:first-child { background-color: #1B4332 !important; }

/* 2. Texto bege — apenas em elementos de texto, NÃO em * para não quebrar ícones */
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span:not([data-testid]),
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] div.stMarkdown p {
    color: #F5F0E8 !important;
    font-size: 16px !important;
}

/* 3. Botões: fundo transparente SEMPRE — usar !important em todos os estados */
[data-testid="stSidebar"] button {
    background-color: #1B4332 !important;
    border: 1px solid rgba(245,240,232,0.25) !important;
    border-radius: 6px !important;
    color: #F5F0E8 !important;
    font-size: 16px !important;
    width: 100% !important;
    text-align: left !important;
    padding: 8px 12px !important;
    margin: 2px 0 !important;
    min-height: 40px !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] button:hover {
    background-color: #40916C !important;
    border-color: #52b788 !important;
    color: #ffffff !important;
}
[data-testid="stSidebar"] button:focus,
[data-testid="stSidebar"] button:active {
    background-color: #1B4332 !important;
    color: #F5F0E8 !important;
    box-shadow: none !important;
    outline: none !important;
}

/* 4. Texto dentro dos botões */
[data-testid="stSidebar"] button > div,
[data-testid="stSidebar"] button > div > p,
[data-testid="stSidebar"] button > div > span {
    color: #F5F0E8 !important;
    font-size: 16px !important;
    background: transparent !important;
}
[data-testid="stSidebar"] button:hover > div,
[data-testid="stSidebar"] button:hover > div > p,
[data-testid="stSidebar"] button:hover > div > span {
    color: #ffffff !important;
}

/* 5. Expanders do menu — usar data-testid correto do Streamlit */
[data-testid="stSidebar"] [data-testid="stExpander"] {
    background-color: #1B4332 !important;
    border: 1px solid rgba(245,240,232,0.15) !important;
    border-radius: 6px !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    background-color: #1B4332 !important;
    color: #F5F0E8 !important;
    font-size: 16px !important;
    font-weight: 600 !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {
    background-color: #40916C !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary > span,
[data-testid="stSidebar"] [data-testid="stExpander"] summary > p {
    color: #F5F0E8 !important;
    font-size: 16px !important;
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


# ── PROTEÇÃO GLOBAL DE TELAS ─────────────────────────────────────────────────

def pagina_protegida(fn):
    """Decorator que envolve funções de página com tratamento de erro global.
    Captura qualquer exceção não tratada e exibe mensagem amigável em vez
    de stack trace para o usuário final.

    Uso: @pagina_protegida
         def page_minha_tela(u): ...
    """
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as _e:
            import logging
            logging.getLogger("auroque").error(
                "Erro em %s: %s", fn.__name__, _e, exc_info=True
            )
            st.error(
                f"⚠️ Ocorreu um erro ao carregar esta tela. "
                f"Tente recarregar a página. "
                f"Se o problema persistir, entre em contato com o suporte.",
                icon="🚨"
            )
            with st.expander("Detalhes técnicos (para suporte)", expanded=False):
                st.code(f"{type(_e).__name__}: {_e}")
    return wrapper
