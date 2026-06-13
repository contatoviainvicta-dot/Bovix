# database.py -- Camada de persistencia (AGREGADOR)
# A fundacao (conexao, pool, _ph, _fetch, cache, planos) foi movida para db/core.py
# Este arquivo mantem migrations, schema e funcoes de dominio.
# Importacoes existentes (from database import ...) continuam funcionando.

import os
import hashlib
import secrets
from contextlib import contextmanager
from datetime import date as _date, timedelta as _td

# Importar toda a fundacao do core
from db.core import *
from db.core import (
    _usar_postgres, _diagnostico_banco, _get_pg_url, _date_add, _cast_date,
    _get_pool_lock, _get_pool, _fechar_pool, _conexao, _cached,
    _ph, _fetch, _fetchone,
    PLANOS_FAZENDEIRO, PLANOS_VETERINARIO,
    UPGRADE_MSG_FAZENDEIRO, UPGRADE_MSG_VETERINARIO,
)


# ── Schema e migrations (movidos para db/schema.py) ──────────────────────────
from db.schema import (
    _MIGRATIONS, _log_db, _log_err, _log_war,
    _criar_tabela_schema_version, _versoes_aplicadas, _registrar_versao,
    aplicar_migrations, _garantir_tabelas_vet,
    _garantir_colunas_vacinas_agenda, _garantir_coluna_crmv,
    inicializar_banco, _migrar_banco,
)

# ── Pesagens e GMD (movidos para db/pesagens.py) ─────────────────────────────
from db.pesagens import (
    adicionar_pesagem, listar_pesagens, atualizar_pesagem, excluir_pesagem,
    listar_pesagens_lote, calcular_gmd_temporal, listar_pesagens_todos_animais,
    calcular_gmds_lote, _gmd_animal, importar_pesagens_csv,
)

# ── Vendas (movidos para db/vendas.py) ───────────────────────────────────────
from db.vendas import (
    marcar_animal_vendido, registrar_receita_parcial, venda_parcial_lote,
    listar_vendas_lote, registrar_venda_lote, marcar_em_venda,
    cancelar_venda_lote, listar_lotes_historico, obter_resumo_venda_lote,
    listar_animais_vendidos_lote, listar_todas_vendas,
)

# ── Animais (movidos para db/animais.py) ─────────────────────────────────────
from db.animais import (
    STATUS_ANIMAL,
    listar_animais, listar_animais_por_lote, adicionar_animal, obter_animal,
    atualizar_animal, excluir_animal, atualizar_status_animal,
    listar_animais_por_status, contagem_status_animais, importar_animais_csv,
)

# ── Lotes (movidos para db/lotes.py) ─────────────────────────────────────────
from db.lotes import (
    adicionar_lote, listar_lotes, obter_lote, atualizar_lote, excluir_lote,
    resumo_lote, atualizar_status_lote, adicionar_custo_lote, listar_custos_lote,
    calcular_margem_lote, encerrar_lote, verificar_limite_fazendas,
)

# ── Usuarios (movidos para db/usuarios.py) ───────────────────────────────────
from db.usuarios import (
    TRIAL_DIAS,
    _hash_senha, _bcrypt_hash, _bcrypt_verify, _is_bcrypt_hash,
    email_valido, email_ja_cadastrado, auto_registrar_usuario, criar_usuario,
    obter_nome_usuario, autenticar_usuario, listar_usuarios, usuario_existe,
    alterar_senha, ativar_trial, obter_status_plano,
    listar_usuarios_trial_expirando, definir_plano_usuario, obter_limites_usuario,
    listar_fazendas_do_vet, aprovar_conta_usuario, adicionar_fazenda,
    listar_fazendas, registrar_auditoria, listar_auditoria,
    _garantir_tabela_login_tentativas, registrar_tentativa_login,
    verificar_bloqueio_login, limpar_tentativas_login, obter_crmv_usuario,
    atualizar_crmv, salvar_coords_fazenda, listar_coords_fazendas,
    buscar_usuario_por_email, obter_plano, atualizar_plano, enviar_email,
    enviar_email_boas_vindas, enviar_email_alerta_diario, is_primeiro_login,
)
# Reexportar _PLANOS (usado por admin_painel e crescimento)
from db.core import _PLANOS

# ── Veterinario (movidos para db/veterinario.py) ─────────────────────────────
from db.veterinario import (
    adicionar_ocorrencia, listar_ocorrencias, atualizar_ocorrencia,
    excluir_ocorrencia, listar_ocorrencias_em_tratamento, solicitar_acesso_vet,
    aprovar_acesso_vet, revogar_acesso_vet, listar_acessos_vet, listar_lotes_vet,
    adicionar_vacina_agenda, registrar_vacina_realizada, listar_vacinas_agenda,
    listar_vacinas_pendentes, adicionar_medicamento, listar_medicamentos,
    atualizar_estoque, registrar_uso_medicamento, listar_medicamentos_criticos,
    verificar_carencia, adicionar_piquete, listar_piquetes, alocar_lote_piquete,
    liberar_piquete, historico_piquete, listar_ocorrencias_todos_animais,
    calcular_risco_sanitario, criar_campanha, listar_campanhas,
    adicionar_lote_campanha, listar_lotes_campanha, registrar_vacinacao_campanha,
    sincronizar_campanha_executada, resumo_campanha, resumo_financeiro_vet,
    sincronizar_ocorrencias_receitas, adicionar_carencia, listar_carencias_ativas,
    listar_animais_em_carencia_fazendeiro, animal_em_carencia,
)

