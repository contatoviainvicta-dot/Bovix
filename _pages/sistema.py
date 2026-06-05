# pages/sistema.py -- Telas: Inicio, Buscar Animal, Notificacoes, Log Auditoria, Administracao, Gestao Usuarios

import streamlit as st
try:
    from ux_helpers import (aplicar_css_global, toast_ok, toast_erro,
                            toast_aviso, empty_state, skeleton_cards,
                            erro_com_acao, humanizar_erro,
                            fmt_brl, fmt_data, fmt_data_hora,
                            safe_line_chart, safe_bar_chart)
except ImportError:
    def aplicar_css_global(): pass
    def toast_ok(m): st.success(m)
    def toast_erro(m): st.error(m)
    def toast_aviso(m): st.warning(m)
    def empty_state(t, d, **k): st.info(f"{t} — {d}"); return False
    def skeleton_cards(n=4): pass
    def erro_com_acao(e, a=""): st.error(str(e))
    def humanizar_erro(e): return str(e)
    def fmt_brl(v):
        try:
            v=float(v); i=int(abs(v)); c=round((abs(v)-i)*100)
            s=f"{i:,}".replace(",","."); r=f"R$ {s},{c:02d}"
            return f"-{r}" if v<0 else r
        except: return "R$ 0,00"
    def fmt_data(d):
        try:
            m={"01":"jan","02":"fev","03":"mar","04":"abr","05":"mai",
               "06":"jun","07":"jul","08":"ago","09":"set","10":"out",
               "11":"nov","12":"dez"}
            d=str(d)[:10]; p=d.split("-")
            return f"{p[2]} {m.get(p[1],p[1])} {p[0]}"
        except: return str(d)
    def fmt_data_hora(d): return fmt_data(d)
    def safe_line_chart(df, titulo=None, empty_msg="Sem dados."):
        import pandas as pd
        if df is None or (hasattr(df,"empty") and df.empty): st.info(empty_msg); return
        try:
            df = pd.DataFrame(df).replace([float("inf"),float("-inf")],None).dropna(how="all")
            if not df.empty: safe_line_chart(df)
            else: st.info(empty_msg)
        except Exception as e: st.info(f"Grafico indisponivel: {e}")
    def safe_bar_chart(df, titulo=None, empty_msg="Sem dados."):
        import pandas as pd
        if df is None or (hasattr(df,"empty") and df.empty): st.info(empty_msg); return
        try:
            df = pd.DataFrame(df).replace([float("inf"),float("-inf")],None).dropna(how="all")
            if not df.empty: safe_bar_chart(df)
            else: st.info(empty_msg)
        except Exception as e: st.info(f"Grafico indisponivel: {e}")
import pandas as pd
from datetime import datetime, date
from database import *
try:
    from database import PLANOS_VETERINARIO, PLANOS_FAZENDEIRO
except ImportError:
    PLANOS_VETERINARIO = {'trial': {'nome':'Trial','limite_fazendas':2,'preco':0}}
    PLANOS_FAZENDEIRO  = {'trial': {'nome':'Trial','limite_animais':50,'preco':0}}
from database import _conexao, _ph

try:
    from notifications import (
        email_boas_vindas, email_trial_expirando, email_trial_expirado,
        email_vacina_pendente, email_medicamento_critico, email_configurado
    )
except ImportError:
    def email_configurado(): return False
    def email_boas_vindas(*a, **k): return False, "Email nao configurado"
    def email_trial_expirando(*a, **k): return False, "Email nao configurado"
    def email_trial_expirado(*a, **k): return False, "Email nao configurado"
    def email_vacina_pendente(*a, **k): return False, "Email nao configurado"
    def email_medicamento_critico(*a, **k): return False, "Email nao configurado"

try:
    from cepea import cotacao_com_cache, historico_grafico
except ImportError:
    def cotacao_com_cache(_db): return dict(preco=0.0, data="", fonte="", sucesso=False, msg="")
    def historico_grafico(c): return dict(datas=[], precos=[])

try:
    from exports import gerar_excel_lote, gerar_pdf_relatorio
except ImportError:
    def gerar_excel_lote(*a, **k): return b""
    def gerar_pdf_relatorio(*a, **k): return b""
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
    sel_fazenda_vet,
)

def hdr(titulo, sub="", desc=""):
    st.title(titulo)
    if sub: st.caption(f"{sub} - {desc}" if desc else sub)
    st.divider()

def page_inicio(u):
    aplicar_css_global()
    hora = datetime.now().hour
    sau  = "Bom dia" if hora < 12 else "Boa tarde" if hora < 18 else "Boa noite"

    # ── Header ────────────────────────────────────────────────────────────────
    # Extrair apenas o primeiro nome limpo (sem sufixos técnicos)
    _nome_raw = u.get('nome', '')
    _nome = _nome_raw.split(' - Nome:')[-1].strip() if ' - Nome:' in _nome_raw else _nome_raw
    _nome = _nome.split(' — ')[0].strip() if ' — ' in _nome else _nome
    _nome = _nome.split(' - ')[0].strip() if ' - Fazenda' in _nome else _nome

    # Dados do perfil e plano
    _perfil_label = {
        "fazendeiro":  "Fazendeiro",
        "veterinario": "Veterinário",
        "admin":       "Administrador",
    }.get(u.get("perfil",""), "Usuário")
    _plano_raw = (u.get("plano") or "free").upper()
    _plano_cor = {
        "FREE":"#6B7280","PRO":"#40916C",
        "VET":"#2563EB","ENTERPRISE":"#7C3AED"
    }.get(_plano_raw, "#6B7280")
    _expirado = u.get("plano_expirado") or u.get("status_conta") == "expirado"

    # Saudação + perfil + plano numa linha
    st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:space-between;
     flex-wrap:wrap;gap:8px;margin-bottom:4px">
  <div>
    <span style="font-size:24px;font-weight:700;color:#1B4332">
      {sau}, <strong>{_nome}</strong> 👋</span>
  </div>
  <div style="display:flex;align-items:center;gap:8px">
    <span style="font-size:12px;color:#6B7280">{_perfil_label}</span>
    <span style="background:{_plano_cor};color:white;font-size:11px;
          font-weight:700;padding:3px 10px;border-radius:20px;
          letter-spacing:.5px">{_plano_raw}</span>
  </div>
