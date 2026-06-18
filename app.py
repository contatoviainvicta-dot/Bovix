# app.py -- Sistema de Gestao Pecuaria
# Execute: streamlit run app.py

import os as _os

# Verificar/importar design system
try:
    from ui import (
        card_kpi, card_kpi_row, alerta, badge,
        badge_status_animal, badge_status_lote, badge_gravidade,
        card_animal, insight_card,
    )
except ImportError:
    # Fallback simples se ui.py nao estiver disponivel
    def card_kpi(t, v, s='', cor=None, delta=None): pass
    def card_kpi_row(itens): pass
    def alerta(m, t='info'): pass
    def badge(txt, ct, cf): return txt
    def badge_status_animal(s): return s
    def badge_status_lote(s): return s
    def badge_gravidade(g): return g
    def card_animal(*a, **k): return ''
    def insight_card(*a, **k): return ''



# Sistema de logs centralizado
try:
    from bovix_logging import configurar_logs, get_logger
    configurar_logs()
    _log = get_logger("auroque.app")
except Exception as _e:
    import logging
    logging.basicConfig(level=logging.INFO)
    _log = logging.getLogger("auroque.app")

import streamlit as st
from rules import (
    is_admin, is_vet, is_fazendeiro, owner_id,
    listar_lotes_usuario, listar_medicamentos_usuario,
    sel_lote, sel_animal, limpar_cache,
    requer_admin, requer_nao_vet, owner_id_lote_novo,
    _listar_lotes_cache, _listar_animais_cache,
)
import pandas as pd
from datetime import date, datetime, timedelta

# database importado via from database import * abaixo
try:
    from database import *
except Exception as _e_db_any:
    import logging as _log_db_imp, traceback as _tb_imp
    _log_db_imp.getLogger("auroque.app").error(
        "Erro no import de database: %s | %s",
        type(_e_db_any).__name__, _e_db_any
    )
    _log_db_imp.getLogger("auroque.app").error(
        "Traceback: %s", _tb_imp.format_exc()
    )

# Importar pages APOS database estar disponivel
from _pages.cadastros  import (page_cadastrar_lote, page_cadastrar_animal,
    page_registrar_pesagem, page_registrar_ocorrencia, page_registrar_morte,
    page_importar_csv, page_editar_lote, page_editar_animal,
    page_editar_pesagens, page_gerenciar_ocorrencias,
    page_transferir_animal, page_status_do_lote)
from _pages.analise    import (page_dashboard_sanitario, page_analisar_por_lote,
    page_analisar_animal, page_score_de_saude, page_gmd_temporal,
    page_comparativo_lotes, page_pesquisar_ocorrencias,
    page_risco_sanitario_ia, page_previsao_de_abate_ia,
    page_anomalias_de_peso, page_previsao_abate)
from _pages.gestao     import (page_calendario_sanitario, page_estoque_medicamentos,
    page_controle_reprodutivo, page_mapa_piquetes,
    page_workspace_do_lote, page_prontuario_animal,
    page_vender_lote, page_historico_lotes)
from _pages.financeiro import (page_painel_de_decisao, page_dashboard_executivo,
    page_margem_real, page_cotacao_cepea, page_rastreabilidade_gta)
from _pages.relatorios import (page_exportar_relatorios, page_backup)

from _pages.veterinario import (
    page_meu_crmv, page_receituario, page_protocolos,
    page_diagnostico_ia, page_relatorio_visita, page_agenda_visitas,
    page_painel_saude, page_controle_carencia,
    page_exames_laboratoriais, page_monitoramento,
    page_gestao_financeira_vet,
    page_mapa_epidemiologico, page_inbox,
    page_campanhas_vacinacao, page_historico_clinico_pdf,
    page_dashboard_produtividade,
)
from _pages.sistema    import (page_inicio, page_buscar_animal, page_notificacoes,
    page_log_auditoria, page_administracao, page_gestao_usuarios,
    page_configurar_whatsapp, page_exportar_dados)
from _pages.crescimento import (page_importar_csv, page_onboarding,
    page_planos, page_notificacoes_email, page_dados_exemplo)
try:
    from _pages.crescimento import page_ferramentas_publicas
except ImportError:
    def page_ferramentas_publicas(u=None):
        st.info("Ferramentas em manutenção. Tente novamente em instantes.")
from _pages.dashboard_exec import page_dashboard_executivo
from _pages.admin_painel   import page_painel_admin

try:
    from exports import gerar_excel_lote, gerar_excel_sanitario, gerar_pdf_relatorio
    _EXP = True
except ImportError:
    _EXP = False
    def gerar_excel_lote(*a, **k): return b""
    def gerar_excel_sanitario(*a, **k): return b""
    def gerar_pdf_relatorio(*a, **k): return b""

try:
    from notifications import (
        email_boas_vindas, email_trial_expirando, email_trial_expirado,
        email_vacina_pendente, email_medicamento_critico,
        email_parto_previsto, email_abate_previsto, email_configurado,
    )
    _NOTIF = True
except ImportError:
    _NOTIF = False
    def email_boas_vindas(*a, **k): return (False, "")
    def email_trial_expirando(*a, **k): return (False, "")
    def email_trial_expirado(*a, **k): return (False, "")
    def email_vacina_pendente(*a, **k): return (False, "")
    def email_medicamento_critico(*a, **k): return (False, "")
    def email_parto_previsto(*a, **k): return (False, "")
    def email_abate_previsto(*a, **k): return (False, "")
    def email_configurado(): return False

try:
    from cepea import cotacao_com_cache, historico_grafico
    _CEPEA = True
except ImportError:
    _CEPEA = False
    def cotacao_com_cache(_db): return dict(preco=0.0, data="", fonte="", sucesso=False, msg="cepea.py nao encontrado")
    def historico_grafico(c): return dict(datas=[], precos=[])

try:
    from backup import gerar_backup_zip, gerar_backup_sqlite, nome_arquivo_backup
    _BACKUP = True
except ImportError:
    _BACKUP = False
    def gerar_backup_zip(p): return b""
    def gerar_backup_sqlite(p): return b""
    def nome_arquivo_backup(ext="zip"): return f"backup.{ext}"

