# ui.py – Design system do Sistema de Gestao Pecuaria

# Componentes reutilizaveis: cards, badges, alertas, metricas

try:
import streamlit as st
except ImportError:
st = None

# ── Paleta de cores ──────────────────────────────────────────────────────────

COR = {
‘verde’:     ‘#1F5C2E’,
‘verde_claro’: ‘#2E7D4F’,
‘verde_bg’:  ‘#E8F5E9’,
‘vermelho’:  ‘#B71C1C’,
‘vermelho_bg’: ‘#FFEBEE’,
‘amarelo’:   ‘#E65100’,
‘amarelo_bg’: ‘#FFF3E0’,
‘azul’:      ‘#1565C0’,
‘azul_bg’:   ‘#E3F2FD’,
‘cinza’:     ‘#546E7A’,
‘cinza_bg’:  ‘#ECEFF1’,
‘roxo’:      ‘#4A148C’,
‘roxo_bg’:   ‘#F3E5F5’,
}

# ── Badges de status ─────────────────────────────────────────────────────────

STATUS_ANIMAL_COR = {
‘ATIVO’:       (COR[‘verde’],    COR[‘verde_bg’]),
‘MORTO’:       (COR[‘vermelho’], COR[‘vermelho_bg’]),
‘VENDIDO’:     (COR[‘azul’],     COR[‘azul_bg’]),
‘TRANSFERIDO’: (COR[‘roxo’],     COR[‘roxo_bg’]),
‘DESCARTADO’:  (COR[‘cinza’],    COR[‘cinza_bg’]),
}

STATUS_LOTE_COR = {
‘ATIVO’:      (COR[‘verde’],    COR[‘verde_bg’]),
‘CRITICO’:    (COR[‘vermelho’], COR[‘vermelho_bg’]),
‘QUARENTENA’: (COR[‘amarelo’],  COR[‘amarelo_bg’]),
‘ENCERRADO’:  (COR[‘cinza’],    COR[‘cinza_bg’]),
‘VENDIDO’:    (COR[‘azul’],     COR[‘azul_bg’]),
}

def badge(texto, cor_texto, cor_fundo):
return (
f”<span style='background:{cor_fundo};color:{cor_texto};"
f"padding:2px 10px;border-radius:12px;font-size:12px;"
f"font-weight:600;border:1px solid {cor_texto}22'>”
f”{texto}</span>”
)

def badge_status_animal(status):
cor_t, cor_f = STATUS_ANIMAL_COR.get(status, (COR[‘cinza’], COR[‘cinza_bg’]))
return badge(status, cor_t, cor_f)

def badge_status_lote(status):
cor_t, cor_f = STATUS_LOTE_COR.get(status, (COR[‘cinza’], COR[‘cinza_bg’]))
return badge(status, cor_t, cor_f)

def badge_gravidade(grav):
mapa = {
‘Alta’:  (COR[‘vermelho’], COR[‘vermelho_bg’]),
‘Media’: (COR[‘amarelo’],  COR[‘amarelo_bg’]),
‘Baixa’: (COR[‘azul’],     COR[‘azul_bg’]),
}
cor_t, cor_f = mapa.get(grav, (COR[‘cinza’], COR[‘cinza_bg’]))
return badge(grav, cor_t, cor_f)

# ── Cards de KPI ─────────────────────────────────────────────────────────────

def card_kpi(titulo, valor, subtitulo=’’, cor=None, delta=None):
if st is None: return
cor_borda = cor or COR[‘verde’]
delta_html = ‘’
if delta is not None:
cor_d = COR[‘verde_claro’] if delta >= 0 else COR[‘vermelho’]
sinal = ‘+’ if delta >= 0 else ‘’
delta_html = f”<div style='color:{cor_d};font-size:12px;margin-top:2px'>{sinal}{delta}</div>”
html = (
f”<div style='background:white;border-left:4px solid {cor_borda};"
f"border-radius:8px;padding:14px 16px;box-shadow:0 1px 3px rgba(0,0,0,0.08)'>”
f”<div style='color:#666;font-size:12px;text-transform:uppercase;letter-spacing:0.5px'>{titulo}</div>”
f”<div style='font-size:24px;font-weight:700;color:#1a1a1a;margin-top:4px'>{valor}</div>”
f”{delta_html}”
f”<div style='color:#999;font-size:11px;margin-top:4px'>{subtitulo}</div>”
f”</div>”
)
st.markdown(html, unsafe_allow_html=True)