</div>
""", unsafe_allow_html=True)
    st.caption(datetime.now().strftime("%A, %d/%m/%Y — %H:%M"))

    # Aviso de plano expirado — apenas na tela início
    if _expirado:
        st.warning(
            "⚠️ **Seu plano expirou.** Você está no plano Free. "
            "Acesse **Sistema → Planos** para renovar.",
            icon="⚠️"
        )

    try:
        lotes   = listar_lotes_usuario()
    except Exception as _e_lotes:
        st.error("⚠️ Erro ao carregar dados. Aguarde e recarregue a página.")
        lotes = []
    _oid    = owner_id()
    _is_faz = is_fazendeiro()
    _is_vet = is_vet()

    # ── Alertas do proprio usuario ─────────────────────────────────────────────
    # Para medicamentos: sempre usa o id do usuario (nunca None)
    _oid_med = _oid if _oid is not None else u["id"]
    pendo    = listar_vacinas_pendentes(owner_id=_oid)
    crit     = listar_medicamentos_criticos(owner_id=_oid_med)
    parto    = listar_partos_previstos(owner_id=_oid)
    try:
        _car_alert = listar_animais_em_carencia_fazendeiro(_oid_med)
    except Exception:
        _car_alert = []
    try:
        _visitas_prox = [v for v in listar_visitas(fazenda_owner_id=_oid_med)
                        if v[6] == 'agendada'][:3]
    except Exception:
        _visitas_prox = []
    _monitor_alert = monitoramentos_vencendo(_oid_med, dias=3)
    try:
        _msgs_nl = contar_mensagens_nao_lidas(u["id"])
    except Exception:
        _msgs_nl = 0
    try:
        _receitas_receb = listar_receitas(fazenda_owner_id=_oid_med)[:3]
    except Exception:
        _receitas_receb = []


    # ══════════════════════════════════════════════════════════════════════════
    # DASHBOARD DO FAZENDEIRO
    # ══════════════════════════════════════════════════════════════════════════
    if _is_faz:

        def fmt_brl(v):
            try:
                i, d = f"{float(v):,.2f}".split(".")
                return f"R$ {i.replace(',','.')},{d}"
            except: return "R$ 0,00"

        # ── Calcular dados de IA e metricas ──────────────────────────────────
        import database as _dbc
        try:
            cot = cotacao_com_cache(_dbc)
            _preco_kg = float(cot["preco"]) if cot.get("sucesso") else 195.0
        except Exception:
            _preco_kg = 195.0

        _todos_animais = []
        _prontos_abate = 0
        _melhor_data   = None
        _receita_est   = 0.0
        _margem_est    = 0.0
        _custo_total   = 0.0

        for l in lotes:
            _anim_lote = listar_animais_por_lote(l[0])
            _todos_animais.extend(_anim_lote)
            try:
                _prev = prever_abate(l[0], peso_alvo_kg=450,
                                     preco_kg=_preco_kg, custo_diario=8.0)
                for _p in _prev:
                    _dr = _p.get("dias_restantes")
                    if _dr is not None and _dr <= 30:
                        _prontos_abate += 1
                    _receita_est += float(_p.get("receita_prevista") or 0)
                    _margem_est  += float(_p.get("margem_estimada") or 0)
                    _custo_total += float(_p.get("custo_estimado") or 0)
                    _dp = _p.get("data_prevista")
                    if _dp and (_melhor_data is None or _dp < _melhor_data):
                        _melhor_data = _dp
            except Exception as _e:
                pass  # silenced

        _n_animais = len(_todos_animais)
        _n_partos  = len(parto)

        # ── Formatar melhor data ──────────────────────────────────────────────
        def _fmt_dt(ds):
            if not ds: return "—"
            try:
                from datetime import datetime as _dtm
                meses = {1:"Jan",2:"Fev",3:"Mar",4:"Abr",5:"Mai",6:"Jun",
                         7:"Jul",8:"Ago",9:"Set",10:"Out",11:"Nov",12:"Dez"}
                dt = _dtm.strptime(str(ds)[:10], "%Y-%m-%d").date()
                return f"{dt.day:02d} {meses[dt.month]} {dt.year}"
            except: return str(ds)

        # ══ BLOCO 1: KPIs COM HIERARQUIA VISUAL ═════════════════════════════
        _cor_marg = "#1B4332" if _margem_est >= 0 else "#E24B4A"
        _n_alertas = len(pendo) + len(crit)

        # KPIs primários — destaque máximo
        st.markdown(f"""
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:12px">
  <div style="background:#1B4332;border-radius:12px;padding:20px 24px;color:white">
    <div style="font-size:12px;opacity:.7;letter-spacing:1px;
         text-transform:uppercase;margin-bottom:6px">Receita Estimada</div>
    <div style="font-size:28px;font-weight:700;line-height:1">
      {fmt_brl(_receita_est)}</div>
    <div style="font-size:11px;opacity:.6;margin-top:4px">
      cotação R$ {_preco_kg:.2f}/@</div>
  </div>
  <div style="background:{'#1D9E75' if _margem_est>=0 else '#E24B4A'};
       border-radius:12px;padding:20px 24px;color:white">
    <div style="font-size:12px;opacity:.7;letter-spacing:1px;
         text-transform:uppercase;margin-bottom:6px">Margem Estimada</div>
    <div style="font-size:28px;font-weight:700;line-height:1">
      {fmt_brl(_margem_est)}</div>
    <div style="font-size:11px;opacity:.6;margin-top:4px">sobre custo total</div>
  </div>
  <div style="background:#F5F0E8;border:1.5px solid #1B4332;
       border-radius:12px;padding:20px 24px">
    <div style="font-size:12px;color:#40916C;letter-spacing:1px;
         text-transform:uppercase;margin-bottom:6px">Próximo Abate</div>
    <div style="font-size:22px;font-weight:700;color:#1B4332;line-height:1">
      {_fmt_dt(_melhor_data)}</div>
    <div style="font-size:11px;color:#6B7280;margin-top:4px">
      {_prontos_abate} animal(is) pronto(s)</div>
  </div>
</div>

<!-- KPIs secundários -->
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;
     margin-bottom:16px">
  <div style="background:white;border:1px solid #E5E7EB;border-radius:10px;
       padding:14px 16px">
    <div style="font-size:11px;color:#6B7280;margin-bottom:4px">Total Animais</div>
    <div style="font-size:22px;font-weight:600;color:#1B4332">{_n_animais}</div>
  </div>
  <div style="background:white;border:1px solid #E5E7EB;border-radius:10px;
       padding:14px 16px">
    <div style="font-size:11px;color:#6B7280;margin-bottom:4px">Custo Total</div>
    <div style="font-size:18px;font-weight:600;color:#374151">
      {fmt_brl(_custo_total)}</div>
  </div>
  <div style="background:white;border:1px solid #E5E7EB;border-radius:10px;
       padding:14px 16px">
    <div style="font-size:11px;color:#6B7280;margin-bottom:4px">Partos 30d</div>
    <div style="font-size:22px;font-weight:600;color:#374151">{_n_partos}</div>
  </div>
  <div style="background:{'#FEF3C7' if _n_alertas>0 else 'white'};
       border:1px solid {'#F59E0B' if _n_alertas>0 else '#E5E7EB'};
       border-radius:10px;padding:14px 16px">
    <div style="font-size:11px;color:#6B7280;margin-bottom:4px">Alertas</div>
    <div style="font-size:22px;font-weight:600;
         color:{'#D97706' if _n_alertas>0 else '#374151'}">
      {_n_alertas}</div>
  </div>