st.set_page_config(
    page_title="Auroque",
    page_icon="🐂",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Meta tags PWA ─────────────────────────────────────────────
st.markdown("""
<head>
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Auroque">
<meta name="theme-color" content="#1B4332">
<meta name="description" content="Gestão Pecuária Inteligente">
<link rel="manifest" href="data:application/json,{
  &quot;name&quot;:&quot;Auroque&quot;,
  &quot;short_name&quot;:&quot;Auroque&quot;,
  &quot;display&quot;:&quot;standalone&quot;,
  &quot;background_color&quot;:&quot;#1B4332&quot;,
  &quot;theme_color&quot;:&quot;#1B4332&quot;,
  &quot;start_url&quot;:&quot;/&quot;,
  &quot;lang&quot;:&quot;pt-BR&quot;
}">
<style>
/* Melhorar touch em mobile */
button, input, select, textarea {
    -webkit-tap-highlight-color: rgba(64,145,108,0.2);
    touch-action: manipulation;
}
/* Evitar zoom em inputs no iOS */
input[type="text"], input[type="email"],
input[type="password"], input[type="number"] {
    font-size: 16px !important;
}
</style>
</head>
""", unsafe_allow_html=True)

# ── Auroque Visual ─────────────────────────────────────────────────────────────
st.markdown("""<style>
/* Fonte Inter */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

/* Botao primario verde Auroque */
.stButton > button[kind="primary"] {
    background: #1A3C2E !important;
    color: #fff !important;
    border: none !important;
    font-weight: 600 !important;
    border-radius: 6px !important;
}
.stButton > button[kind="primary"]:hover { background: #2E5C46 !important; }

/* Botao secundario */
.stButton > button[kind="secondary"] {
    border: 1.5px solid #1A3C2E !important;
    color: #1A3C2E !important;
    font-weight: 500 !important;
    border-radius: 6px !important;
}

/* Tabs - linha ativa verde neon */
.stTabs [data-baseweb="tab-list"] { border-bottom: 2px solid #E8E8E8 !important; }
.stTabs [data-baseweb="tab"] {
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 8px 16px !important;
}
.stTabs [aria-selected="true"] {
    color: #1A3C2E !important;
    font-weight: 700 !important;
    border-bottom: 3px solid #4ADE80 !important;
}

/* Metricas com borda esquerda verde */
[data-testid="metric-container"] {
    border-left: 3px solid #1A3C2E !important;
    border-radius: 0 8px 8px 0 !important;
    padding-left: 12px !important;
    background: #fff !important;
}

/* Scrollbar fina e visivel */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #F0F0F0; border-radius: 3px; }
::-webkit-scrollbar-thumb { background: #1A3C2E; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #2E5C46; }

/* Focus em inputs verde */
input:focus, textarea:focus, select:focus {
    border-color: #4ADE80 !important;
    box-shadow: 0 0 0 2px rgba(74,222,128,0.2) !important;
}
</style>""", unsafe_allow_html=True)



# Inicializar banco (detecta automaticamente se ja existe - 1 query)
if "banco_ok" not in st.session_state:
    try:
        inicializar_banco()
        import database as _db_diag
        st.session_state.banco_ok    = True
        st.session_state.usando_pg   = _db_diag._usar_postgres()
        st.session_state.banco_erro  = None
    except Exception as _e_init:
        # Não parar o app - mostrar aviso e tentar continuar
        _msg_erro = str(_e_init)
        st.session_state.banco_ok    = False
        st.session_state.banco_erro  = _msg_erro
        st.session_state.usando_pg   = False
        # Logar mas não crashar
        import logging as _log_init
        _log_init.getLogger("auroque.app").error(
            "Falha init banco: %s", _msg_erro
        )

# Exibir aviso de banco indisponível sem parar o app
if not st.session_state.get("banco_ok", True):
    _erro_banco = st.session_state.get("banco_erro", "")
    if "max clients" in _erro_banco or "pool" in _erro_banco.lower():
        st.warning(
            "⚠️ O banco de dados está com muitas conexões simultâneas. "
            "Aguarde alguns segundos e recarregue a página."
        )
    else:
        st.warning(
            f"⚠️ Banco de dados temporariamente indisponível. "
            "Tente recarregar a página em instantes."
        )
    # Limpar o estado para tentar reconectar no próximo rerun
    if st.button("🔄 Tentar reconectar", key="_btn_reconectar"):
        st.session_state.pop("banco_ok", None)
        st.session_state.pop("banco_erro", None)
        st.rerun()
    st.stop()

if not st.session_state.get("usando_pg", False):
    st.sidebar.error("SQLite local - dados nao persistem!")

# ── helper ──────────────────────────────────────────────────────────────────
# ── Helpers de formatacao globais ────────────────────────────────────────────
_MESES_PT = {1:"Jan",2:"Fev",3:"Mar",4:"Abr",5:"Mai",6:"Jun",
             7:"Jul",8:"Ago",9:"Set",10:"Out",11:"Nov",12:"Dez"}

def fmt_data(d):
    """Formata date/string para 'DD Mmm AAAA'. Ex: 15 Jan 2025"""
    if not d: return "-"
    try:
        from datetime import date as _dt, datetime as _dtm
        if isinstance(d, str):
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
                try: d = _dtm.strptime(d, fmt).date(); break
                except: pass
        if hasattr(d, 'day'):
            return f"{d.day:02d} {_MESES_PT[d.month]} {d.year}"
    except: pass
    return str(d)

def fmt_brl(v):
    """Formata valor para padrao brasileiro. Ex: R$ 1.250,00"""
    try:
        v = float(v)
        inteiro, decimal = f"{v:,.2f}".split(".")
        inteiro = inteiro.replace(",", ".")
        return f"R$ {inteiro},{decimal}"
    except:
        return "R$ 0,00"

def fmt_peso(v, casas=2):
    """Formata peso com casas decimais. Ex: 325,50 kg"""
    try:
        return f"{float(v):.{casas}f} kg".replace(".", ",")
    except:
        return "-"

def hdr(icone, titulo, sub=""):
    st.markdown(f"## {icone} {titulo}")
    if sub: st.caption(sub)
    st.divider()

# ── autenticacao ─────────────────────────────────────────────────────────────
if "usuario" not in st.session_state:
    st.session_state.usuario = None

# Ler query param de menu na URL
_qp_menu = st.query_params.get("menu", "")
if _qp_menu and not st.session_state.get("menu"):
    st.session_state["menu"] = _qp_menu
    st.query_params.clear()

# Página pública de ferramentas — sem login
# Acessível via ?menu=Ferramentas ou pelo botão na tela de login
if st.session_state.get("menu") == "Ferramentas" and st.session_state.usuario is None:
    page_ferramentas_publicas()
    st.stop()

if st.session_state.usuario is None:
    # ── CSS: sem scroll, tudo visível numa tela ──────────────────────
    st.markdown("""
<style>
[data-testid="stAppViewContainer"]>.main{
  background:linear-gradient(135deg,#f0f4f0 0%,#e8f5ee 100%);
  padding-top:0!important;
}
[data-testid="stSidebar"]{display:none!important}
[data-testid="collapsedControl"]{display:none!important}
[data-testid="stMain"]>.block-container{
  padding:1rem 1rem 0.5rem!important;
  max-width:900px;
}
/* Inputs compactos */
div[data-testid="stTextInput"] input{padding:6px 10px!important;font-size:14px!important}
div[data-testid="stTextInput"] label{font-size:13px!important}
div[data-testid="stForm"]{border:none!important;padding:0!important}
div[data-testid="stTabs"] button{font-size:13px!important;padding:6px 12px!important}
/* Botão compacto */
div[data-testid="stFormSubmitButton"] button{padding:8px!important;font-size:14px!important}
</style>
""", unsafe_allow_html=True)

    # ── Cabeçalho compacto ────────────────────────────────────────────
    st.markdown("""
<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">
  <svg width="28" height="28" viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg">
    <polygon points="22,3 39,13 39,31 22,41 5,31 5,13"
             fill="none" stroke="#1B4332" stroke-width="2.5"/>
    <text x="22" y="30" font-family="system-ui" font-size="20"
          font-weight="300" fill="#1B4332" text-anchor="middle">A</text>
    <line x1="13" y1="34" x2="31" y2="34" stroke="#40916C" stroke-width="2"/>
  </svg>
  <div style="display:flex;align-items:baseline;gap:8px">
    <span style="font-family:Georgia,serif;font-size:20px;font-weight:700;color:#1B4332">
      Auroque</span>
    <span style="font-size:9px;color:#40916C;letter-spacing:3px">GESTÃO PECUÁRIA</span>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Duas colunas: info | formulário ──────────────────────────────
    _col_esq, _col_dir = st.columns([1, 1], gap="large")

    with _col_esq:
        st.markdown("""
<div style="padding:0 4px">
  <h2 style="font-family:Georgia,serif;font-size:19px;font-weight:700;
       color:#1B4332;line-height:1.25;margin:0 0 8px">
    Gerencie seu rebanho com inteligência
  </h2>
  <p style="font-size:12px;color:#4B5563;margin:0 0 10px;line-height:1.4">
    Animais, pesagens, saúde e finanças em um só lugar.
  </p>
  <div style="display:flex;flex-direction:column;gap:5px;margin-bottom:12px">
    <div style="font-size:12px;color:#374151">
      <span style="color:#40916C;font-weight:700">✓</span> Lotes e GMD automático</div>
    <div style="font-size:12px;color:#374151">
      <span style="color:#40916C;font-weight:700">✓</span> Receituários e carência</div>
    <div style="font-size:12px;color:#374151">
      <span style="color:#40916C;font-weight:700">✓</span> DRE e projeção de abate</div>
    <div style="font-size:12px;color:#374151">
      <span style="color:#40916C;font-weight:700">✓</span> IA para risco sanitário</div>
    <div style="font-size:12px;color:#374151">
      <span style="color:#40916C;font-weight:700">✓</span> Pesagem por voz 🎤</div>
  </div>
  <div style="background:#1B4332;border-radius:8px;padding:8px 12px;margin-bottom:10px">
    <div style="font-size:12px;color:#40916C;font-weight:600">🚀 14 dias grátis</div>
    <div style="font-size:11px;color:rgba(245,240,232,.7)">
      Sem cartão · Cancele quando quiser</div>
  </div>
  <div style="font-size:10px;color:#9CA3AF">contato@auroque.com.br</div>
</div>
""", unsafe_allow_html=True)
        if st.button("🧮 Calculadoras gratuitas", use_container_width=True,
                     key="btn_ferramentas_pub",
                     help="GMD · Previsão de abate · Custo/@ · Pastagem"):
            st.session_state["menu"] = "Ferramentas"
            st.rerun()

    with _col_dir:
        _tab_login, _tab_reg = st.tabs(["🔑 Entrar", "🚀 Criar conta"])

        # ── ABA LOGIN ─────────────────────────────────────────────────
        with _tab_login:
            if not usuario_existe():
                st.info("Primeiro acesso: crie a conta de administrador.")
                with st.form("form_first"):
                    nome  = st.text_input("Nome")
                    email = st.text_input("E-mail")
                    senha = st.text_input("Senha", type="password")
                    perf  = st.selectbox("Perfil", ["admin","veterinario","fazendeiro"])
                    if st.form_submit_button("Criar conta", type="primary",
                                             use_container_width=True):
                        if nome and email and senha:
                            uid = criar_usuario(nome, email, senha, perf)
                            ativar_trial(uid)
                            email_boas_vindas(email, nome)
                            st.success("Conta criada! Faça login.")
                            st.rerun()
                        else:
                            st.error("Preencha todos os campos.")
            else:
                with st.form("form_login"):
                    email = st.text_input("E-mail", placeholder="seu@email.com")
                    senha = st.text_input("Senha", type="password",
                                          placeholder="••••••••")
                    submit = st.form_submit_button("Entrar →", type="primary",
                                                   use_container_width=True)
                    if submit:
                        email_norm = (email or "").strip().lower()
                        _bloq, _n_tent, _seg_rest = verificar_bloqueio_login(email_norm)
                        if _bloq:
                            _min_rest = max(1, _seg_rest // 60 + 1)
                            st.error(f"Conta bloqueada. Aguarde {_min_rest} min.")
                        else:
                            try:
                                u = autenticar_usuario(email, senha)
                            except Exception as _e_auth:
                                st.error("Erro temporário ao autenticar. Tente novamente.")
                                u = None
                            if u:
                                try:
                                    _lim_login = obter_limites_usuario(u["id"])
                                    _status_login = (_lim_login or {}).get(
                                        "status_conta", "ativo")
                                except Exception:
                                    _status_login = "ativo"
                                if _status_login == "suspenso":
                                    st.error("Conta suspensa. Fale com o suporte.")
                                elif _status_login == "pendente":
                                    st.warning("Conta aguardando aprovação.")
                                else:
                                    limpar_tentativas_login(email_norm)
                                    st.session_state.menu          = "Inicio"
                                    st.session_state.wizard_passo  = 1
                                    st.session_state.wizard_pulado = False
                                    st.session_state.onboarding_ok = None
                                    if u.get("perfil") == "admin":
                                        u["owner_id"] = None
                                    elif not u.get("owner_id"):
                                        u["owner_id"] = u["id"]
                                    st.session_state.usuario = u
                                    # Verificar primeiro login e criar dados demo
                                    try:
                                        from database import (
                                            is_primeiro_login,
                                            criar_dados_demo
                                        )
                                        _uid_login = u.get("owner_id") or u["id"]
                                        if is_primeiro_login(_uid_login):
                                            st.session_state["_primeiro_login"] = True
                                            criar_dados_demo(_uid_login)
                                        else:
                                            st.session_state["_primeiro_login"] = False
                                    except Exception:
                                        st.session_state["_primeiro_login"] = False
                                    st.rerun()
                            else:
                                registrar_tentativa_login(email_norm)
                                _bloq2, _n2, _ = verificar_bloqueio_login(email_norm)
                                restantes = max(0, 5 - _n2)
                                if _bloq2:
                                    st.error("Muitas tentativas. Bloqueado por 10 min.")
                                else:
                                    st.error(f"E-mail ou senha incorretos. "
                                             f"Tentativas restantes: {restantes}")

        # ── ABA CADASTRO ──────────────────────────────────────────────
        with _tab_reg:
            with st.form("form_registro"):
                _r_nome  = st.text_input("Nome", placeholder="João Silva")
                _r_email = st.text_input("E-mail", placeholder="seu@email.com")
                _r_perfil = st.radio("Você é:", ["🐄 Fazendeiro", "🩺 Veterinário"],
                                     horizontal=True, key="_reg_perfil")
                _r_senha = st.text_input("Senha (mín. 6 caracteres)",
                                          type="password")
                _r_conf  = st.text_input("Confirmar senha", type="password")
                _r_termos = st.checkbox("Concordo com os termos de uso")
                _r_submit = st.form_submit_button(
                    "🚀 Criar conta — 14 dias grátis",
                    type="primary", use_container_width=True
                )
                if _r_submit:
                    if not _r_termos:
                        st.error("Aceite os termos para continuar.")
                    elif _r_senha != _r_conf:
                        st.error("As senhas não coincidem.")
                    elif len(_r_senha) < 6:
                        st.error("Senha: mínimo 6 caracteres.")
                    else:
                        try:
                            from database import auto_registrar_usuario
                            _perfil_reg = ("veterinario"
                                           if "Veterinário" in _r_perfil
                                           else "fazendeiro")
                            _ok, _msg, _uid = auto_registrar_usuario(
                                _r_nome, _r_email, _r_senha,
                                perfil=_perfil_reg
                            )
                            if _ok:
                                st.success(f"✅ {_msg}")
                                st.info("Agora clique na aba **Entrar**.")
                                try:
                                    email_boas_vindas(_r_email, _r_nome)
                                except Exception:
                                    pass
                            else:
                                st.error(f"❌ {_msg}")
                        except Exception as _er:
                            st.error(f"Erro: {_er}")

    st.stop()

u = st.session_state.usuario

# ── WIZARD DE ONBOARDING ──────────────────────────────────────────────────────
if u and not is_admin():
    # Cache: consultar banco apenas uma vez por sessao de login
    if st.session_state.get("onboarding_ok") is None:
        try:
            _val = onboarding_concluido(u["id"])
            st.session_state.onboarding_ok = bool(_val)
        except Exception:
            # Erro na query = coluna pode nao existir, nao bloquear usuario
            st.session_state.onboarding_ok = True

    _onb_ok = st.session_state.get("onboarding_ok", True)

    if not _onb_ok and not st.session_state.get("wizard_pulado", False):
        # Determinar passo atual
        passo = st.session_state.get("wizard_passo") or 1
        passo = int(passo)

        # ── Container do wizard ──────────────────────────────────────────
        st.markdown(f"""
<div style="background:linear-gradient(135deg,#1A3C2E 0%,#2E5C46 100%);
     border-radius:12px;padding:24px;margin-bottom:24px;color:#fff">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
    <div style="display:flex;align-items:center;gap:12px">
      <svg width="36" height="36" viewBox="0 0 48 48" fill="none">
        <polygon points="24,3 41,12.5 41,31.5 24,41 7,31.5 7,12.5" fill="#4ADE80"/>
        <rect x="16" y="13" width="4" height="22" rx="1.5" fill="#1A3C2E"/>
        <path d="M20 13 L27 13 C30.5 13 33 15.5 33 19 C33 22.5 30.5 25 27 25 L20 25"
              stroke="#1A3C2E" stroke-width="3.5" fill="none" stroke-linecap="round"/>
        <path d="M20 25 L28 25 C31.5 25 34 27.5 34 31 C34 34.5 31.5 37 28 37 L20 37"
              stroke="#1A3C2E" stroke-width="3.5" fill="none" stroke-linecap="round"/>
      </svg>
      <div>
        <div style="font-size:20px;font-weight:700">Bem-vindo ao Auroque!</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.6);letter-spacing:1.5px">
          Passo {passo} de 4
        </div>
      </div>
    </div>
    <div style="background:rgba(74,222,128,0.2);padding:4px 12px;border-radius:20px;
         font-size:11px;font-weight:600;color:#4ADE80">
      {int(passo/4*100)}% completo
    </div>
  </div>
  <div style="height:6px;background:rgba(255,255,255,0.1);border-radius:3px;overflow:hidden">
    <div style="width:{int(passo/4*100)}%;height:100%;background:#4ADE80"></div>
  </div>
</div>
""", unsafe_allow_html=True)

        # ── PASSO 1: Boas vindas ───────────────────────────────────────────
        if passo == 1:
            st.markdown(f"### Ola, {u['nome']}!")
            st.write("")
            st.write("Vamos configurar o Auroque em 4 passos rapidos.")
            st.write("")
            st.markdown("""
**O que vamos fazer:**

1. ✓ Conhecer o Auroque (este passo)
2. Cadastrar seu primeiro lote de animais
3. Decidir se quer ver dados de exemplo
4. Pronto para usar!
""")
            st.info("Voce pode pular este tutorial e configurar tudo depois. O wizard ficara disponivel em **Sistema → Refazer Tutorial**.")
            c1, c2, c3 = st.columns([1, 1, 2])
            with c1:
                if st.button("Pular tutorial", key="wiz_skip"):
                    st.session_state.wizard_pulado = True
                    marcar_onboarding_completo(u["id"])
                    st.rerun()
            with c3:
                if st.button("Comecar →", type="primary", key="wiz_p1_next", use_container_width=True):
                    st.session_state.wizard_passo = 2
                    st.rerun()
            st.stop()

        # ── PASSO 2: Primeiro lote ────────────────────────────────────────
        elif passo == 2:
            st.markdown("### Cadastre seu primeiro lote")
            st.write("Um lote e um grupo de animais que voce gerencia juntos (ex: 'Pasto 1', 'Confinamento A').")
            st.write("")

            from datetime import date as _d
            with st.form("wiz_form_lote"):
                col1, col2 = st.columns(2)
                with col1:
                    w_nome = st.text_input("Nome do lote *", value="Pasto 1",
                                          help="Ex: Pasto 1, Confinamento A, Lote Maio")
                    w_data = st.date_input("Data de inicio", value=_d.today())
                with col2:
                    w_qtd  = st.number_input("Quantidade de animais", 1, 10000, 10)
                    w_tipo = st.selectbox("Tipo", ["Engorda","Cria","Recria","Reproducao"])

                w_desc = st.text_area("Descricao (opcional)", placeholder="Ex: Bois nelore para engorda")

                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    voltar = st.form_submit_button("← Voltar")
                with col_b2:
                    avancar = st.form_submit_button("Cadastrar e avancar →", type="primary")

                if voltar:
                    st.session_state.wizard_passo = 1
                    st.rerun()
                if avancar:
                    if not w_nome:
                        st.error("Informe o nome do lote.")
                    else:
                        try:
                            _oid_lote = u.get("owner_id") or u["id"]
                            lote_id = adicionar_lote(
                                w_nome, w_desc or "", str(w_data),
                                int(w_qtd), int(w_qtd), w_tipo,
                                owner_id=_oid_lote
                            )
                            st.session_state.wizard_lote_id = lote_id
                            st.session_state.wizard_passo = 3
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao criar lote: {e}")
            st.stop()

        # ── PASSO 3: Dados de exemplo (opcional) ─────────────────────────
        elif passo == 3:
            st.markdown("### Quer ver dados de exemplo?")
            st.write("Podemos criar uma fazenda fictícia com 1 lote e 5 animais para voce explorar o sistema antes de cadastrar seus dados reais.")
            st.write("")
            st.info("**Vantagem:** voce ja ve graficos, IA, scores e relatorios funcionando. Pode excluir os dados de exemplo a qualquer momento.")
            st.write("")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Nao, vou cadastrar meus dados →", key="wiz_no_demo"):
                    st.session_state.wizard_passo = 4
                    st.rerun()
            with col2:
                if st.button("Sim, criar dados de exemplo", type="primary",
                            key="wiz_yes_demo", use_container_width=True):
                    with st.spinner("Criando fazenda de exemplo..."):
                        try:
                            r = criar_dados_exemplo(u["id"])
                            if r["ja_existe"]:
                                st.warning(r["msg"])
                            else:
                                st.success(r["msg"])
                        except Exception as e:
                            st.error(f"Erro: {e}")
                    st.session_state.wizard_passo = 4
                    st.rerun()

            st.write("")
            if st.button("← Voltar", key="wiz_p3_back"):
                st.session_state.wizard_passo = 2
                st.rerun()
            st.stop()

        # ── PASSO 4: Pronto ────────────────────────────────────────────────
        elif passo == 4:
            st.markdown("### Tudo certo!")
            st.write("Seu Auroque esta configurado e pronto para usar.")
            st.write("")
            st.success("**Proximos passos sugeridos:**")
            st.markdown("""
- **Cadastrar Animal** → registre os animais do seu lote
- **Registrar Pesagem** → comece a acompanhar o ganho de peso
- **Workspace do Lote** → veja a visao completa do seu lote
- **Dashboard Executivo** → KPIs consolidados da sua fazenda
- **Analise & IA** → previsao de abate e risco sanitario
""")
            st.write("")
            st.info("Voce pode refazer este tutorial em **Sistema → Refazer Tutorial**.")
            st.write("")

            if st.button("Ir para o Dashboard →", type="primary",
                        key="wiz_finish", use_container_width=True):
                marcar_onboarding_completo(u["id"])
                st.session_state.wizard_pulado = True
                st.session_state.menu = "Inicio"
                st.rerun()
            st.stop()


# ── CSS da sidebar - injetado antes de renderizar ────────────────────────────
try:
    from ux_helpers import _CSS_AUROQUE as _CSS_SB
    st.markdown(_CSS_SB, unsafe_allow_html=True)
except Exception:
    st.markdown("""<style>
[data-testid="stSidebar"]{background-color:#1B4332 !important;}
[data-testid="stSidebar"]>div:first-child{background-color:#1B4332 !important;}
[data-testid="stSidebar"] button{background-color:#1B4332 !important;
  color:#F5F0E8 !important;border:1px solid rgba(245,240,232,0.2) !important;}
[data-testid="stSidebar"] button:hover{background-color:#40916C !important;}
[data-testid="stSidebar"] span:not([data-testid]),
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label{color:#F5F0E8 !important;}
</style>""", unsafe_allow_html=True)

# ── sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:

    # ── 1. LOGO + FAZENDA + PERFIL (TOPO) ────────────────────────────
    _sb_nome_raw = u.get("nome", "")
    _sb_fazenda  = ""
    if " - " in _sb_nome_raw:
        _sb_fazenda = _sb_nome_raw.split(" - ")[-1].strip()
        _sb_fazenda = _sb_fazenda.split(" - Nome:")[0].strip()
        if _sb_fazenda.lower().startswith("fazenda "):
            _sb_fazenda = _sb_fazenda[8:].strip()
    elif " - Fazenda" in _sb_nome_raw:
        _sb_fazenda = _sb_nome_raw.split(" - Fazenda")[-1].strip()
    elif " - Nome:" in _sb_nome_raw:
        _sb_fazenda = _sb_nome_raw.split(" - Nome:")[0].strip()
        _sb_fazenda = _sb_fazenda.split(" - ")[-1].strip()
    _sb_perfil = u.get("perfil", "fazendeiro").capitalize()
    _sb_plano  = (u.get("plano") or "free").upper()
    _plano_cor = {
        "FREE": "#6B7280", "PRO": "#40916C",
        "VET": "#2563EB", "ENTERPRISE": "#7C3AED"
    }.get(_sb_plano, "#6B7280")

    st.markdown(f"""
<div style="padding:14px 4px 10px">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
    <svg width="36" height="36" viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg">
      <polygon points="22,3 39,13 39,31 22,41 5,31 5,13"
               fill="none" stroke="#F5F0E8" stroke-width="2"/>
      <text x="22" y="30" font-family="system-ui,sans-serif"
            font-size="20" font-weight="300" fill="#F5F0E8"
            text-anchor="middle">A</text>
      <line x1="13" y1="34" x2="31" y2="34"
            stroke="#40916C" stroke-width="1.8"/>
    </svg>
    <div>
      <div style="font-family:Georgia,serif;font-size:20px;font-weight:700;
           color:#F5F0E8;letter-spacing:1px;line-height:1">Auroque</div>
      <div style="font-size:7px;color:#40916C;letter-spacing:3px;
           margin-top:2px">GESTÃO PECUÁRIA</div>
    </div>
  </div>
  <div style="background:rgba(64,145,108,.15);border-radius:8px;
       padding:8px 10px;margin-bottom:6px">
    <div style="font-size:13px;font-weight:600;color:#F5F0E8;
         white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
      🏡 {_sb_fazenda or 'Minha Fazenda'}</div>
    <div style="display:flex;align-items:center;gap:6px;margin-top:4px">
      <span style="font-size:11px;color:rgba(245,240,232,.6)">{_sb_perfil}</span>
      <span style="background:{_plano_cor};color:white;font-size:9px;
            font-weight:700;padding:1px 6px;border-radius:4px;
            letter-spacing:.5px">{_sb_plano}</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── 2. BOTÃO SAIR ─────────────────────────────────────────────────
    if st.button("Sair", key="_btn_sair", use_container_width=True):
        st.session_state.usuario       = None
        st.session_state.onboarding_ok = None
        st.session_state.wizard_pulado = False
        st.session_state.wizard_passo  = 1
        st.rerun()

    st.markdown(
        "<div style='height:1px;background:rgba(245,240,232,.15);"
        "margin:6px 0 8px'></div>",
        unsafe_allow_html=True
    )

    # ── 3. ATALHOS RÁPIDOS ────────────────────────────────────────────
    if not is_admin():
        st.markdown(
            "<div style='font-size:10px;color:rgba(245,240,232,.45);"
            "letter-spacing:1px;text-transform:uppercase;"
            "margin:0 0 5px;padding:0 2px'>Acesso rápido</div>",
            unsafe_allow_html=True
        )
        _atalhos = [
            ("📋 Prontuário",         "Prontuario Animal"),
            ("💊 Receituário",        "Receituario"),
            ("📅 Agenda",             "Agenda Visitas"),
            ("⏱️ Carências",          "Controle Carencia"),
            ("💰 Financeiro",         "Financeiro Vet"),
        ] if is_vet() else [
            ("⚖️ Pesagem",            "Workspace do Lote"),
            ("🐄 Cadastrar animal",   "Cadastrar Animal"),
            ("💰 Financeiro",         "Dashboard Financeiro"),
            ("📋 Prontuário",         "Prontuario Animal"),
            ("📥 Exportar dados",     "Exportar Relatorios"),
        ]
        for _label, _destino in _atalhos:
            if st.button(_label, key=f"_atl_{_destino}",
                         use_container_width=True):
                st.session_state.menu = _destino
                st.rerun()
        st.markdown(
            "<div style='height:1px;background:rgba(245,240,232,.15);"
            "margin:8px 0'></div>",
            unsafe_allow_html=True
        )

    # ── 4. PLANO / TRIAL (discreto, sem erro vermelho) ────────────────
    @st.cache_data(ttl=300, show_spinner=False)
    def _plano_usuario(uid):
        return obter_status_plano(uid)
    _sp = _plano_usuario(u["id"])
    if _sp and _sp.get("plano") == "trial":
        _dr = _sp.get("dias_restantes", 0)
        if _dr <= 3:
            st.warning(f"⚠️ Trial: {_dr} dia(s) restante(s)")
        elif _dr <= 7:
            st.caption(f"Trial: {_dr} dias restantes")

    st.markdown(
        "<div style='font-size:10px;color:rgba(245,240,232,.4);"
        "letter-spacing:1px;text-transform:uppercase;"
        "padding:2px 0 4px'>Menu</div>",
        unsafe_allow_html=True
    )

    # ── Busca global ─────────────────────────────────────────
    with st.sidebar:
        _busca = st.text_input(
            "Buscar",
            placeholder="🔍  animal ou lote...",
            key="_busca_global",
            label_visibility="collapsed",
        )
        if _busca and len(_busca.strip()) >= 2:
            try:
                from database import buscar_animal_global
                _resultados = buscar_animal_global(
                    _busca.strip(), owner_id()
                )
                if _resultados:
                    for _r in _resultados[:5]:
                        _lbl = (f"🐄 {_r.get('identificacao','')} "
                                f"- {_r.get('lote_nome','')}")
                        if st.button(_lbl,
                                     key=f"_br_{_r.get('id')}",
                                     use_container_width=True):
                            st.session_state["_prontuario_aid"] = _r.get("id")
                            st.session_state.menu = "Prontuario Animal"
                            st.rerun()
                else:
                    st.caption("Sem resultados")
            except Exception:
                pass
        st.markdown(
            "<div style='height:1px;background:rgba(245,240,232,.2);"
            "margin:6px 0 10px'></div>",
            unsafe_allow_html=True
        )

    # ── Definição dos grupos do menu ─────────────────────────────────
    GRUPOS = {
        "Inicio": [
            ("Inicio",               "Painel geral"),
            ("Workspace do Lote",    "Visao completa do lote"),
        ],
    }

    if is_admin():
        GRUPOS["Analise"] = [
            ("Dashboard Executivo",  "KPIs consolidados"),
            ("Dashboard Sanitario",  "Incidencias e alertas"),
            ("Analisar por Lote",    "GMD e desempenho"),
            ("Analisar Animal",      "Analise individual"),
            ("Score de Saude",       "Ranking 0-100"),
            ("GMD Temporal",         "Evolucao no tempo"),
            ("Comparativo Lotes",    "Side by side"),
            ("Pesquisar Ocorrencias","Busca avancada"),
        ]
        GRUPOS["Inteligencia"] = [
            ("Risco Sanitario IA",   "Score de risco do lote"),
            ("Previsao de Abate IA", "Predicao por animal"),
            ("Anomalias de Peso",    "Alertas inteligentes"),
        ]
        GRUPOS["Administracao"] = [
            ("Painel Admin",         "MRR, usuarios e erros"),
            ("Administracao",        "Usuarios e planos"),
            ("Gestao Usuarios",      "Planos e acessos vet"),
            ("Log Auditoria",        "Historico de acoes"),
            ("Diagnostico DB",       "Schema do banco"),
        ]
        GRUPOS["Sistema"] = [
            ("Importar CSV",         "Importar animais e pesagens"),
            ("Exportar Relatorios",  "PDF e Excel"),
            ("Notificacoes",         "E-mail e alertas"),
            ("Mensagens",            "Inbox vet-fazendeiro"),
        ]
    else:
        if is_vet():
            # ── MENU VETERINÁRIO ─────────────────────────────────
            GRUPOS["Inicio"] = [
                ("Meu Dashboard",       "Produtividade e configuracao"),
                ("Inicio",              "Painel das fazendas atendidas"),
                ("Meu CRMV",            "Registro profissional"),
            ]
            GRUPOS["Clinico"] = [
                ("Prontuario Animal",   "Historico completo do animal"),
                ("Receituario",         "Emissao de receitas"),
                ("Diagnostico IA",      "Analise clinica com IA"),
                ("Historico PDF",       "Historico clinico do animal"),
                ("Monitoramento",       "Pos-tratamento e follow-up"),
            ]
            GRUPOS["Preventivo"] = [
                ("Protocolos",          "Protocolos sanitarios"),
                ("Campanhas",           "Vacinacao por safra"),
                ("Controle Carencia",   "Periodo de carencia ao abate"),
                ("Calendario Sanitario","Vacinas e alertas"),
                ("Mapa Epidemio",       "Epidemiologia cruzada"),
            ]
            GRUPOS["Laboratorio"] = [
                ("Exames Lab",          "Exames laboratoriais"),
                ("Painel Saude",        "Estatisticas do rebanho"),
                ("Dashboard Sanitario", "Incidencias e alertas"),
                ("Pesquisar Ocorrencias","Busca avancada"),
            ]
            GRUPOS["Visitas Vet"] = [
                ("Agenda Visitas",      "Visitas tecnicas"),
                ("Relatorio Visita",    "Laudos de visita"),
                ("Financeiro Vet",      "Honorarios e faturamento"),
            ]
            GRUPOS["Analises"] = [
                ("Analisar por Lote",   "GMD e desempenho"),
                ("Analisar Animal",     "Analise individual"),
                ("Score de Saude",      "Ranking 0-100"),
                ("Risco Sanitario IA",  "Score de risco do lote"),
                ("Workspace do Lote",   "Visao completa do lote"),
            ]
            GRUPOS["Sistema"] = [
                ("Mensagens",           "Inbox vet-fazendeiro"),
                ("Exportar Relatorios", "PDF e Excel"),
                ("Planos",              "Meu plano e limites"),
                ("Dados de Exemplo",    "Criar ou remover fazenda demo"),
                ("Onboarding",          "Configuracao inicial guiada"),
            ]

        else:
            # ── MENU FAZENDEIRO ──────────────────────────────────
            GRUPOS["Rebanho"] = [
                ("Cadastrar Lote",       "Novo lote"),
                ("Cadastrar Animal",     "Novo animal"),
                ("Registrar Pesagem",    "Nova pesagem"),
                ("Registrar Ocorrencia", "Nova ocorrencia"),
                ("Buscar Animal",        "Busca por brinco"),
                ("Status do Lote",       "Alterar status"),
                ("Transferir Animal",    "Mover entre lotes"),
                ("Registrar Morte",      "Baixa de animal"),
                ("Editar Lote",          "Alterar lote"),
                ("Editar Animal",        "Alterar animal"),
                ("Editar Pesagens",      "Corrigir pesagens"),
                ("Vender Lote",          "Registrar venda do lote"),
                ("Historico Lotes",      "Lotes vendidos e DRE"),
            ]
            GRUPOS["Gestao Sanitaria"] = [
                ("Prontuario Animal",    "Historico completo"),
                ("Gerenciar Ocorrencias","Tratamentos e ocorrencias"),
                ("Calendario Sanitario", "Vacinas e alertas"),
                ("Estoque Medicamentos", "Controle de estoque"),
                ("Controle Reprodutivo", "IATF e prenhez"),
            ]
            GRUPOS["Analises"] = [
                ("Dashboard Executivo",  "KPIs consolidados"),
                ("Dashboard Sanitario",  "Incidencias e alertas"),
                ("Analisar por Lote",    "GMD e desempenho"),
                ("Analisar Animal",      "Analise individual"),
                ("Comparativo Lotes",    "Side by side"),
                ("Score de Saude",       "Ranking 0-100"),
                ("GMD Temporal",         "Evolucao no tempo"),
                ("Pesquisar Ocorrencias","Busca avancada"),
            ]
            GRUPOS["Inteligencia IA"] = [
                ("Risco Sanitario IA",   "Score de risco do lote"),
                ("Previsao de Abate IA", "Predicao por animal"),
                ("Anomalias de Peso",    "Alertas inteligentes"),
                ("Painel de Decisao",    "Lucro por lote"),
            ]
            GRUPOS["Financeiro"] = [
                ("Dashboard Financeiro", "KPIs, DRE e projecao de abate"),
                ("Previsao Abate",       "Data estimada de abate"),
                ("Margem Real",          "Compra x Venda"),
                ("Rastreabilidade GTA",  "GTA e SISBOV"),
                ("Cotacao Cepea",        "Preco boi gordo"),
                ("Mapa Piquetes",        "Pastagens"),
            ]
            GRUPOS["Sistema"] = [
                ("Importar CSV",         "Importar animais e pesagens"),
                ("Exportar Relatorios",  "PDF e Excel"),
                ("Planos",               "Meu plano e limites"),
                ("WhatsApp",             "Configurar alertas WhatsApp"),
                ("Mensagens",            "Inbox vet-fazendeiro"),
                ("Email Alertas",        "Notificacoes por email"),
                ("Ferramentas",          "Calculadoras e calendarios publicos"),
                ("Dados de Exemplo",     "Criar ou remover fazenda demo"),
                ("Onboarding",           "Configuracao inicial guiada"),
            ]

    if "menu" not in st.session_state:
        st.session_state.menu = "Inicio"

    # Ícones por grupo
    _ICONES = {
        "Inicio":           "🏠",
        "Rebanho":          "🐄",
        "Gestao Sanitaria": "🩺",
        "Analises":         "📊",
        "Inteligencia IA":  "🤖",
        "Inteligencia":     "🤖",
        "Financeiro":       "💰",
        "Sistema":          "⚙️",
        "Clinico":          "💊",
        "Preventivo":       "🛡️",
        "Laboratorio":      "🔬",
        "Visitas Vet":      "📅",
        "Analise":          "📊",
        "Administracao":    "👥",
    }

    for grupo, itens in GRUPOS.items():
        if not itens:
            continue

        # INICIO sem expander - itens diretos
        if grupo == "Inicio":
            st.markdown(
                f"<div style='font-size:9px;color:rgba(255,255,255,0.3);"
                f"letter-spacing:1.5px;text-transform:uppercase;"
                f"padding:6px 8px 2px'>🏠 INICIO</div>",
                unsafe_allow_html=True
            )
            for nome_item, desc in itens:
                ativo = st.session_state.menu == nome_item
                label = f"**{nome_item}**" if ativo else nome_item
                _key_menu = f"menu_{grupo}_{nome_item}".replace(" ","_")
                if st.button(label, key=_key_menu,
                             use_container_width=True, help=desc):
                    st.session_state.menu = nome_item
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            continue

        # Verificar se algum item do grupo está ativo
        grupo_ativo = any(st.session_state.menu == n for n, _ in itens)
        icone = _ICONES.get(grupo, "-")
        label_grupo = f"{icone} {grupo} ({len(itens)})"

        with st.sidebar.expander(label_grupo, expanded=grupo_ativo):
            for nome_item, desc in itens:
                ativo = st.session_state.menu == nome_item
                label = f"**✦ {nome_item}**" if ativo else nome_item
                _key_menu2 = f"menu_{grupo}_{nome_item}".replace(" ","_")
                if st.button(label, key=_key_menu2,
                             use_container_width=True, help=desc):
                    st.session_state.menu = nome_item
                    st.rerun()

menu = st.session_state.menu

# ── ROTEAMENTO ─────────────────────────────────────────────────────────────────
# ── TELAS DE ONBOARDING ───────────────────────────────────────────────────────

def page_refazer_tutorial(u):
    import streamlit as st
    st.title("Refazer Tutorial")
    st.caption("Reabrir o wizard de primeiros passos do Auroque")
    st.divider()
    st.info("Ao clicar em 'Refazer tutorial', voce sera levado de volta ao wizard de onboarding na proxima atualizacao da pagina.")
    st.write("")
    if st.button("Refazer tutorial agora", type="primary", key="btn_refazer"):
        # Resetar flag de onboarding via funcao do database
        from database import _conexao, _ph
        try:
            with _conexao() as conn:
                cur = conn.cursor()
                p = _ph()
                cur.execute(f"UPDATE usuarios SET onboarding_completo=0 WHERE id={p}", (u["id"],))
                conn.commit()
        except Exception:
            pass
        st.session_state.wizard_passo = 1
        st.session_state.wizard_pulado = False
        st.success("Tutorial reaberto! Atualizando...")
        st.rerun()


def page_dados_exemplo(u):
    import streamlit as st
    st.title("Dados de Exemplo")
    st.caption("Criar ou remover fazenda fictícia para testar o sistema")
    st.divider()

    # Verificar se ja tem dados exemplo
    lotes_user = listar_lotes(owner_id=u.get("owner_id") or u["id"])
    tem_demo = any('[DEMO]' in (l[1] or '') for l in lotes_user)

    if tem_demo:
        st.success("Voce tem dados de exemplo cadastrados.")
        st.write("Os dados de exemplo incluem 1 lote chamado **[DEMO] Pasto Vitrine** com 5 animais ficticios e pesagens historicas.")
        st.write("")
        st.warning("Ao remover, todos os animais, pesagens e ocorrencias dos lotes [DEMO] serao excluidos.")
        if st.button("Remover dados de exemplo", type="primary", key="btn_rm_demo"):
            n = remover_dados_exemplo(u["id"])
            st.success(f"{n} lote(s) de exemplo removido(s).")
            limpar_cache()
            st.rerun()
    else:
        st.info("Voce ainda nao tem dados de exemplo.")
        st.write("Podemos criar uma fazenda fictícia com:")
        st.markdown("""
- 1 lote chamado **[DEMO] Pasto Vitrine**
- 5 animais ficticios (DEMO-001 a DEMO-005)
- Pesagens historicas dos ultimos 90 dias
- 1 ocorrencia sanitaria exemplo
""")
        st.write("")
        st.caption("Util para explorar o sistema e ver graficos, IA e relatorios funcionando antes de cadastrar seus dados reais.")
        st.write("")
        if st.button("Criar dados de exemplo", type="primary", key="btn_cr_demo"):
            with st.spinner("Criando fazenda exemplo..."):
                r = criar_dados_exemplo(u["id"])
            if r["ja_existe"]:
                st.warning(r["msg"])
            else:
                st.success(r["msg"])
            limpar_cache()
            st.rerun()


def _page_diagnostico_db(u):
    if not is_admin():
        st.error("Acesso restrito ao admin.")
        st.stop()
    st.title("Diagnostico do Banco")
    st.caption("Tela temporaria para diagnostico do schema real do Supabase")
    from database import _conexao, _usar_postgres
    with _conexao() as conn:
        cur = conn.cursor()
        for tbl in ["animais","lotes","medicamentos","usuarios"]:
            st.subheader(f"Tabela: `{tbl}`")
            try:
                if _usar_postgres():
                    cur.execute(f"SELECT column_name,data_type FROM information_schema.columns WHERE table_name='{tbl}' ORDER BY ordinal_position")
                    cols = cur.fetchall()
                    st.write(" | ".join([f"`{c[0]}` ({c[1]})" for c in cols]))
                else:
                    cur.execute(f"PRAGMA table_info({tbl})")
                    cols = cur.fetchall()
                    st.write(" | ".join([f"`{c[1]}` ({c[2]})" for c in cols]))
            except Exception as e:
                st.error(f"Erro: {e}")
        st.subheader("Amostra: animais")
        try:
            cur.execute("SELECT * FROM animais LIMIT 3")
            rows = cur.fetchall()
            descr = [d[0] for d in cur.description]
            for r in rows:
                st.json(dict(zip(descr, [str(x) for x in r])))
        except Exception as e:
            st.error(str(e))
        st.subheader("Amostra: medicamentos")
        try:
            cur.execute("SELECT * FROM medicamentos LIMIT 3")
            rows = cur.fetchall()
            descr = [d[0] for d in cur.description]
            for r in rows:
                st.json(dict(zip(descr, [str(x) for x in r])))
        except Exception as e:
            st.error(str(e))


_ROTAS = {
    "Inicio":               page_inicio,
    "Buscar Animal":        page_buscar_animal,
    "Cadastrar Lote":       page_cadastrar_lote,
    "Cadastrar Animal":     page_cadastrar_animal,
    "Registrar Pesagem":    page_registrar_pesagem,
    "Registrar Ocorrencia": page_registrar_ocorrencia,
    "Registrar Morte":      page_registrar_morte,
    "Importar CSV":         page_importar_csv,
    "Dashboard Sanitario":  page_dashboard_sanitario,
    "Analisar por Lote":    page_analisar_por_lote,
    "Analisar Animal":      page_analisar_animal,
    "Score de Saude":       page_score_de_saude,
    "GMD Temporal":         page_gmd_temporal,
    "Comparativo Lotes":    page_comparativo_lotes,
    "Painel de Decisao":    page_painel_de_decisao,
    "Dashboard Executivo":  page_dashboard_executivo,
    "Pesquisar Ocorrencias":page_pesquisar_ocorrencias,
    "Calendario Sanitario": page_calendario_sanitario,
    "Estoque Medicamentos": page_estoque_medicamentos,
    "Controle Reprodutivo": page_controle_reprodutivo,
    "Mapa Piquetes":        page_mapa_piquetes,
    "Previsao Abate":       page_previsao_abate,
    "Prontuario Animal":    page_prontuario_animal,
    "Margem Real":          page_margem_real,
    "Cotacao Cepea":        page_cotacao_cepea,
    "Rastreabilidade GTA":  page_rastreabilidade_gta,
    "Exportar Relatorios":  page_exportar_relatorios,
    "Backup":               page_backup,
    "Notificacoes":         page_notificacoes,
    "Log Auditoria":        page_log_auditoria,
    "Administracao":        page_administracao,
    "Editar Lote":          page_editar_lote,
    "Editar Animal":        page_editar_animal,
    "Editar Pesagens":      page_editar_pesagens,
    "Gerenciar Ocorrencias":page_gerenciar_ocorrencias,
    "Transferir Animal":    page_transferir_animal,
    "Status do Lote":       page_status_do_lote,
    "Workspace do Lote":    page_workspace_do_lote,
    "Gestao Usuarios":      page_gestao_usuarios,
    "Risco Sanitario IA":   page_risco_sanitario_ia,
    "Previsao de Abate IA": page_previsao_de_abate_ia,
    "Anomalias de Peso":    page_anomalias_de_peso,
    "Refazer Tutorial":     page_refazer_tutorial,
    "Dados de Exemplo":     page_dados_exemplo,
    "Diagnostico DB":       _page_diagnostico_db,
    # Modulo Veterinario
    "Meu CRMV":             page_meu_crmv,
    "Receituario":          page_receituario,
    "Protocolos":           page_protocolos,
    "Diagnostico IA":       page_diagnostico_ia,
    "Relatorio Visita":     page_relatorio_visita,
    "Agenda Visitas":       page_agenda_visitas,
    "Painel Saude":         page_painel_saude,
    "Controle Carencia":    page_controle_carencia,
    "Exames Lab":           page_exames_laboratoriais,
    "Monitoramento":        page_monitoramento,
    "Financeiro Vet":       page_gestao_financeira_vet,
    "Meu Dashboard":        page_dashboard_produtividade,
    "Mapa Epidemio":        page_mapa_epidemiologico,
    "Mensagens":            page_inbox,
    "Campanhas":            page_campanhas_vacinacao,
    "Historico PDF":        page_historico_clinico_pdf,
    "Importar CSV":         page_importar_csv,
    "Onboarding":           page_onboarding,
    "Planos":               page_planos,
    "Email Alertas":        page_notificacoes_email,
    "Dashboard Financeiro": page_dashboard_executivo,
    "Painel Admin":         page_painel_admin,
    "Ferramentas":          page_ferramentas_publicas,
    "Vender Lote":          page_vender_lote,
    "Historico Lotes":      page_historico_lotes,
    "Dados de Exemplo":     page_dados_exemplo,
    "WhatsApp":             page_configurar_whatsapp,
    "Exportar Relatorios":  page_exportar_dados,
}





page_fn = _ROTAS.get(menu)
if page_fn:
    # ── Modal de boas-vindas — primeiro login ────────────────────────
    if st.session_state.get("_primeiro_login") and not is_admin():
        if is_vet():
            st.markdown("""
<style>
.ob-modal{background:white;border-radius:16px;padding:32px 36px;
  box-shadow:0 8px 40px rgba(0,0,0,.18);max-width:680px;margin:0 auto 24px}
.ob-titulo{font-family:Georgia,serif;font-size:26px;font-weight:700;
  color:#1B4332;margin:0 0 6px}
.ob-sub{font-size:14px;color:#6B7280;margin:0 0 24px}
.ob-steps{display:flex;gap:16px;margin-bottom:24px;flex-wrap:wrap}
.ob-step{flex:1;min-width:160px;background:#F5F9F7;border-radius:10px;
  padding:14px 16px;border:2px solid #D1FAE5}
.ob-step-num{font-size:22px;margin-bottom:6px}
.ob-step-titulo{font-size:13px;font-weight:700;color:#1B4332;margin-bottom:3px}
.ob-step-desc{font-size:11px;color:#6B7280;line-height:1.4}
</style>
<div class="ob-modal">
  <div class="ob-titulo">👋 Bem-vindo ao Auroque Vet!</div>
  <div class="ob-sub">
    Sua conta veterinária está pronta. Siga os passos abaixo para começar.
  </div>
  <div class="ob-steps">
    <div class="ob-step">
      <div class="ob-step-num">1️⃣</div>
      <div class="ob-step-titulo">Cadastre seu CRMV</div>
      <div class="ob-step-desc">
        Vá em Meu CRMV para registrar seu número profissional — necessário para emitir receituários
      </div>
    </div>
    <div class="ob-step">
      <div class="ob-step-num">2️⃣</div>
      <div class="ob-step-titulo">Crie dados de exemplo</div>
      <div class="ob-step-desc">
        Vá em Sistema → Dados de Exemplo para criar uma fazenda demo e explorar o prontuário e carências
      </div>
    </div>
    <div class="ob-step">
      <div class="ob-step-num">3️⃣</div>
      <div class="ob-step-titulo">Solicite acesso a uma fazenda</div>
      <div class="ob-step-desc">
        Peça ao fazendeiro para aprovar seu acesso em Gestão de Usuários — ou explore a demo primeiro
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
            _ob1, _ob2, _ob3 = st.columns([1, 1, 1])
            with _ob1:
                if st.button("🪪 Cadastrar meu CRMV",
                             type="primary", use_container_width=True,
                             key="ob_crmv"):
                    st.session_state["_primeiro_login"] = False
                    st.session_state.menu = "Meu CRMV"
                    st.rerun()
            with _ob2:
                if st.button("🌱 Criar dados de exemplo",
                             use_container_width=True, key="ob_demo_vet"):
                    st.session_state["_primeiro_login"] = False
                    st.session_state.menu = "Dados de Exemplo"
                    st.rerun()
            with _ob3:
                if st.button("Explorar sozinho →",
                             use_container_width=True, key="ob_pular_vet"):
                    st.session_state["_primeiro_login"] = False
                    st.rerun()
        else:
            st.markdown("""
<style>
.ob-modal{background:white;border-radius:16px;padding:32px 36px;
  box-shadow:0 8px 40px rgba(0,0,0,.18);max-width:680px;margin:0 auto 24px}
.ob-titulo{font-family:Georgia,serif;font-size:26px;font-weight:700;
  color:#1B4332;margin:0 0 6px}
.ob-sub{font-size:14px;color:#6B7280;margin:0 0 24px}
.ob-steps{display:flex;gap:16px;margin-bottom:24px;flex-wrap:wrap}
.ob-step{flex:1;min-width:160px;background:#F5F9F7;border-radius:10px;
  padding:14px 16px;border:2px solid #D1FAE5}
.ob-step-num{font-size:22px;margin-bottom:6px}
.ob-step-titulo{font-size:13px;font-weight:700;color:#1B4332;margin-bottom:3px}
.ob-step-desc{font-size:11px;color:#6B7280;line-height:1.4}
</style>
<div class="ob-modal">
  <div class="ob-titulo">👋 Bem-vindo ao Auroque!</div>
  <div class="ob-sub">
    Criamos uma fazenda demo com dados reais para você explorar o sistema.
    Siga os 3 passos abaixo para começar — ou explore por conta própria.
  </div>
  <div class="ob-steps">
    <div class="ob-step">
      <div class="ob-step-num">1️⃣</div>
      <div class="ob-step-titulo">Explore o Workspace</div>
      <div class="ob-step-desc">
        Veja os 8 animais demo, pesagens e o gráfico de evolução do lote
      </div>
    </div>
    <div class="ob-step">
      <div class="ob-step-num">2️⃣</div>
      <div class="ob-step-titulo">Registre uma pesagem</div>
      <div class="ob-step-desc">
        Experimente a pesagem por voz falando "01 peso 350"
      </div>
    </div>
    <div class="ob-step">
      <div class="ob-step-num">3️⃣</div>
      <div class="ob-step-titulo">Cadastre seu lote real</div>
      <div class="ob-step-desc">
        Quando quiser, vá em Rebanho → Cadastrar Lote e adicione seus dados
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
            _ob1, _ob2, _ob3 = st.columns([1, 1, 1])
            with _ob1:
                if st.button("🐄 Ver Workspace do Lote",
                             type="primary", use_container_width=True,
                             key="ob_workspace"):
                    st.session_state["_primeiro_login"] = False
                    st.session_state.menu = "Workspace do Lote"
                    st.rerun()
            with _ob2:
                if st.button("📋 Cadastrar meu lote real",
                             use_container_width=True, key="ob_lote"):
                    st.session_state["_primeiro_login"] = False
                    st.session_state.menu = "Cadastrar Lote"
                    st.rerun()
            with _ob3:
                if st.button("Pular → Explorar sozinho",
                             use_container_width=True, key="ob_pular"):
                    st.session_state["_primeiro_login"] = False
                    st.rerun()

        st.stop()

    # Banner onboarding para usuarios novos
    try:
        from database import onboarding_completo as _ob_ok
        _oid_on = u.get("owner_id") or u["id"]
        if not _ob_ok(_oid_on) and menu != "Onboarding":
            from database import obter_progresso_onboarding, _PASSOS_ONBOARDING
            _prog_on = obter_progresso_onboarding(_oid_on)
            _conc_on = sum(1 for v in _prog_on.values() if v)
            _tot_on  = len(_PASSOS_ONBOARDING)
            if _conc_on < _tot_on:
                col_b1, col_b2 = st.columns([3, 1])
            with col_b1:
                st.info(
                    f"Configure o Auroque: {_conc_on}/{_tot_on} passos concluidos."
                )
            with col_b2:
                if st.button("Abrir Onboarding", key="_btn_ob_banner",
                            type="primary"):
                    st.session_state.menu = "Onboarding"
                    st.rerun()
    except Exception:
        pass
    # CSS global Auroque - aplicado em TODA página, toda navegação
    try:
        from ux_helpers import aplicar_css_global as _css_global
        _css_global()
    except Exception:
        pass

    from ux_helpers import pagina_protegida
    pagina_protegida(page_fn)(u)
else:
    st.error(f"Tela '{menu}' nao encontrada.")