# ── Financeiro (movidos para db/financeiro.py) ───────────────────────────────
from db.financeiro import (
    calcular_score_saude, calcular_previsao_abate, salvar_cotacao,
    obter_ultima_cotacao, calcular_scores_lote, margem_bruta_lote,
    dashboard_financeiro_fazendeiro, dre_por_periodo, curva_resultado_mensal,
    listar_cotacoes,
)

# ── Admin (movidos para db/admin.py) ─────────────────────────────────────────
from db.admin import (
    admin_metricas_usuarios, admin_calcular_mrr, admin_adicionar_ajuste_mrr,
    admin_listar_usuarios, admin_historico_acessos, admin_registrar_erro,
    admin_listar_erros, admin_erros_email_log, admin_metricas_produto,
)

# ── Clinica veterinaria (movidos para db/clinica.py) ─────────────────────────
from db.clinica import (
    adicionar_exame, atualizar_exame, listar_exames, adicionar_monitoramento,
    registrar_evolucao, encerrar_monitoramento, listar_monitoramentos,
    monitoramentos_vencendo, lancar_honorario, listar_honorarios,
    listar_itens_honorario, registrar_pagamento_honorario, cancelar_honorario,
    listar_receitas, adicionar_receita, adicionar_protocolo, listar_protocolos,
    adicionar_item_protocolo, listar_itens_protocolo, aplicar_protocolo_no_lote,
    adicionar_visita, listar_visitas, atualizar_status_visita,
    adicionar_relatorio_visita, listar_relatorios,
)

# ── Insights / IA / KPIs (movidos para db/insights.py) ───────────────────────
from db.insights import (
    gerar_insights_lote, prever_abate, detectar_anomalias_peso,
    resumo_ia_fazenda, resumo_dashboard, kpis_executivos,
    painel_saude_rebanho, epidemiologia_por_fazenda,
)

# ── Onboarding / dados demo (movidos para db/onboarding.py) ──────────────────
from db.onboarding import (
    obter_progresso_onboarding, marcar_passo_onboarding, onboarding_completo,
    criar_dados_demo, _garantir_coluna_onboarding, marcar_onboarding_completo,
    onboarding_concluido, criar_dados_exemplo, remover_dados_exemplo,
    _PASSOS_ONBOARDING,
)

# ── LOTES ────────────────────────────────────────────────────────────────────
def buscar_animal_global(termo, owner_id):
    """Busca animal por identificacao ou nome em todos os lotes do owner."""
    if not termo or not owner_id:
        return []
    p = _ph()
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT a.id, a.identificacao, a.raca, a.sexo, "
                f"l.nome as lote_nome "
                f"FROM animais a "
                f"JOIN lotes l ON l.id = a.lote_id "
                f"WHERE l.owner_id = {p} "
                f"AND a.ativo = 1 "
                f"AND (LOWER(a.identificacao) LIKE LOWER({p}) "
                f"     OR LOWER(COALESCE(a.nome,'')) LIKE LOWER({p})) "
                f"ORDER BY a.identificacao "
                f"LIMIT 10",
                (owner_id, f"%{termo}%", f"%{termo}%")
            )
            rows = cur.fetchall()
        return [
            dict(id=r[0], identificacao=r[1],
                 raca=r[2], sexo=r[3], lote_nome=r[4])
            for r in rows
        ]
    except Exception as _e:
        _log_war.debug("buscar_animal_global: %s", _e)
        return []


def contar_animais_no_lote(lote_id, incluir_inativos=False):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if incluir_inativos:
            cur.execute(f"SELECT COUNT(*) FROM animais WHERE lote_id={p}", (lote_id,))
        else:
            cur.execute(f"SELECT COUNT(*) FROM animais WHERE lote_id={p} AND COALESCE(ativo,1)=1", (lote_id,))
        return cur.fetchone()[0]

def atualizar_animal_detalhes(animal_id, peso_alvo=None, observacoes=None, foto_path=None):
    p = _ph()
    campos, vals = [], []
    if peso_alvo   is not None: campos.append(f"peso_alvo={p}");   vals.append(peso_alvo)
    if observacoes is not None: campos.append(f"observacoes={p}"); vals.append(observacoes)
    if foto_path   is not None: campos.append(f"foto_path={p}");   vals.append(foto_path)
    if not campos: return
    vals.append(animal_id)
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE animais SET {', '.join(campos)} WHERE id={p}", vals)