</div>
""", unsafe_allow_html=True)

        _c_btn1, _c_btn2 = st.columns(2)
        with _c_btn1:
            if st.button("📊 Análise completa de abate",
                         key="btn_ver_abate", type="primary"):
                st.session_state.menu = "Previsao de Abate IA"; st.rerun()
        with _c_btn2:
            if st.button("💰 Dashboard financeiro",
                         key="btn_ver_fin"):
                st.session_state.menu = "Dashboard Financeiro"; st.rerun()

        st.divider()

        # ══ BLOCO 2: ALERTAS ═════════════════════════════════════════════════
        st.subheader("Alertas")

        # Monitoramentos vencendo — sempre visivel, independente dos outros alertas
        if _monitor_alert:
            st.error(
                f"🔴 **{len(_monitor_alert)} retorno(s) veterinario(s) pendente(s)** — "
                + " | ".join(
                    f"{m.get('brinco') or m['animal_id']}: "
                    f"{'/'.join(reversed(str(m['data_retorno'])[:10].split('-')))}"
                    + (" ⚠ ATRASADO" if m["vencido"] else "")
                    for m in _monitor_alert[:3]
                )
            )

        if pendo or crit or parto or _car_alert:
            al1, al2, al3, al4 = st.columns(4)
            with al1:
                if pendo:
                    with st.expander(f"💉 Vacinas ({len(pendo)})", expanded=True):
                        for v in pendo[:4]:
                            st.caption(f"- {v[3]} | {v[4]}")
            with al2:
                if crit:
                    with st.expander(f"⚠ Medicamentos ({len(crit)})", expanded=True):
                        for m in crit[:4]:
                            mot = "baixo" if (m[3] or 0)<=(m[4] or 0) else f"vence {m[5]}"
                            st.caption(f"- {m[1]}: {m[3]:.0f} {m[2]} ({mot})")
            with al3:
                if parto:
                    with st.expander(f"🐄 Partos ({len(parto)})", expanded=True):
                        for p in parto[:4]:
                            st.caption(f"- {p[1]} | {p[3]}")
            with al4:
                if _car_alert:
                    with st.expander(
                        f"🚫 Carencia ({len(_car_alert)})", expanded=True
                    ):
                        for c in _car_alert[:4]:
                            st.caption(
                                f"- {c[1]}: {c[2]} | libera {'/'.join(reversed(str(c[3])[:10].split('-')))}"
                            )

            # Mensagens nao lidas
            if _msgs_nl:
                st.info(f"📬 {_msgs_nl} mensagem(ns) nao lida(s) do veterinario. Acesse **Mensagens** no menu.")

            # Visitas agendadas pelo vet
            if _visitas_prox:
                st.divider()
                with st.expander(f"Visitas do veterinario ({len(_visitas_prox)})", expanded=True):
                    for v in _visitas_prox:
                        dt_f = fmt_data(v[3])
                        st.caption(f"- {dt_f}: {v[4] or 'Visita tecnica'}")

            # Receitas recebidas
            if _receitas_receb:
                with st.expander(f"💊 Receitas do veterinario ({len(_receitas_receb)})", expanded=False):
                    for r in _receitas_receb:
                        dt_f = fmt_data(r[5])
                        st.caption(f"- {dt_f}: {r[6]} | {r[7]}")

        # ══ BLOCO 3: LOTES ═══════════════════════════════════════════════════
        st.subheader("Seus lotes")
        if not lotes:
            empty_state("Nenhum lote encontrado", "Crie um lote para organizar seus animais.", icone="🌾")
        else:
            ncols = min(3, len(lotes))
            cols  = st.columns(ncols)
            for i, l in enumerate(lotes[:6]):
                try: rs = resumo_lote(l[0])
                except: rs = dict(ativos=0, mortos=0,
                                  vacinas_pendentes=0, ocorrencias=0)
                _tags = []
                if rs.get("mortos"):            _tags.append(f"Mortes: {rs['mortos']}")
                if rs.get("vacinas_pendentes"): _tags.append(f"Vac.: {rs['vacinas_pendentes']}")
                if rs.get("ocorrencias"):       _tags.append(f"Ocorr.: {rs['ocorrencias']}")
                _ico = "🔴" if _tags else "🟢"
                with cols[i % ncols]:
                    st.markdown(f"**{_ico} {l[1]}**")
                    st.caption(f"Animais: {rs.get('ativos',0)} | "
                               f"Entrada: {l[3] or '—'}")
                    if _tags: st.warning(" | ".join(_tags))
                    else:     st.caption("Sem alertas")
                    if st.button("Ver lote", key=f"btn_lote_{l[0]}",
                                 use_container_width=True):
                        st.session_state.menu = "Workspace do Lote"
                        st.session_state["ws_lote_id"] = l[0]
                        st.rerun()

        st.divider()

        # ══ BLOCO 4: BOTOES GRADE 2x3 ════════════════════════════════════════
        _BTNS = [
            ("📝", "Registrar Pesagem",   "Registrar Pesagem"),
            ("🚨", "Nova Ocorrencia",     "Registrar Ocorrencia"),
            ("🐄", "Novo Lote",           "Cadastrar Lote"),
            ("🤖", "Risco Sanitario IA",  "Risco Sanitario IA"),
            ("📈", "Previsao de Abate",   "Previsao de Abate IA"),
            ("📊", "Anomalias de Peso",   "Anomalias de Peso"),
        ]
        _bcols = st.columns(3)
        for _bi, (_ico, _label, _menu) in enumerate(_BTNS):
            with _bcols[_bi % 3]:
                st.markdown(
                    f"<div style='text-align:center;font-size:28px'>{_ico}</div>",
                    unsafe_allow_html=True
                )
                if st.button(_label, key=f"grid_btn_{_bi}",
                             use_container_width=True):
                    st.session_state.menu = _menu; st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # DASHBOARD DO VETERINARIO
    # ══════════════════════════════════════════════════════════════════════════
    elif _is_vet:
        # ── Buscar fazendas aprovadas e agrupar lotes corretamente ────────────
        from database import listar_fazendas_do_vet
        _faz_ids = listar_fazendas_do_vet(u["id"])  # lista de owner_ids aprovados
        _faz_map = {}
        for _foid in _faz_ids:
            _lotes_faz = [l for l in lotes if True]  # placeholder
            # Buscar lotes desta fazenda especifica
            from database import listar_lotes as _ll
            _faz_map[_foid] = _ll(owner_id=_foid)

        _n_fazendas = len(_faz_map)
        _n_animais  = sum(len(listar_animais_por_lote(l[0])) for l in lotes)

        # ── Cards globais ─────────────────────────────────────────────────────
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Fazendas vinculadas",  _n_fazendas)
        c2.metric("Total animais",        _n_animais)
        c3.metric("Vacinas pendentes",    len(pendo),
                  delta="atencao" if pendo else None,
                  delta_color="inverse" if pendo else "off")
        c4.metric("Meds. em alerta",      len(crit),
                  delta="atencao" if crit else None,
                  delta_color="inverse" if crit else "off")

        st.divider()

        # ── Seletor de fazenda ────────────────────────────────────────────────
        if _n_fazendas == 0:
            st.info("Nenhuma fazenda aprovada. Solicite acesso a um fazendeiro.")
            _lotes_sel = []
        else:
            # Montar opcoes de fazenda com nome dos lotes
            _faz_opcoes = {}
            for _foid, _flotes in _faz_map.items():
                _n_an  = sum(len(listar_animais_por_lote(_fl[0])) for _fl in _flotes)
                _nomes = ", ".join(_fl[1] for _fl in _flotes[:2])
                if len(_flotes) > 2: _nomes += f" +{len(_flotes)-2}"
                _label = f"Fazenda {_foid} | {_nomes} | {_n_an} animais"
                _faz_opcoes[_label] = _foid

            if _n_fazendas == 1:
                # Uma fazenda: mostrar label sem seletor interativo
                _unico_label = list(_faz_opcoes.keys())[0]
                st.info(f"Fazenda vinculada: **{_unico_label}**")
                _foid_sel  = list(_faz_opcoes.values())[0]
            else:
                # Multiplas fazendas: seletor dropdown
                st.subheader("Selecione a fazenda")
                _sel_label = st.selectbox(
                    "Fazenda",
                    list(_faz_opcoes.keys()),
                    key="vet_faz_sel",
                    label_visibility="collapsed"
                )
                _foid_sel = _faz_opcoes[_sel_label]

            _lotes_sel = _faz_map[_foid_sel]
            st.divider()

            # ── Alertas da fazenda selecionada ────────────────────────────────
            _ids_lotes_sel = [_fl[0] for _fl in _lotes_sel]
            _pendo_faz = [v for v in pendo if v[1] in _ids_lotes_sel]
            _parto_faz = [p for p in parto if p[2] in [_fl[1] for _fl in _lotes_sel]]

            al1, al2 = st.columns(2)
            with al1:
                st.subheader("Alertas sanitarios")
                if not _pendo_faz and not crit:
                    st.info("Nenhum alerta critico.")
                if _pendo_faz:
                    with st.expander(
                        f"💉 Vacinas pendentes ({len(_pendo_faz)})",
                        expanded=True
                    ):
                        for v in _pendo_faz[:5]:
                            st.caption(f"- {v[3]} | Lote: {v[2]} | {v[4]}")
                if crit:
                    with st.expander(
                        f"⚠ Meds. proprios em alerta ({len(crit)})",
                        expanded=True
                    ):
                        for m in crit[:5]:
                            mot = "baixo" if (m[3] or 0)<=(m[4] or 0)                                   else f"vence {m[5]}"
                            st.caption(f"- {m[1]}: {m[3]:.0f} {m[2]} ({mot})")

            with al2:
                st.subheader("Lotes desta fazenda")
                for _fl in _lotes_sel:
                    try: _rs = resumo_lote(_fl[0])
                    except: _rs = dict(ativos=0, ocorrencias=0)
                    _ico2 = "🔴" if _rs.get("ocorrencias") else "🟢"
                    _n_at = _rs.get("ativos", 0)
                    _n_oc = _rs.get("ocorrencias", 0)
                    with st.container():
                        cc1, cc2 = st.columns([3, 1])
                        with cc1:
                            st.markdown(
                                f"**{_ico2} {_fl[1]}** — "
                                f"{_n_at} animais"
                                + (f" | {_n_oc} ocorr." if _n_oc else "")
                            )
                        with cc2:
                            if st.button(
                                "Abrir", key=f"vet_lote_{_fl[0]}",
                                use_container_width=True
                            ):
                                st.session_state.menu = "Workspace do Lote"
                                st.session_state["ws_lote_id"] = _fl[0]
                                st.rerun()

        st.divider()
        st.subheader("Acoes rapidas")
        qa1, qa2, qa3 = st.columns(3)
        if qa1.button("Registrar Ocorrencia", use_container_width=True):
            st.session_state.menu = "Registrar Ocorrencia"; st.rerun()
        if qa2.button("Registrar Pesagem",    use_container_width=True):
            st.session_state.menu = "Registrar Pesagem";    st.rerun()
        if qa3.button("Prontuario Animal",    use_container_width=True):
            st.session_state.menu = "Prontuario Animal";    st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # DASHBOARD DO ADMIN
    # ══════════════════════════════════════════════════════════════════════════
    else:
        _dash = resumo_dashboard(owner_id=None)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total lotes",   _dash.get("lotes", 0))
        c2.metric("Total animais", _dash.get("animais", 0))
        c3.metric("Usuarios",      len(listar_usuarios()))
        c4.metric("Vacinas pend.", _dash.get("vacinas_pendentes", 0))
        st.divider()
        st.subheader("Acoes rapidas")
        qa1, qa2, qa3 = st.columns(3)
        if qa1.button("Gestao Usuarios",  use_container_width=True):
            st.session_state.menu = "Gestao Usuarios";  st.rerun()
        if qa2.button("Log Auditoria",    use_container_width=True):
            st.session_state.menu = "Log Auditoria";    st.rerun()
        if qa3.button("Administracao",    use_container_width=True):
            st.session_state.menu = "Administracao";    st.rerun()

    # ============================================================
    # BUSCAR ANIMAL
    # ============================================================


def page_buscar_animal(u):
    lotes = listar_lotes_usuario()
    hdr("Buscar Animal", "Busca Global", "Encontre qualquer animal pelo brinco ou identificacao")
    if is_vet():
        sel_fazenda_vet(key="vet_faz_buscar")

    termo = st.text_input("Identificacao / brinco", placeholder="Ex: BOI-001")
    if termo:
        # Buscar apenas nos lotes do usuario logado
        _lotes_busca = listar_lotes_usuario()
        _lids_busca  = {l[0] for l in _lotes_busca}
        encontrados  = [
            a
            for lid in _lids_busca
            for a in listar_animais_por_lote(lid)
            if termo.lower() in a[1].lower()
        ]
        if encontrados:
            st.success(f"{len(encontrados)} animal(is) encontrado(s)")
            for a in encontrados:
                lote = obter_lote(a[3])
                nome_lote = lote[1] if lote else "?"
                with st.expander(f"{a[1]} -- Lote: {nome_lote}"):
                    det = obter_animal(a[0])
                    c1,c2 = st.columns(2)
                    with c1:
                        st.caption(f"ID: {a[0]} | Idade: {a[2]} meses")
                        if det: st.caption(f"Raca: {det[5]} | Peso alvo: {det[7]} kg")
                    with c2:
                        ps = listar_pesagens(a[0])
                        ocs = listar_ocorrencias(a[0])
                        sc  = calcular_score_saude(a[0])
                        st.caption(f"Pesagens: {len(ps)} | Ocorrencias: {len(ocs)}")
                        st.write(f"Score saude: {sc['score']}/100 ({sc['classificacao']})")
                        car = verificar_carencia(a[0])
                        if car["em_carencia"]:
                            st.warning(f"Em carencia ate {car['liberado_em']}")
        else:
            st.warning(f"Nenhum animal encontrado para '{termo}'")

    # ============================================================
    # CADASTRAR LOTE
    # ============================================================


def page_notificacoes(u):
    lotes = listar_lotes_usuario()
    parto = listar_partos_previstos(owner_id=owner_id())
    pend  = listar_vacinas_pendentes(owner_id=owner_id())
    _oid_notif_med = owner_id() if owner_id() is not None else u["id"]
    crit  = listar_medicamentos_criticos(owner_id=_oid_notif_med)
    hdr("Notificacoes", "Central de Notificacoes", "Alertas automaticos e manuais por e-mail")
    if is_vet():
        sel_fazenda_vet(key="vet_faz_notif")


    if not email_configurado():
        st.warning("E-mail nao configurado. Configure em .streamlit/secrets.toml:")
        st.code("""[email]
    smtp_host     = smtp.gmail.com
    smtp_port     = 587
    smtp_user     = seu@gmail.com
    smtp_password = senha_app_google
    remetente     = Gestao Pecuaria <seu@gmail.com>""", language="toml")
        st.info("Use Senha de App do Google - nao a senha da conta. Veja: myaccount.google.com/apppasswords")
    else:
        toast_ok("E-mail configurado e pronto para envio.")

    st.divider()
    tab_alertas, tab_risco, tab_abate, tab_config = st.tabs([
        "Alertas do Sistema", "Alerta de Risco IA", "Alerta de Abate IA", "Historico"
    ])

    with tab_alertas:
        st.subheader("Alertas manuais")
        col_a1, col_a2, col_a3 = st.columns(3)

        with col_a1:
            st.metric("Vacinas pendentes", len(pend),
                     delta="atencao" if pend else None, delta_color="inverse")
            if pend:
                destino_v = st.text_input("Email destino", value=u["email"], key="dest_vac")
                if st.button("Enviar alerta vacinas", type="primary", key="btn_vac"):
                    if email_configurado():
                        vs = [{"lote":v[2],"vacina":v[3],"data_prevista":v[4]} for v in pend]
                        ok, msg = email_vacina_pendente(destino_v, u["nome"], vs)
                        st.success(msg) if ok else st.error(msg)
                    else:
                        st.error("Configure o e-mail primeiro")
            else:
                empty_state("Vacinas em dia", "Nenhuma vacina pendente no momento.", icone="✅")

        with col_a2:
            st.metric("Medicamentos criticos", len(crit),
                     delta="atencao" if crit else None, delta_color="inverse")
            if crit:
                destino_m = st.text_input("Email destino", value=u["email"], key="dest_med")
                if st.button("Enviar alerta meds", type="primary", key="btn_med"):
                    if email_configurado():
                        meds = [{"nome":m[1],"estoque_atual":m[3],"unidade":m[2],"validade":m[5] or ""} for m in crit]
                        ok, msg = email_medicamento_critico(destino_m, u["nome"], meds)
                        st.success(msg) if ok else st.error(msg)
                    else:
                        st.error("Configure o e-mail primeiro")
            else:
                toast_ok("Estoque OK")

        with col_a3:
            st.metric("Partos previstos 30d", len(parto))
            if parto:
                destino_p = st.text_input("Email destino", value=u["email"], key="dest_par")
                if st.button("Enviar alerta partos", type="primary", key="btn_par"):
                    if email_configurado():
                        pts = [{"animal":p[1],"lote":p[2],"data_parto_previsto":p[3]} for p in parto]
                        ok, msg = email_parto_previsto(destino_p, u["nome"], pts)
                        st.success(msg) if ok else st.error(msg)
                    else:
                        st.error("Configure o e-mail primeiro")
            else:
                st.info("Nenhum parto previsto")

    with tab_risco:
        st.subheader("Alerta de Risco Sanitario por IA")
        st.caption("Envia analise de risco de todos os lotes para um email")
        lotes_risco = listar_lotes_usuario()
        if not lotes_risco:
            empty_state("Nenhum lote encontrado", "Crie um lote para organizar seus animais.", icone="🌾")
        else:
            with st.spinner("Calculando riscos..."):
                resumo_r = resumo_ia_fazenda(owner_id=owner_id())

            # Mostrar resumo
            criticos_ia = [r for r in resumo_r if r['risco_nivel'] in ['Critico','Alto']]
            if criticos_ia:
                st.error(f"{len(criticos_ia)} lote(s) com risco Alto ou Critico!")
                for r in criticos_ia:
                    st.warning(f"**{r['lote_nome']}** - {r['risco_nivel']} ({r['risco_score']}pts) - {r['principal_risco']}")
            else:
                empty_state("Nenhum lote encontrado", "Crie um lote para organizar seus animais.", icone="🌾")

            destino_r = st.text_input("Enviar relatorio para", value=u["email"], key="dest_risco")
            if st.button("Enviar relatorio de risco por email", type="primary", key="btn_risco"):
                if email_configurado():
                    # Montar lista de vacinas pendentes como proxy de risco
                    vs_r = [{"lote":r['lote_nome'],
                             "vacina":f"Risco {r['risco_nivel']} ({r['risco_score']}pts)",
                             "data_prevista":r['principal_risco']} for r in resumo_r]
                    ok, msg = email_vacina_pendente(destino_r, u["nome"], vs_r)
                    toast_ok("Relatorio enviado!") if ok else st.error(msg)
                else:
                    st.error("Configure o e-mail primeiro")

    with tab_abate:
        st.subheader("Alerta de Animais Proximos do Abate")
        lote_id_ab, _ = sel_lote("notif_abate_lote")
        if lote_id_ab:
            col_ab1, col_ab2, col_ab3 = st.columns(3)
            with col_ab1: peso_ab = st.number_input("Peso alvo (kg)", 300.0, 600.0, 450.0, key="notif_pa")
            with col_ab2: preco_ab = st.number_input("Preco/kg (R$)", 1.0, 50.0, 10.0, key="notif_pp")
            with col_ab3: custo_ab = st.number_input("Custo diario (R$)", 1.0, 100.0, 12.0, key="notif_cd")

            with st.spinner("Calculando previsoes..."):
                prev_ab = prever_abate(lote_id_ab, peso_ab, preco_ab, custo_ab)

            prontos_ab = [p for p in prev_ab
                         if p['status'] in ['Pronto para abate','Proximo do abate']]
            st.metric("Animais prontos ou proximos", len(prontos_ab))

            if prontos_ab:
                destino_ab = st.text_input("Enviar para", value=u["email"], key="dest_abate")
                if st.button("Enviar alerta de abate", type="primary", key="btn_abate"):
                    if email_configurado():
                        lista_ab = [{"animal":p['identificacao'],
                                    "lote": lote_id_ab,
                                    "peso_atual":p['peso_atual'],
                                    "peso_alvo":peso_ab,
                                    "data_prevista":p['data_prevista'] or "Pronto"} for p in prontos_ab]
                        ok, msg = email_abate_previsto(destino_ab, u["nome"], lista_ab)
                        st.success(msg) if ok else st.error(msg)
                    else:
                        st.error("Configure o e-mail primeiro")
            else:
                st.info("Nenhum animal proximo do peso de abate com os parametros atuais.")

    with tab_config:
        st.info("Historico de notificacoes enviadas em breve.")

    if u["perfil"] == "admin":
        st.divider()
        st.subheader("Gestao de Planos")
        usuarios = listar_usuarios()
        if usuarios:
            df_u = pd.DataFrame(usuarios, columns=["ID","Nome","Email","Perfil","Fazenda"])
            st.dataframe(df_u, use_container_width=True)
        with st.form("form_conv"):
            uid_c = st.number_input("ID usuario para converter para PAGO", 1, step=1)
            if st.form_submit_button("Converter para pago"):
                converter_para_pago(int(uid_c))
                st.success(f"Usuario {uid_c} convertido!"); st.rerun()

    # ============================================================
    # LOG AUDITORIA
    # ============================================================


def page_log_auditoria(u):
    hdr("Log Auditoria", "Log de Auditoria", "Historico de acoes por usuario")
    if u["perfil"] != "admin":
        st.warning("Acesso restrito a administradores.")
    else:
        c1,c2 = st.columns(2)
        lim   = c1.slider("Ultimos registros", 10, 500, 100)
        usuarios = listar_usuarios()
        dict_us  = {"Todos": None, **{f"{x[1]} (ID {x[0]})": x[0] for x in usuarios}}
        uf       = c2.selectbox("Filtrar usuario", list(dict_us.keys()))
        logs = listar_auditoria(lim, dict_us[uf])
        if logs:
            df_log = pd.DataFrame(logs, columns=["ID","Usuario","Acao","Tabela","Reg ID","Detalhe","Data/Hora"])
            st.dataframe(df_log, use_container_width=True)
            st.metric("Total registros", len(logs))
        else: st.info("Nenhum registro.")

    # ============================================================
    # ADMINISTRACAO
    # ============================================================


def page_administracao(u):
    hdr("Administracao", "Administracao", "Usuarios, planos e configuracoes")
    is_admin_local = u["perfil"] == "admin"
    t1, t2, t_em = st.tabs(["Usuarios", "Alterar Senha", "Disparar Emails Trial"])

    with t_em:
        if not is_admin_local:
            st.warning("Acesso restrito a administradores.")
        else:
            st.subheader("Emails automaticos de trial")
            st.caption("Envia emails para usuarios com trial expirando ou expirado.")
            try:
                from notifications import (
                    email_trial_expirando, email_trial_expirado, email_configurado
                )
                _has_email = True
            except ImportError:
                _has_email = False

            if not _has_email or not email_configurado():
                st.warning("E-mail nao configurado. Configure SMTP em .streamlit/secrets.toml.")
            else:
                try:
                    usuarios_trial = listar_usuarios_trial_expirando(dias_limite=7)
                except Exception:
                    usuarios_trial = []

                if not usuarios_trial:
                    st.info("Nenhum usuario com trial expirando nos proximos 7 dias.")
                else:
                    st.info(f"**{len(usuarios_trial)} usuario(s) em situacao de trial:**")
                    for usr in usuarios_trial:
                        uid_t, nome_t, email_t = usr[0], usr[1], usr[2]
                        dias_rest = usr[3] if len(usr) > 3 else 0
                        status = "Expirado" if dias_rest <= 0 else f"{dias_rest} dia(s) restantes"
                        with st.expander(f"{nome_t} - {email_t} - {status}"):
                            c1, c2 = st.columns(2)
                            with c1:
                                if 0 < dias_rest <= 7:
                                    if st.button("Enviar 'expirando'", key=f"em_e_{uid_t}"):
                                        ok, msg = email_trial_expirando(email_t, nome_t, dias_rest)
                                        st.success(msg) if ok else st.error(msg)
                            with c2:
                                if dias_rest <= 0:
                                    if st.button("Enviar 'expirado'", key=f"em_x_{uid_t}"):
                                        ok, msg = email_trial_expirado(email_t, nome_t)
                                        st.success(msg) if ok else st.error(msg)

                    st.divider()
                    if st.button("Disparar TODOS os emails", type="primary", key="em_all"):
                        ok_n, err_n = 0, 0
                        for usr in usuarios_trial:
                            uid_t, nome_t, email_t = usr[0], usr[1], usr[2]
                            dias_rest = usr[3] if len(usr) > 3 else 0
                            try:
                                if 0 < dias_rest <= 7:
                                    ok, _ = email_trial_expirando(email_t, nome_t, dias_rest)
                                elif dias_rest <= 0:
                                    ok, _ = email_trial_expirado(email_t, nome_t)
                                else:
                                    continue
                                if ok: ok_n += 1
                                else:  err_n += 1
                            except Exception:
                                err_n += 1
                        st.success(f"Sucesso: {ok_n} | Erros: {err_n}")

    with t1:
        if not is_admin_local: st.warning("Acesso restrito a administradores.")
        else:
            usuarios = listar_usuarios()
            if usuarios:
                df_u = pd.DataFrame(usuarios, columns=["ID","Nome","Email","Perfil","Fazenda"])
                st.dataframe(df_u, use_container_width=True)
            st.subheader("Criar usuario")
            with st.form("form_user"):
                au1,au2 = st.columns(2)
                with au1:
                    n_nome  = st.text_input("Nome")
                    n_email = st.text_input("Email")
                with au2:
                    n_senha = st.text_input("Senha", type="password")
                    n_perf  = st.selectbox("Perfil", ["fazendeiro","veterinario","admin"])
                if st.form_submit_button("Criar", type="primary"):
                    if n_nome and n_email and n_senha:
                        try:
                            uid_n = criar_usuario(n_nome, n_email, n_senha, n_perf)
                            ativar_trial(uid_n)
                            toast_ok("Usuario criado!"); st.rerun()
                        except Exception: st.error("Email ja cadastrado.")
                    else: st.error("Preencha todos os campos.")
    with t2:
        with st.form("form_senha"):
            senha_a = st.text_input("Senha atual", type="password")
            nova_s  = st.text_input("Nova senha", type="password")
            conf_s  = st.text_input("Confirmar", type="password")
            if st.form_submit_button("Alterar", type="primary"):
                if not autenticar_usuario(u["email"], senha_a): st.error("Senha atual incorreta.")
                elif nova_s != conf_s:                          st.error("Senhas nao coincidem.")
                elif len(nova_s) < 6:                          st.error("Minimo 6 caracteres.")
                else:
                    alterar_senha(u["id"], nova_s)
                    st.success("Senha alterada!")

    # ============================================================
    # EDITAR LOTE
    # ============================================================


def page_gestao_usuarios(u):
    hdr("Gestao Usuarios", "Planos e Acessos", "Gerencie planos e acessos de veterinarios")

    if not is_admin():
        st.error("Acesso restrito ao administrador.")
        st.stop()

    tab_pend, tab_usuarios, tab_acessos, tab_faz = st.tabs([
        "Solicitacoes Pendentes",
        "Gerenciar Planos",
        "Acessos Veterinarios",
        "Acesso Fazendeiros",
    ])

    # ── ABA 1: Solicitacoes pendentes ────────────────────────────────────────
    with tab_pend:
        st.subheader("Solicitacoes de acesso pendentes")
        pendentes = listar_solicitacoes_pendentes()
        if not pendentes:
            st.info("Nenhuma solicitacao pendente.")
        else:
            st.warning(f"{len(pendentes)} solicitacao(oes) aguardando aprovacao")
            for req in pendentes:
                vet_id, vet_nome, vet_email = req[1], req[2], req[3]
                owner_id, faz_nome = req[4], req[5]
                data_req = req[8]
                with st.expander(f"Vet: {vet_nome} -> Fazenda: {faz_nome} | {data_req}"):
                    st.markdown(f"**Veterinario:** {vet_nome} ({vet_email})")
                    st.markdown(f"**Fazenda:** {faz_nome}")
                    st.markdown(f"**Solicitado em:** {data_req}")
                    lim_vet = verificar_limite_fazendas(vet_id)
                    st.caption(f"Fazendas do vet: {lim_vet['msg']}")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("Aprovar", key=f"apr_{vet_id}_{owner_id}", type="primary"):
                            r = aprovar_acesso_vet(vet_id, owner_id, u["id"], True)
                            st.success(r["msg"]); st.rerun()
                    with c2:
                        if st.button("Rejeitar", key=f"rej_{vet_id}_{owner_id}"):
                            r = aprovar_acesso_vet(vet_id, owner_id, u["id"], False)
                            st.error(r["msg"]); st.rerun()

    # ── ABA 2: Gerenciar Planos ──────────────────────────────────────────────
    with tab_usuarios:
        st.subheader("Gerenciar planos dos usuarios")
        usuarios_todos = listar_usuarios()
        if not usuarios_todos:
            st.info("Nenhum usuario cadastrado.")
        else:
            for usr in usuarios_todos:
                uid_u, nome_u, email_u, perfil_u = usr[0], usr[1], usr[2], usr[3]
                limites = obter_limites_usuario(uid_u)
                plano_atual = limites["plano_nome"] if limites else "trial"
                status_conta = limites["status_conta"] if limites else "pendente"

                with st.expander(f"{nome_u} | {perfil_u} | Plano: {plano_atual} | Status: {status_conta}"):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.markdown(f"**Email:** {email_u}")
                        st.markdown(f"**Perfil:** {perfil_u}")
                    with c2:
                        if limites:
                            if perfil_u == "veterinario":
                                lim = verificar_limite_fazendas(uid_u)
                            else:
                                lim = verificar_limite_animais(uid_u)
                            _uso_msg = lim.get('msg', f"{lim.get('atual',0)}/{lim.get('limite',0)}") if isinstance(lim, dict) else str(lim)
                            st.markdown(f"**Uso:** {_uso_msg}")
                    with c3:
                        if status_conta == "pendente" and perfil_u != "admin":
                            if st.button("Aprovar conta", key=f"aprc_{uid_u}"):
                                aprovar_conta_usuario(uid_u, u["id"])
                                st.success("Conta aprovada!"); st.rerun()

                    if perfil_u != "admin":
                        st.divider()
                        if perfil_u == "veterinario":
                            opcoes_plano = list(PLANOS_VETERINARIO.keys())
                            planos_info  = PLANOS_VETERINARIO
                        else:
                            opcoes_plano = list(PLANOS_FAZENDEIRO.keys())
                            planos_info  = PLANOS_FAZENDEIRO

                        idx_atual = opcoes_plano.index(plano_atual) if plano_atual in opcoes_plano else 0
                        novo_plano = st.selectbox(
                            "Alterar plano", opcoes_plano,
                            index=idx_atual, key=f"plano_{uid_u}",
                            format_func=lambda x: f"{planos_info[x]['nome']} - R$ {planos_info[x]['preco']}/mes"
                        )

                        col_btn, col_exp = st.columns(2)
                        with col_btn:
                            if st.button("Salvar plano", key=f"sv_plano_{uid_u}", type="primary"):
                                definir_plano_usuario(uid_u, perfil_u, novo_plano, u["id"])
                                toast_ok("Plano atualizado para {planos_info[novo_plano]['nome']}")
                                st.rerun()
                        with col_exp:
                            sp_u = obter_status_plano(uid_u)
                            st.caption(f"Expira: {sp_u.get('plano_expira','N/A')}")

    # ── ABA 3: Acessos Veterinarios ─────────────────────────────────────────
    with tab_faz:
        st.subheader("Gerenciar acesso de fazendeiros")
        st.caption("Suspenda ou reative o acesso de fazendeiros ao sistema.")
        fazendeiros = [u2 for u2 in listar_usuarios()
                       if u2[3] == "fazendeiro"]
        if not fazendeiros:
            st.info("Nenhum fazendeiro cadastrado.")
        else:
            for faz in fazendeiros:
                fid, fnome, femail = faz[0], faz[1], faz[2]
                lim_faz = obter_limites_usuario(fid)
                status_faz = lim_faz["status_conta"] if lim_faz else "pendente"
                plano_faz  = lim_faz["plano_nome"]   if lim_faz else "trial"
                with st.expander(f"{fnome} | {femail} | {plano_faz} | Status: {status_faz}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"**Email:** {femail}")
                        st.markdown(f"**Plano:** {plano_faz}")
                        lim_a = verificar_limite_animais(fid)
                        st.write(f"**Uso:** {lim_a['msg']}")
                    with c2:
                        if status_faz == "ativo":
                            if st.button("Suspender acesso", key=f"susp_{fid}",
                                         type="primary"):
                                with _conexao() as conn:
                                    cur = conn.cursor()
                                    p = _ph()
                                    cur.execute(
                                        f"UPDATE usuarios SET status_conta={p} WHERE id={p}",
                                        ("suspenso", fid)
                                    )
                                    conn.commit()
                                registrar_auditoria(u["id"], "suspender_fazendeiro",
                                                    "usuarios", fid, fnome)
                                st.warning(f"Acesso de {fnome} suspenso.")
                                st.rerun()
                        elif status_faz in ("suspenso", "pendente"):
                            if st.button("Reativar acesso", key=f"reativ_{fid}"):
                                with _conexao() as conn:
                                    cur = conn.cursor()
                                    p = _ph()
                                    cur.execute(
                                        f"UPDATE usuarios SET status_conta={p} WHERE id={p}",
                                        ("ativo", fid)
                                    )
                                    conn.commit()
                                registrar_auditoria(u["id"], "reativar_fazendeiro",
                                                    "usuarios", fid, fnome)
                                toast_ok(f"Acesso de {fnome} reativado.")
                                st.rerun()
                        else:
                            st.caption(f"Status: {status_faz}")

    with tab_acessos:
        st.subheader("Acessos veterinario-fazenda")

        todos_acessos = listar_acessos_vet()
        if not todos_acessos:
            st.info("Nenhum acesso configurado.")
        else:
            df_ac = pd.DataFrame(todos_acessos, columns=[
                "ID","Vet ID","Veterinario","Email Vet",
                "Fazenda ID","Fazenda","Email Faz",
                "Status","Data Solicitacao","Data Aprovacao"
            ])
            st.dataframe(
                df_ac[["Veterinario","Fazenda","Status","Data Solicitacao","Data Aprovacao"]],
                use_container_width=True
            )
            st.divider()
            st.subheader("Revogar acesso")
            aprovados = [a for a in todos_acessos if a[7] == "aprovado"]
            if aprovados:
                opts = {f"{a[2]} -> {a[5]}": (a[1], a[4]) for a in aprovados}
                sel_rev = st.selectbox("Selecionar acesso aprovado", list(opts.keys()), key="rev_sel")
                if st.button("Revogar acesso", type="primary", key="rev_btn"):
                    vet_r, own_r = opts[sel_rev]
                    r = revogar_acesso_vet(vet_r, own_r, u["id"])
                    st.success(r["msg"]); st.rerun()
            else:
                st.info("Nenhum acesso aprovado para revogar.")

        st.divider()
        st.subheader("Conceder acesso manualmente")
        st.caption("Adicione acesso de veterinario a uma fazenda sem solicitacao")
        usuarios_vet = [usr for usr in listar_usuarios() if usr[3] == "veterinario"]
        usuarios_faz = [usr for usr in listar_usuarios() if usr[3] == "fazendeiro"]
        if usuarios_vet and usuarios_faz:
            cv1, cv2 = st.columns(2)
            with cv1:
                dict_vet_m = {f"{v[1]} ({v[2]})": v[0] for v in usuarios_vet}
                vet_man = st.selectbox("Veterinario", list(dict_vet_m.keys()), key="man_vet")
            with cv2:
                dict_faz_m = {f"{f[1]} ({f[2]})": f[0] for f in usuarios_faz}
                faz_man = st.selectbox("Fazenda", list(dict_faz_m.keys()), key="man_faz")
            if st.button("Conceder acesso", type="primary", key="man_btn"):
                vet_id_m = dict_vet_m[vet_man]
                faz_id_m = dict_faz_m[faz_man]
                r = solicitar_acesso_vet(vet_id_m, faz_id_m)
                if r["ok"] or "ja existe" in r["msg"]:
                    aprovar_acesso_vet(vet_id_m, faz_id_m, u["id"], True)
                    st.success("Acesso concedido!"); st.rerun()
                else:
                    st.error(r["msg"])

    # ============================================================
    # RISCO SANITARIO IA
    # ============================================================




def page_configurar_whatsapp(u):
    """Tela de configuração do WhatsApp pelo admin/fazendeiro."""
    from ux_helpers import toast_ok, toast_erro, fmt_brl
    st.subheader("📱 Configurar Notificações WhatsApp")
    st.caption("Configure o provedor de WhatsApp para receber alertas no celular")

    try:
        from database import obter_config_sistema, salvar_config_sistema
    except ImportError:
        st.error("Módulo de configuração não disponível.")
        return

    cfg = obter_config_sistema("whatsapp") or {}

    with st.expander("ℹ️ Como funciona", expanded=False):
        st.markdown("""
