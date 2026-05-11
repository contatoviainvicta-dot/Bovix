# pages/relatorios.py – Telas: Exportar Relatorios, Backup

import streamlit as st
import pandas as pd
from database import *
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
)

def hdr(titulo, sub=””, desc=””):
st.title(titulo)
if sub: st.caption(f”{sub} - {desc}” if desc else sub)
st.divider()

def page_exportar_relatorios(u):
hdr(“Exportar Relatorios”, “Relatorios”, “PDF e Excel do lote, sanitario e estoque”)
lote_id, _ = sel_lote(“exp_lote”)
if lote_id:
lote = obter_lote(lote_id)
nome_lote = lote[1] if lote else “lote”
animais = listar_animais_por_lote(lote_id)
pd_dict = {a[0]: listar_pesagens(a[0])    for a in animais}
oc_dict = {a[0]: listar_ocorrencias(a[0]) for a in animais}
c1,c2 = st.columns(2)
with c1:
st.subheader(“Excel do Lote”)
st.write(“Abas: Resumo, Animais, Pesagens, Ocorrencias”)
if *EXP:
xls = gerar_excel_lote(nome_lote, animais, pd_dict, oc_dict)
st.download_button(
label=“Baixar Excel”,
data=xls,
file_name=f”lote*{nome_lote.replace(’ ‘,’*’)}.xlsx”,
mime=“application/vnd.openxmlformats-officedocument.spreadsheetml.sheet”,
key=“dl_xls_lote”,
)
else: st.warning(“exports.py nao encontrado.”)
with c2:
st.subheader(“PDF do Lote”)
if *EXP:
df_anim = pd.DataFrame(animais, columns=[“ID”,“Identificacao”,“Idade”,“Lote ID”])
todos_p = [p for ps in pd_dict.values() for p in ps]
df_peso = pd.DataFrame(todos_p, columns=[“ID”,“Animal ID”,“Peso”,“Data”]) if todos_p else pd.DataFrame()
todos_o = [o for os in oc_dict.values() for o in os]
df_oc   = pd.DataFrame(todos_o, columns=[“ID”,“Animal”,“Data”,“Tipo”,“Desc”,“Grav”,“Custo”,“Dias”,“Status”]) if todos_o else pd.DataFrame()
secoes  = [{“titulo”:“Animais”,“df”:df_anim},{“titulo”:“Pesagens”,“df”:df_peso},{“titulo”:“Ocorrencias”,“df”:df_oc}]
pdf = gerar_pdf_relatorio(f”Relatorio {nome_lote}”, secoes)
st.download_button(
label=“Baixar PDF”,
data=pdf,
file_name=f”relatorio*{nome_lote.replace(’ ‘,’*’)}.pdf”,
mime=“application/pdf”,
key=“dl_pdf_lote”,
)
else: st.warning(“exports.py nao encontrado.”)
st.divider()
st.subheader(“Excel Sanitario”)
if _EXP:
vacs = listar_vacinas_agenda()
meds = listar_medicamentos_usuario()
xls2 = gerar_excel_sanitario(vacs, meds)
st.download_button(
label=“Baixar Excel Sanitario”,
data=xls2,
file_name=“sanitario.xlsx”,
mime=“application/vnd.openxmlformats-officedocument.spreadsheetml.sheet”,
key=“dl_xls_san”,
)

```
# ============================================================
# BACKUP
# ============================================================
```

def page_backup(u):
hdr(“Backup”, “Backup do Sistema”, “Download dos seus dados”)
import database as _dbm
db_path = _dbm.DB_PATH
st.info(f”Banco: `{db_path}`”)
c1,c2 = st.columns(2)
with c1:
st.subheader(“Download ZIP (CSVs)”)
if _BACKUP:
with st.spinner(“Preparando…”):
dados_zip = gerar_backup_zip(db_path)
nome_zip = nome_arquivo_backup(“zip”)
st.download_button(“Baixar ZIP”, dados_zip, nome_zip, “application/zip”, key=“dl_bkp_zip”)
registrar_auditoria(u[“id”], “backup_zip”, “sistema”, None, nome_zip)
else: st.warning(“backup.py nao encontrado.”)
with c2:
st.subheader(“Download SQLite”)
if _BACKUP:
with st.spinner(“Preparando…”):
dados_db = gerar_backup_sqlite(db_path)
nome_db = nome_arquivo_backup(“db”)
st.download_button(“Baixar SQLite”, dados_db, nome_db, “application/octet-stream”, key=“dl_bkp_db”)
else: st.warning(“backup.py nao encontrado.”)

```
# ============================================================
# NOTIFICACOES
# ============================================================
```