def card_kpi_row(itens):
if st is None: return
cols = st.columns(len(itens))
for col, item in zip(cols, itens):
with col:
card_kpi(
item.get(‘titulo’, ‘’),
item.get(‘valor’, ‘’),
item.get(‘subtitulo’, ‘’),
item.get(‘cor’),
item.get(‘delta’),
)
st.write(’’)

# ── Card de alerta ───────────────────────────────────────────────────────────

def alerta(mensagem, tipo=‘info’):
if st is None: return
mapa = {
‘info’:    (’#1565C0’, ‘#E3F2FD’, ‘i’),
‘sucesso’: (’#1B5E20’, ‘#E8F5E9’, ‘v’),
‘aviso’:   (’#E65100’, ‘#FFF3E0’, ‘!’),
‘erro’:    (’#B71C1C’, ‘#FFEBEE’, ‘x’),
}
cor_t, cor_f, icone = mapa.get(tipo, mapa[‘info’])
html = (
f”<div style='background:{cor_f};border-left:4px solid {cor_t};"
f"border-radius:6px;padding:10px 14px;margin:4px 0'>”
f”<span style='color:{cor_t};font-weight:700'>{mensagem}</span>”
f”</div>”
)
st.markdown(html, unsafe_allow_html=True)

# ── Card de animal ───────────────────────────────────────────────────────────

def card_animal(ident, status, gmd=None, score=None, ocorrencias=0):
cor_t, cor_f = STATUS_ANIMAL_COR.get(status, (COR[‘cinza’], COR[‘cinza_bg’]))
gmd_txt = f”GMD: {gmd:.3f} kg/d” if gmd is not None else “Sem pesagens”
score_txt = f”Score: {score}/100” if score is not None else ‘’
oc_txt = f”{ocorrencias} ocorr.” if ocorrencias > 0 else ‘’
html = (
f”<div style='background:white;border:1px solid #e0e0e0;"
f"border-radius:8px;padding:12px;margin-bottom:8px'>”
f”<div style='display:flex;justify-content:space-between;align-items:center'>”
f”<div style='font-weight:600;font-size:14px'>{ident}</div>”
f”<span style='background:{cor_f};color:{cor_t};padding:2px 8px;"
f"border-radius:10px;font-size:11px;font-weight:600'>{status}</span>”
f”</div>”
f”<div style='color:#666;font-size:12px;margin-top:4px'>”
f”{gmd_txt}”
f”{’ | ’ + score_txt if score_txt else ‘’}”
f”{’ | ’ + oc_txt if oc_txt else ‘’}”
f”</div>”
f”</div>”
)
return html

# ── Insight card ─────────────────────────────────────────────────────────────

def insight_card(titulo, descricao, tipo=‘aviso’, acao=None):
mapa = {
‘critico’: (’#B71C1C’, ‘#FFEBEE’, ‘Critico’),
‘aviso’:   (’#E65100’, ‘#FFF3E0’, ‘Atencao’),
‘info’:    (’#1565C0’, ‘#E3F2FD’, ‘Info’),
‘positivo’:(’#1B5E20’, ‘#E8F5E9’, ‘OK’),
}
cor_t, cor_f, label = mapa.get(tipo, mapa[‘aviso’])
acao_html = f”<div style='margin-top:6px;font-size:11px;color:{cor_t}'>{acao}</div>” if acao else ‘’
html = (
f”<div style='background:{cor_f};border-left:4px solid {cor_t};"
f"border-radius:6px;padding:12px;margin-bottom:8px'>”
f”<div style='display:flex;justify-content:space-between'>”
f”<div style='font-weight:600;font-size:13px;color:{cor_t}'>{titulo}</div>”
f”<span style='background:{cor_t}22;color:{cor_t};padding:1px 8px;"
f"border-radius:10px;font-size:10px;font-weight:700'>{label}</span>”
f”</div>”
f”<div style='color:#444;font-size:12px;margin-top:4px'>{descricao}</div>”
f”{acao_html}”
f”</div>”
)
return html