**Z-API** (recomendado para Brasil):
- Plano a partir de R$ 97/mês · [z-api.io](https://z-api.io)
- Crie uma instância e copie o Instance ID e Token

**Twilio** (internacional):
- Pay-as-you-go · [twilio.com](https://www.twilio.com)
- Precisará de Account SID, Auth Token e número WhatsApp Business
        """)

    provedor = st.selectbox(
        "Provedor",
        ["", "zapi", "twilio"],
        index=["","zapi","twilio"].index(cfg.get("provedor","")) if cfg.get("provedor","") in ["","zapi","twilio"] else 0,
        format_func=lambda x: {"":"Selecione...","zapi":"Z-API (Brasil)","twilio":"Twilio (Internacional)"}.get(x,x)
    )

    st.divider()

    if provedor == "zapi":
        st.markdown("**Configuração Z-API**")
        c1, c2 = st.columns(2)
        with c1:
            zapi_id    = st.text_input("Instance ID", value=cfg.get("zapi_instance_id",""),
                                        type="password")
        with c2:
            zapi_token = st.text_input("Token",       value=cfg.get("zapi_token",""),
                                        type="password")
        zapi_client = st.text_input("Client Token (opcional)",
                                     value=cfg.get("zapi_client_token",""),
                                     type="password")

    elif provedor == "twilio":
        st.markdown("**Configuração Twilio**")
        c1, c2 = st.columns(2)
        with c1:
            tw_sid   = st.text_input("Account SID",  value=cfg.get("twilio_account_sid",""),
                                      type="password")
        with c2:
            tw_token = st.text_input("Auth Token",   value=cfg.get("twilio_auth_token",""),
                                      type="password")
        tw_from  = st.text_input("Número From", value=cfg.get("twilio_from_number",
                                                               "whatsapp:+14155238886"))

    st.divider()
    st.markdown("**Número para receber alertas**")
    fone_alerta = st.text_input(
        "Telefone (com DDD, ex: 11999998888)",
        value=cfg.get("fone_alerta",""),
        help="Este número receberá os alertas de vacinas, carências e abate"
    )

    st.markdown("**Tipos de alerta**")
    _c1, _c2 = st.columns(2)
    with _c1:
        al_vacina   = st.checkbox("Vacinas pendentes",    value=cfg.get("al_vacina", True))
        al_carencia = st.checkbox("Carência vencendo",    value=cfg.get("al_carencia", True))
    with _c2:
        al_abate    = st.checkbox("Projeção de abate",    value=cfg.get("al_abate", True))
        al_receita  = st.checkbox("Nova receita do vet",  value=cfg.get("al_receita", True))

    col_s, col_t = st.columns(2)
    with col_s:
        if st.button("💾 Salvar configuração", type="primary", key="btn_salvar_wpp"):
            nova_cfg = dict(
                provedor=provedor,
                fone_alerta=fone_alerta,
                al_vacina=al_vacina, al_carencia=al_carencia,
                al_abate=al_abate, al_receita=al_receita,
            )
            if provedor == "zapi":
                nova_cfg.update(zapi_instance_id=zapi_id,
                                zapi_token=zapi_token,
                                zapi_client_token=zapi_client)
            elif provedor == "twilio":
                nova_cfg.update(twilio_account_sid=tw_sid,
                                twilio_auth_token=tw_token,
                                twilio_from_number=tw_from)
            try:
                salvar_config_sistema("whatsapp", nova_cfg)
                toast_ok("Configuração salva!")
            except Exception as _e:
                toast_erro(f"Erro ao salvar: {_e}")

    with col_t:
        if st.button("🧪 Testar envio", key="btn_testar_wpp"):
            if not fone_alerta:
                st.warning("Informe o telefone para teste.")
            else:
                try:
                    from whatsapp import enviar_whatsapp
                    ok = enviar_whatsapp(fone_alerta,
                                         "✅ *Auroque* — Teste de notificação funcionando!")
                    if ok:
                        toast_ok(f"Mensagem enviada para {fone_alerta[-4:]}****")
                    else:
                        toast_erro("Falha no envio — verifique as credenciais.")
                except Exception as _e:
                    toast_erro(f"Erro: {_e}")


def page_exportar_dados(u):
    """Tela de exportação de dados para Excel/CSV."""
    from ux_helpers import toast_ok, toast_erro
    st.subheader("📥 Exportar Dados")
    st.caption("Baixe seus dados em Excel para análise externa ou relatórios")

    _oid = owner_id() or u["id"]

    try:
        from export import (exportar_tudo, exportar_animais,
                             exportar_pesagens, exportar_financeiro,
                             exportar_veterinario)
        _export_ok = True
    except ImportError:
        _export_ok = False
        st.warning("Módulo de exportação não disponível. "
                   "Verifique se export.py está na raiz do projeto.")

    if not _export_ok:
        return

    st.markdown("**Escolha o que exportar:**")
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("##### 📦 Exportação completa")
        st.caption("Todos os dados em um único arquivo Excel com múltiplas abas")
        if st.button("⬇️ Exportar tudo (.xlsx)",
                     key="btn_exp_tudo", type="primary",
                     use_container_width=True):
            with st.spinner("Gerando arquivo..."):
                try:
                    data = exportar_tudo(_oid)
                    ts = datetime.now().strftime("%Y%m%d_%H%M")
                    st.download_button(
                        "💾 Baixar auroque_completo.xlsx",
                        data=data,
                        file_name=f"auroque_completo_{ts}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument"
                             ".spreadsheetml.sheet",
                        key="dl_tudo"
                    )
                except Exception as _e:
                    toast_erro(f"Erro: {_e}")

    with c2:
        st.markdown("##### 🐄 Animais e pesagens")
        st.caption("Lista de animais por lote com histórico de pesagens")
        col_a, col_p = st.columns(2)
        with col_a:
            if st.button("⬇️ Animais",
                         key="btn_exp_anim", use_container_width=True):
                with st.spinner("Gerando..."):
                    try:
                        data = exportar_animais(_oid)
                        st.download_button(
                            "💾 animais.xlsx", data=data,
                            file_name="auroque_animais.xlsx",
                            mime="application/vnd.openxmlformats-officedocument"
                                 ".spreadsheetml.sheet",
                            key="dl_anim"
                        )
                    except Exception as _e:
                        toast_erro(f"Erro: {_e}")
        with col_p:
            if st.button("⬇️ Pesagens",
                         key="btn_exp_pes", use_container_width=True):
                with st.spinner("Gerando..."):
                    try:
                        data = exportar_pesagens(_oid)
                        st.download_button(
                            "💾 pesagens.xlsx", data=data,
                            file_name="auroque_pesagens.xlsx",
                            mime="application/vnd.openxmlformats-officedocument"
                                 ".spreadsheetml.sheet",
                            key="dl_pes"
                        )
                    except Exception as _e:
                        toast_erro(f"Erro: {_e}")

    st.divider()
    c3, c4 = st.columns(2)

    with c3:
        st.markdown("##### 💰 Financeiro")
        st.caption("DRE, custos variáveis e registro de vendas")
        if st.button("⬇️ Exportar financeiro",
                     key="btn_exp_fin", use_container_width=True):
            with st.spinner("Gerando..."):
                try:
                    data = exportar_financeiro(_oid)
                    if data:
                        st.download_button(
                            "💾 financeiro.xlsx", data=data,
                            file_name="auroque_financeiro.xlsx",
                            mime="application/vnd.openxmlformats-officedocument"
                                 ".spreadsheetml.sheet",
                            key="dl_fin"
                        )
                    else:
                        st.info("Sem dados financeiros para exportar.")
                except Exception as _e:
                    toast_erro(f"Erro: {_e}")

    with c4:
        if is_vet():
            st.markdown("##### 🩺 Veterinário")
            st.caption("Receituário, vacinas e ocorrências clínicas")
            if st.button("⬇️ Exportar veterinário",
                         key="btn_exp_vet", use_container_width=True):
                with st.spinner("Gerando..."):
                    try:
                        data = exportar_veterinario(_oid)
                        if data:
                            st.download_button(
                                "💾 veterinario.xlsx", data=data,
                                file_name="auroque_veterinario.xlsx",
                                mime="application/vnd.openxmlformats-"
                                     "officedocument.spreadsheetml.sheet",
                                key="dl_vet"
                            )
                    except Exception as _e:
                        toast_erro(f"Erro: {_e}")