@lambda _f: _cached(_f, ttl=30)
def listar_lotes_por_status(status=None, owner_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        base = (
            "SELECT id,nome,descricao,data_entrada,qtd_comprada,qtd_recebida,transporte,"
            "COALESCE(status,'ATIVO') as status FROM lotes WHERE 1=1"
        )
        params = []
        if owner_id is not None:
            base += f" AND owner_id={p}"
            params += [owner_id]
        if status:
            base += f" AND COALESCE(status,'ATIVO')={p}"
            params.append(status)
        base += " ORDER BY data_entrada DESC"
        cur.execute(base, params)
        rows = _fetch(cur)
        return [(r['id'],r['nome'],r['descricao'],r['data_entrada'],
                 r['qtd_comprada'],r['qtd_recebida'],r['transporte'],r['status']) for r in rows]


# ── OCORRENCIAS ──────────────────────────────────────────────────────────────
def listar_tratamentos_vencidos(owner_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        hoje = str(_date.today())
        filtro_owner = f" AND l.owner_id={p}" if owner_id is not None else ""
        params = (owner_id,) if owner_id is not None else ()
        cur.execute(
            "SELECT o.id,o.animal_id,a.identificacao,l.nome,o.data,o.tipo,o.descricao,o.gravidade,o.custo,o.dias_recuperacao,o.status"
            " FROM ocorrencias o JOIN animais a ON a.id=o.animal_id JOIN lotes l ON l.id=a.lote_id"
            f" WHERE o.status='Em tratamento' AND o.dias_recuperacao > 0{filtro_owner}",
            params,
        )
        rows = _fetch(cur)
        import datetime
        vencidos = []
        for r in rows:
            try:
                dt_oc = datetime.datetime.strptime(str(r["data"])[:10], "%Y-%m-%d").date()
                dt_alta = dt_oc + datetime.timedelta(days=int(r["dias_recuperacao"] or 0))
                if dt_alta < _date.today():
                    vencidos.append(tuple(r.values()))
            except Exception as _ew:
                _log_war.debug("excecao ignorada: %s", _ew)
        return vencidos


# ── USUARIOS ─────────────────────────────────────────────────────────────────
# ─── BCRYPT — novo sistema de hash ───────────────────────────────────────────
@lambda _f: _cached(_f, ttl=60)
def converter_para_pago(usuario_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE usuarios SET plano='pago',plano_expira=NULL WHERE id={p}", (usuario_id,))

# ── PLANOS E VETERINARIO ────────────────────────────────────────────────────

def verificar_limite_animais(owner_id, n_novos=0):
    """Verifica limite de animais. n_novos: quantos serão adicionados."""
    limites = obter_limites_usuario(owner_id)
    if not limites:
        return dict(ok=False, pode=False, atual=0, limite=0, disponiveis=0,
                    msg='Usuario nao encontrado', upgrade='')
    if limites['perfil'] == 'admin':
        return dict(ok=True, pode=True, atual=0, limite=99999, disponiveis=99999,
                    msg='Admin sem limite', upgrade='')
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT COUNT(*) FROM animais a JOIN lotes l ON l.id=a.lote_id"
            f" WHERE l.owner_id={p} AND COALESCE(a.ativo,1)=1",
            (owner_id,),
        )
        atual = cur.fetchone()[0]
    limite    = limites['limite_animais']
    disponiv  = max(0, limite - atual)
    pode      = (atual + n_novos) <= limite
    plano_k   = limites.get('plano_nome', 'trial')
    upgrade   = UPGRADE_MSG_FAZENDEIRO.get(plano_k, '')
    if pode:
        msg = f'{atual}/{limite} animais ({disponiv} disponiveis)'
    else:
        msg = (f'Limite atingido: {atual}/{limite} animais. '
               f'Voce tentou adicionar {n_novos} mas so ha {disponiv} vagas. {upgrade}')
    return dict(ok=pode, pode=pode, atual=atual, limite=limite,
                disponiveis=disponiv, msg=msg, upgrade=upgrade)

# ── Acesso veterinario-fazenda ───────────────────────────────────────────────

def listar_solicitacoes_pendentes():
    return listar_acessos_vet(status='pendente')

# ── FAZENDAS ──────────────────────────────────────────────────────────────────
# ── VACINAS ───────────────────────────────────────────────────────────────────
# ── REPRODUCAO ────────────────────────────────────────────────────────────────
def adicionar_reproducao(animal_id, tipo_cobertura, data_cio=None, data_diagnostico=None, resultado="pendente", data_parto_previsto=None, observacao=""):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(f"INSERT INTO reproducao (animal_id,data_cio,tipo_cobertura,data_diagnostico,resultado,data_parto_previsto,observacao) VALUES({p},{p},{p},{p},{p},{p},{p}) RETURNING id", (animal_id, data_cio, tipo_cobertura, data_diagnostico, resultado, data_parto_previsto, observacao))
            return cur.fetchone()[0]
        else:
            cur.execute(f"INSERT INTO reproducao (animal_id,data_cio,tipo_cobertura,data_diagnostico,resultado,data_parto_previsto,observacao) VALUES({p},{p},{p},{p},{p},{p},{p})", (animal_id, data_cio, tipo_cobertura, data_diagnostico, resultado, data_parto_previsto, observacao))
            return cur.lastrowid

def atualizar_reproducao(repro_id, resultado, data_parto_real=None, data_diagnostico=None, data_parto_previsto=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE reproducao SET resultado={p},data_parto_real=COALESCE({p},data_parto_real),data_diagnostico=COALESCE({p},data_diagnostico),data_parto_previsto=COALESCE({p},data_parto_previsto) WHERE id={p}",
            (resultado, data_parto_real, data_diagnostico, data_parto_previsto, repro_id),
        )

def listar_reproducao(animal_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT id,animal_id,data_cio,tipo_cobertura,data_diagnostico,resultado,data_parto_previsto,data_parto_real,observacao FROM reproducao WHERE animal_id={p} ORDER BY data_cio DESC", (animal_id,))
        rows = _fetch(cur)
        return [(r["id"],r["animal_id"],r["data_cio"],r["tipo_cobertura"],r["data_diagnostico"],r["resultado"],r["data_parto_previsto"],r["data_parto_real"],r["observacao"]) for r in rows]

def listar_partos_previstos(owner_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        filtro_owner = f" AND l.owner_id={p}" if owner_id is not None else ""
        params = (owner_id,) if owner_id is not None else ()
        cur.execute(
            f"SELECT r.id,a.identificacao,l.nome,r.data_parto_previsto,r.tipo_cobertura"
            f" FROM reproducao r JOIN animais a ON a.id=r.animal_id JOIN lotes l ON l.id=a.lote_id"
            f" WHERE r.resultado='positivo' AND r.data_parto_real IS NULL"
            f" AND {_cast_date('r.data_parto_previsto')}<={_date_add(30)}{filtro_owner}"
            f" ORDER BY r.data_parto_previsto",
            params,
        )
        rows = _fetch(cur)
        return [(r["id"],r["identificacao"],r["nome"],r["data_parto_previsto"],r["tipo_cobertura"]) for r in rows]

def taxa_prenhez_lote(lote_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(DISTINCT r.animal_id) FROM reproducao r JOIN animais a ON a.id=r.animal_id WHERE a.lote_id={p}", (lote_id,))
        total = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(DISTINCT r.animal_id) FROM reproducao r JOIN animais a ON a.id=r.animal_id WHERE a.lote_id={p} AND r.resultado='positivo'", (lote_id,))
        positivas = cur.fetchone()[0]
    return dict(total=total, positivas=positivas, taxa=(positivas/total*100) if total > 0 else 0)


# ── PIQUETES ──────────────────────────────────────────────────────────────────
# ── MORTALIDADE ───────────────────────────────────────────────────────────────
def registrar_morte(animal_id, data, causa, descricao="", custo_perda=0.0):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT lote_id FROM animais WHERE id={p}", (animal_id,))
        r = cur.fetchone()
        lote_id = r[0] if r else None
        cur.execute(f"UPDATE animais SET ativo=0 WHERE id={p}", (animal_id,))
        if _usar_postgres():
            cur.execute(f"INSERT INTO mortalidade (animal_id,data,causa,descricao,custo_perda) VALUES({p},{p},{p},{p},{p}) RETURNING id", (animal_id, data, causa, descricao, custo_perda))
            mid = cur.fetchone()[0]
        else:
            cur.execute(f"INSERT INTO mortalidade (animal_id,data,causa,descricao,custo_perda) VALUES({p},{p},{p},{p},{p})", (animal_id, data, causa, descricao, custo_perda))
            mid = cur.lastrowid
    if lote_id:
        atualizar_qtd_lote(lote_id)
    return mid

def listar_mortalidade(lote_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if lote_id:
            cur.execute(f"SELECT m.id,m.animal_id,a.identificacao,m.data,m.causa,m.descricao,m.custo_perda FROM mortalidade m JOIN animais a ON a.id=m.animal_id WHERE a.lote_id={p} ORDER BY m.data DESC", (lote_id,))
        else:
            cur.execute("SELECT m.id,m.animal_id,a.identificacao,m.data,m.causa,m.descricao,m.custo_perda FROM mortalidade m JOIN animais a ON a.id=m.animal_id ORDER BY m.data DESC")
        rows = _fetch(cur)
        return [(r["id"],r["animal_id"],r["identificacao"],r["data"],r["causa"],r["descricao"],r["custo_perda"]) for r in rows]

def taxa_mortalidade_lote(lote_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM animais WHERE lote_id={p}", (lote_id,))
        total = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM mortalidade m JOIN animais a ON a.id=m.animal_id WHERE a.lote_id={p}", (lote_id,))
        mortos = cur.fetchone()[0]
    return dict(total=total, mortos=mortos, taxa=round((mortos/total*100) if total > 0 else 0, 2))


# ── AUDITORIA ─────────────────────────────────────────────────────────────────
# ── GTA / SISBOV ──────────────────────────────────────────────────────────────
def registrar_gta(lote_id, numero_gta, data_emissao, origem, destino, quantidade, finalidade="Abate", observacao=""):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(f"INSERT INTO gta (lote_id,numero_gta,data_emissao,origem,destino,quantidade,finalidade,observacao) VALUES({p},{p},{p},{p},{p},{p},{p},{p}) RETURNING id", (lote_id, numero_gta, data_emissao, origem, destino, quantidade, finalidade, observacao))
            gta_id = cur.fetchone()[0]
        else:
            cur.execute(f"INSERT INTO gta (lote_id,numero_gta,data_emissao,origem,destino,quantidade,finalidade,observacao) VALUES({p},{p},{p},{p},{p},{p},{p},{p})", (lote_id, numero_gta, data_emissao, origem, destino, quantidade, finalidade, observacao))
            gta_id = cur.lastrowid
        if finalidade in ("Abate", "Venda"):
            cur.execute(f"SELECT id FROM animais WHERE lote_id={p} AND COALESCE(ativo,1)=1 ORDER BY id DESC LIMIT {p}", (lote_id, quantidade))
            rows = cur.fetchall()
            for row in rows:
                aid = row[0] if _usar_postgres() else row[0]
                cur.execute(f"UPDATE animais SET ativo=0 WHERE id={p}", (aid,))
    atualizar_qtd_lote(lote_id)
    return gta_id

def listar_gta(lote_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if lote_id:
            cur.execute(f"SELECT g.id,g.lote_id,l.nome,g.numero_gta,g.data_emissao,g.origem,g.destino,g.quantidade,g.finalidade,g.observacao FROM gta g JOIN lotes l ON l.id=g.lote_id WHERE g.lote_id={p} ORDER BY g.data_emissao DESC", (lote_id,))
        else:
            cur.execute("SELECT g.id,g.lote_id,l.nome,g.numero_gta,g.data_emissao,g.origem,g.destino,g.quantidade,g.finalidade,g.observacao FROM gta g JOIN lotes l ON l.id=g.lote_id ORDER BY g.data_emissao DESC")
        rows = _fetch(cur)
        return [(r["id"],r["lote_id"],r["nome"],r["numero_gta"],r["data_emissao"],r["origem"],r["destino"],r["quantidade"],r["finalidade"],r["observacao"]) for r in rows]

def registrar_sisbov(animal_id, numero_sisbov, data_certificacao):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(f"INSERT INTO sisbov (animal_id,numero_sisbov,data_certificacao) VALUES({p},{p},{p}) ON CONFLICT (animal_id) DO UPDATE SET numero_sisbov=EXCLUDED.numero_sisbov,data_certificacao=EXCLUDED.data_certificacao RETURNING id", (animal_id, numero_sisbov, data_certificacao))
            return cur.fetchone()[0]
        else:
            cur.execute(f"INSERT OR REPLACE INTO sisbov (animal_id,numero_sisbov,data_certificacao) VALUES({p},{p},{p})", (animal_id, numero_sisbov, data_certificacao))
            return cur.lastrowid

def obter_sisbov(animal_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT id,animal_id,numero_sisbov,data_certificacao FROM sisbov WHERE animal_id={p}", (animal_id,))
        r = _fetchone(cur)
        return (r["id"],r["animal_id"],r["numero_sisbov"],r["data_certificacao"]) if r else None


# ── SCORE DE SAUDE ────────────────────────────────────────────────────────────
# ── PREVISAO DE ABATE ─────────────────────────────────────────────────────────
# ── VENDAS / MARGEM ───────────────────────────────────────────────────────────
def lote_ja_vendido(lote_id):
    """Verifica se lote ja foi vendido (sem animais ativos)."""
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        try:
            cur.execute(f"SELECT COUNT(*) FROM animais WHERE lote_id={p} AND ativo=1",(lote_id,))
            ativos = cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM animais WHERE lote_id={p}",(lote_id,))
            total = cur.fetchone()[0]
            return total > 0 and ativos == 0
        except Exception:
            _log_war.debug('excecao tratada: %s', exc_info=True)
            return False


# ── CICLO DE VIDA: VENDA E ENCERRAMENTO ──────────────────────
def listar_animais_por_lote_status(lote_id, status=None):
    """Lista animais do lote filtrado por status (None=todos, VENDIDO, ATIVO)."""
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if status == 'VENDIDO':
            cur.execute(
                f"SELECT id,identificacao,raca,sexo,idade,peso_entrada,"
                f"peso_alvo,status,ativo FROM animais "
                f"WHERE lote_id={p} AND status='VENDIDO' ORDER BY identificacao",
                (lote_id,)
            )
        elif status == 'ATIVO':
            cur.execute(
                f"SELECT id,identificacao,raca,sexo,idade,peso_entrada,"
                f"peso_alvo,status,ativo FROM animais "
                f"WHERE lote_id={p} AND ativo=1 AND status!='VENDIDO' "
                f"ORDER BY identificacao",
                (lote_id,)
            )
        else:
            cur.execute(
                f"SELECT id,identificacao,raca,sexo,idade,peso_entrada,"
                f"peso_alvo,status,ativo FROM animais "
                f"WHERE lote_id={p} ORDER BY identificacao",
                (lote_id,)
            )
        return cur.fetchall()




# ── COTACOES ──────────────────────────────────────────────────────────────────
# ── GMD TEMPORAL ──────────────────────────────────────────────────────────────
# ── CICLO DE VIDA DO LOTE ─────────────────────────────────────────────────────

# ── IMPORTACAO CSV ─────────────────────────────────────────────────────────────


# ── CONSISTENCIA DE LOTE ──────────────────────────────────────────────────────
def atualizar_qtd_lote(lote_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM animais WHERE lote_id={p} AND COALESCE(ativo,1)=1", (lote_id,))
        n = cur.fetchone()[0]
        cur.execute(f"UPDATE lotes SET qtd_recebida={p} WHERE id={p}", (n, lote_id))
    return n

def transferir_animal(animal_id, lote_destino_id, motivo='', usuario_id=None):
    p = _ph()
    from datetime import date as _d
    with _conexao() as conn:
        cur = conn.cursor()
        # Buscar lote atual
        cur.execute(f"SELECT lote_id FROM animais WHERE id={p}", (animal_id,))
        r = cur.fetchone()
        if not r:
            return dict(ok=False, msg='Animal nao encontrado')
        lote_origem_id = r[0]
        if lote_origem_id == lote_destino_id:
            return dict(ok=False, msg='Animal ja esta neste lote')
        # Mover o animal
        cur.execute(
            f"UPDATE animais SET lote_id={p}, status='ATIVO', ativo=1 WHERE id={p}",
            (lote_destino_id, animal_id),
        )
        # Registrar movimentacao
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO movimentacoes_animais (animal_id,lote_origem,lote_destino,data,motivo,usuario_id)"
                f" VALUES({p},{p},{p},{p},{p},{p}) RETURNING id",
                (animal_id, lote_origem_id, lote_destino_id, str(_d.today()), motivo, usuario_id),
            )
        else:
            cur.execute(
                f"INSERT INTO movimentacoes_animais (animal_id,lote_origem,lote_destino,data,motivo,usuario_id)"
                f" VALUES({p},{p},{p},{p},{p},{p})",
                (animal_id, lote_origem_id, lote_destino_id, str(_d.today()), motivo, usuario_id),
            )
        conn.commit()
    # Atualizar contagens de ambos os lotes
    atualizar_qtd_lote(lote_origem_id)
    atualizar_qtd_lote(lote_destino_id)
    return dict(ok=True, msg='Animal transferido com sucesso',
                lote_origem=lote_origem_id, lote_destino=lote_destino_id)

def listar_movimentacoes(animal_id=None, lote_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if animal_id:
            cur.execute(
                f"SELECT m.id,m.animal_id,a.identificacao,"
                f"lo.nome as lote_origem,ld.nome as lote_destino,m.data,m.motivo"
                f" FROM movimentacoes_animais m"
                f" JOIN animais a ON a.id=m.animal_id"
                f" JOIN lotes lo ON lo.id=m.lote_origem"
                f" JOIN lotes ld ON ld.id=m.lote_destino"
                f" WHERE m.animal_id={p} ORDER BY m.data DESC",
                (animal_id,),
            )
        elif lote_id:
            cur.execute(
                f"SELECT m.id,m.animal_id,a.identificacao,"
                f"lo.nome as lote_origem,ld.nome as lote_destino,m.data,m.motivo"
                f" FROM movimentacoes_animais m"
                f" JOIN animais a ON a.id=m.animal_id"
                f" JOIN lotes lo ON lo.id=m.lote_origem"
                f" JOIN lotes ld ON ld.id=m.lote_destino"
                f" WHERE m.lote_origem={p} OR m.lote_destino={p} ORDER BY m.data DESC",
                (lote_id, lote_id),
            )
        else:
            cur.execute(
                "SELECT m.id,m.animal_id,a.identificacao,"
                "lo.nome as lote_origem,ld.nome as lote_destino,m.data,m.motivo"
                " FROM movimentacoes_animais m"
                " JOIN animais a ON a.id=m.animal_id"
                " JOIN lotes lo ON lo.id=m.lote_origem"
                " JOIN lotes ld ON ld.id=m.lote_destino"
                " ORDER BY m.data DESC LIMIT 100"
            )
        rows = _fetch(cur)
        return [(r['id'],r['animal_id'],r['identificacao'],
                 r['lote_origem'],r['lote_destino'],r['data'],r['motivo']) for r in rows]


# ── QUERIES AGREGADAS (elimina N+1) ─────────────────────────────────────────

# ── IA E PREDICAO ────────────────────────────────────────────────────────────

def _garantir_status_animal_lote():
    """Garante coluna status em animais e lotes."""
    with _conexao() as conn:
        cur = conn.cursor()
        try:
            if _usar_postgres():
                cur.execute("ALTER TABLE animais ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'ATIVO'")
                cur.execute("ALTER TABLE lotes ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'Ativo'")
            else:
                for tbl, col in [('animais','status'),('lotes','status')]:
                    cur.execute(f"PRAGMA table_info({tbl})")
                    cols = [r[1] for r in cur.fetchall()]
                    if col not in cols:
                        cur.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} TEXT DEFAULT 'Ativo'")
            conn.commit()
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)
# MODULO VETERINARIO - Funcoes CRUD
# ============================================================

# ── RECEITUARIO DIGITAL ───────────────────────────────────────
# ── EXAMES LABORATORIAIS ─────────────────────────────────────
# ── MONITORAMENTO POS-TRATAMENTO ──────────────────────────────
# ── HONORARIOS VETERINARIOS ──────────────────────────────────
# ── MENSAGENS VET-FAZENDEIRO ─────────────────────────────────
def enviar_mensagem(remetente_id, destinatario_id, corpo,
                   assunto="", tipo="mensagem"):
    """Envia mensagem interna entre vet e fazendeiro."""
    _garantir_tabelas_vet()
    from datetime import date
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO mensagens_vet "
                f"(remetente_id,destinatario_id,assunto,corpo,"
                f"lida,criado_em,tipo) "
                f"VALUES({p},{p},{p},{p},0,{p},{p}) RETURNING id",
                (remetente_id, destinatario_id, assunto or "",
                 corpo, str(date.today()), tipo)
            )
            return cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO mensagens_vet "
                f"(remetente_id,destinatario_id,assunto,corpo,"
                f"lida,criado_em,tipo) "
                f"VALUES({p},{p},{p},{p},0,{p},{p})",
                (remetente_id, destinatario_id, assunto or "",
                 corpo, str(date.today()), tipo)
            )
            return cur.lastrowid


def listar_mensagens(user_id, caixa="entrada"):
    """Lista mensagens do usuario. caixa='entrada' ou 'enviadas'."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if caixa == "entrada":
            cur.execute(
                f"SELECT id,remetente_id,destinatario_id,assunto,"
                f"corpo,lida,criado_em,tipo "
                f"FROM mensagens_vet WHERE destinatario_id={p} "
                f"ORDER BY criado_em DESC",
                (user_id,)
            )
        else:
            cur.execute(
                f"SELECT id,remetente_id,destinatario_id,assunto,"
                f"corpo,lida,criado_em,tipo "
                f"FROM mensagens_vet WHERE remetente_id={p} "
                f"ORDER BY criado_em DESC",
                (user_id,)
            )
        return cur.fetchall()


def marcar_mensagem_lida(mensagem_id):
    """Marca mensagem como lida."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE mensagens_vet SET lida=1 WHERE id={p}",
            (mensagem_id,)
        )
        conn.commit()


def contar_mensagens_nao_lidas(user_id):
    """Retorna numero de mensagens nao lidas."""
    _garantir_tabelas_vet()
    p = _ph()
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT COUNT(*) FROM mensagens_vet "
                f"WHERE destinatario_id={p} AND lida=0",
                (user_id,)
            )
            return cur.fetchone()[0]
    except Exception:
        _log_war.debug('excecao tratada: %s', exc_info=True)
        return 0


# ── CAMPANHAS DE VACINACAO ────────────────────────────────────
# ── COORDENADAS DE FAZENDAS ───────────────────────────────────
# ── DADOS EPIDEMIOLOGICOS ──────────────────────────────────────
# ── HISTORICO CLINICO PDF ──────────────────────────────────────
def historico_clinico_animal(animal_id):
    """Retorna historico completo do animal para PDF."""
    p = _ph()
    dados = {}

    # Dados basicos
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT a.identificacao,a.raca,a.sexo,a.idade,"
                f"a.peso_entrada,a.peso_alvo,l.nome "
                f"FROM animais a JOIN lotes l ON l.id=a.lote_id "
                f"WHERE a.id={p}",
                (animal_id,)
            )
            r = cur.fetchone()
            if r:
                dados["animal"] = {
                    "brinco": r[0], "raca": r[1], "sexo": r[2],
                    "idade": r[3], "peso_entrada": r[4],
                    "peso_alvo": r[5], "lote": r[6]
                }
    except Exception:
        dados["animal"] = {}

    # Pesagens
    dados["pesagens"] = listar_pesagens(animal_id) or []

    # Ocorrencias
    dados["ocorrencias"] = listar_ocorrencias(animal_id) or []

    # Exames
    try:
        dados["exames"] = listar_exames(animal_id=animal_id) or []
    except Exception:
        dados["exames"] = []

    # Carencia ativa
    try:
        dados["carencia"] = animal_em_carencia(animal_id) or []
    except Exception:
        dados["carencia"] = []

    return dados


# ── PLANOS E LIMITES ─────────────────────────────────────────

# ═══════════════════════════════════════════════════════════════════════════
# DASHBOARD FINANCEIRO DO FAZENDEIRO
# ═══════════════════════════════════════════════════════════════════════════

@lambda _f: _cached(_f, ttl=120)
@lambda _f: _cached(_f, ttl=300)
def calendario_abate(owner_id):
    """Previsão de abate para todos os lotes ativos do fazendeiro."""
    from datetime import date, timedelta
    lotes = listar_lotes(owner_id=owner_id)
    resultado = []

    for l in lotes:
        lote_id = l[0]
        animais = listar_animais_por_lote(lote_id)
        if not animais:
            continue

        datas_prev   = []
        pesos_atuais = []

        for a in animais:
            peso_alvo = float(a[7] or 450) if len(a) > 7 else 450
            pes = listar_pesagens(a[0])
            if not pes:
                continue

            peso_ult = float(pes[-1][2])
            pesos_atuais.append(peso_ult)

            if len(pes) >= 2:
                gmd = _gmd_animal(pes)
                if gmd > 0:
                    kg_faltam = max(0, peso_alvo - peso_ult)
                    dias      = int(kg_faltam / gmd)
                    data_prev = date.today() + timedelta(days=dias)
                    datas_prev.append(data_prev)
            elif pes:
                pesos_atuais.append(peso_ult)

        if not datas_prev:
            continue

        data_media   = date.fromordinal(
            int(sum(d.toordinal() for d in datas_prev) / len(datas_prev))
        )
        peso_medio   = round(sum(pesos_atuais) / max(len(pesos_atuais), 1), 1)
        dias_restant = (data_media - date.today()).days

        try:
            cotacao = obter_cotacao_boi_gordo() or 15.0
        except Exception:
            cotacao = 15.0

        # Receita projetada no abate
        peso_alvo_medio = 450
        if animais:
            alvos = [float(a[7] or 450) for a in animais if len(a) > 7]
            if alvos:
                peso_alvo_medio = sum(alvos) / len(alvos)

        receita_proj = (peso_alvo_medio / 15) * cotacao * len(animais)

        resultado.append({
            "lote_id":       lote_id,
            "nome":          l[1],
            "n_animais":     len(animais),
            "peso_atual":    peso_medio,
            "peso_alvo":     round(peso_alvo_medio, 1),
            "data_abate":    str(data_media),
            "dias_restantes":dias_restant,
            "receita_proj":  receita_proj,
            "cotacao":       cotacao,
        })

    return sorted(resultado, key=lambda x: x["data_abate"])


# ── VENDAS DE LOTE ───────────────────────────────────────────




# ── DRE POR PERÍODO ───────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════
# PAINEL ADMIN — MRR, USUARIOS, CHURN, ERROS
# ═══════════════════════════════════════════════════════════════════════════

@lambda _f: _cached(_f, ttl=300)
def _fmt_dt(d):
    """Formata data para exibição: 12 jan 2025"""
    try:
        if not d or str(d) in ("None","","nan"): return "—"
        s = str(d)[:10]
        ano,mes,dia = int(s[:4]),int(s[5:7]),int(s[8:10])
        return f"{dia:02d} {_MESES_ABR_DB[mes]} {ano}"
    except Exception:
        return str(d)[:10] if d else "—"


def _brl(v):
    """Formata valor em BRL: R$ 1.250,00"""
    try:
        v = float(v)
        neg = v < 0
        inteiro = int(abs(v))
        centavos = round((abs(v) - inteiro) * 100)
        s_int = f"{inteiro:,}".replace(",", ".")
        s = f"R$ {s_int},{centavos:02d}"
        return f"-{s}" if neg else s
    except Exception:
        return "R$ 0,00"


# ── ONBOARDING ────────────────────────────────────────────────


# ── IMPORTACAO CSV ────────────────────────────────────────────


# ── PROTOCOLOS SANITARIOS ─────────────────────────────────────
# ── VISITAS TECNICAS ──────────────────────────────────────────
# ── RELATORIOS DE VISITA ──────────────────────────────────────
# ── CARENCIA ──────────────────────────────────────────────────
# ── PAINEL DE SAUDE DO REBANHO ────────────────────────────────
def _garantir_owner_id_medicamentos():
    """Garante que a tabela medicamentos tem coluna owner_id."""
    with _conexao() as conn:
        cur = conn.cursor()
        try:
            if _usar_postgres():
                cur.execute(
                    "ALTER TABLE medicamentos ADD COLUMN IF NOT EXISTS owner_id INTEGER"
                )
            else:
                cur.execute("PRAGMA table_info(medicamentos)")
                cols = [r[1] for r in cur.fetchall()]
                if 'owner_id' not in cols:
                    cur.execute("ALTER TABLE medicamentos ADD COLUMN owner_id INTEGER")
            conn.commit()
            return True
        except Exception:
            _log_war.debug('excecao tratada: %s', exc_info=True)
            return False


def sincronizar_todos_lotes():
    lotes = listar_lotes()
    resultados = []
    for l in lotes:
        n = atualizar_qtd_lote(l[0])
        resultados.append((l[0], l[1], n))
    return resultados
