# rules.py – Regras de negocio e helpers de contexto do BOVIX

# Centraliza: perfil do usuario, filtros por owner_id, cache de listas

import streamlit as st

# ── Cache de dados ────────────────────────────────────────────────────────────

@st.cache_data(ttl=600, show_spinner=False)
def _listar_lotes_cache(owner_id=None):
from database import listar_lotes
return listar_lotes(owner_id=owner_id)

@st.cache_data(ttl=600, show_spinner=False)
def _listar_animais_cache(lote_id):
from database import listar_animais_por_lote
return listar_animais_por_lote(lote_id)

def limpar_cache():
“”“Invalida caches apos cadastros/edicoes.”””
_listar_lotes_cache.clear()
_listar_animais_cache.clear()

# ── Perfil do usuario logado ──────────────────────────────────────────────────

def usuario_atual():
return st.session_state.get(“usuario”)

def is_admin():
u = usuario_atual()
return bool(u and u.get(“perfil”) == “admin”)

def is_vet():
u = usuario_atual()
return bool(u and u.get(“perfil”) == “veterinario”)

def is_fazendeiro():
u = usuario_atual()
return bool(u and u.get(“perfil”) == “fazendeiro”)

def owner_id():
“”“None para admin (ve tudo), id do usuario para fazendeiro/vet.”””
u = usuario_atual()
if not u: return None
if u.get(“perfil”) == “admin”: return None
return u.get(“owner_id”, u[“id”])

def owner_id_medicamentos():
“”“owner_id para filtrar medicamentos. Vet usa primeira fazenda aprovada.”””
u = usuario_atual()
if not u: return None
if is_admin(): return None
if is_vet():
from database import listar_fazendas_do_vet
fazendas = listar_fazendas_do_vet(u[“id”])
return fazendas[0] if fazendas else None
return u.get(“owner_id”, u[“id”])

# ── Listas filtradas por perfil ───────────────────────────────────────────────

def listar_lotes_usuario():
“”“Retorna lotes do usuario logado respeitando o perfil.”””
u = usuario_atual()
if not u: return []
if is_admin():
return _listar_lotes_cache(owner_id=None)
if is_vet():
from database import listar_lotes_vet
return listar_lotes_vet(u[“id”])
return _listar_lotes_cache(owner_id=owner_id())

def listar_medicamentos_usuario():
“”“Retorna medicamentos do usuario logado respeitando o perfil.”””
from database import listar_medicamentos
if is_admin():
return listar_medicamentos(owner_id=None)
if is_vet():
from database import listar_fazendas_do_vet
u = usuario_atual()
fazendas = listar_fazendas_do_vet(u[“id”]) if u else []
return [m for fid in fazendas for m in listar_medicamentos(owner_id=fid)]
return listar_medicamentos(owner_id=owner_id())

# ── Selectboxes padrao ────────────────────────────────────────────────────────

def sel_lote(key=“lote”):
“”“Selectbox de lote filtrado pelo perfil do usuario.”””
lotes = listar_lotes_usuario()
if not lotes:
st.warning(“Nenhum lote cadastrado. Va em Cadastrar Lote primeiro.”)
return None, None
d = {f”{l[1]} (ID {l[0]})”: l[0] for l in lotes}
sel = st.selectbox(“Lote”, list(d.keys()), key=key)
return d[sel], lotes

def sel_animal(lote_id, key=“animal”):
“”“Selectbox de animal filtrado pelo lote.”””
animais = _listar_animais_cache(lote_id)
if not animais:
st.warning(“Nenhum animal neste lote.”)
return None
d = {f”{a[1]} (ID {a[0]})”: a[0] for a in animais}
sel = st.selectbox(“Animal”, list(d.keys()), key=key)
return d[sel]

# ── Verificacoes de acesso ────────────────────────────────────────────────────

def requer_admin():
“”“Para na tela se nao for admin.”””
if not is_admin():
st.error(“Acesso restrito ao administrador.”)
st.stop()

def requer_nao_vet():
“”“Para na tela se for veterinario (dados financeiros).”””
if is_vet():
st.error(“Acesso restrito. Dados financeiros nao disponiveis para veterinarios.”)
st.stop()

def owner_id_lote_novo():
“”“owner_id correto ao criar um lote novo.”””
u = usuario_atual()
if not u: return None
return u.get(“owner_id”, u[“id”])
