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


def gerar_insights_lote(lote_id):
    import pandas as pd
    from datetime import date as _d
    insights = []
    animais = listar_animais_por_lote(lote_id)
    if not animais:
        return insights

    # 1. Queda de GMD
    gmds = []
    for a in animais:
        ps = listar_pesagens(a[0])
        if len(ps) >= 2:
            df = pd.DataFrame(ps, columns=['id','aid','peso','data'] + (['ident'] if ps and len(ps[0]) > 4 else []))
            df['data'] = pd.to_datetime(df['data'])
            df = df.sort_values('data')
            dias = (df['data'].iloc[-1] - df['data'].iloc[0]).days
            if dias > 0:
                g = (df['peso'].iloc[-1] - df['peso'].iloc[0]) / dias
                gmds.append(g)
    if gmds:
        gmd_medio = sum(gmds) / len(gmds)
        if gmd_medio < 0:
            insights.append(dict(tipo='critico', titulo='GMD negativo',
                descricao=f'Media do lote: {gmd_medio:.3f} kg/dia. Animais perdendo peso.',
                acao='Revisar alimentacao e saude do lote'))
        elif gmd_medio < 0.5:
            insights.append(dict(tipo='aviso', titulo='GMD abaixo do esperado',
                descricao=f'Media do lote: {gmd_medio:.3f} kg/dia. Esperado acima de 0.8.',
                acao='Avaliar dieta e condicao sanitaria'))

    # 2. Mortalidade elevada
    from database import taxa_mortalidade_lote
    mort = taxa_mortalidade_lote(lote_id)
    if mort['taxa'] >= 5:
        insights.append(dict(tipo='critico', titulo='Mortalidade elevada',
            descricao=f'{mort["mortos"]} mortes ({mort["taxa"]}% do lote).',
            acao='Investigar causa e acionar veterinario'))
    elif mort['taxa'] >= 2:
        insights.append(dict(tipo='aviso', titulo='Mortalidade acima do normal',
            descricao=f'{mort["mortos"]} mortes ({mort["taxa"]}% do lote).',
            acao='Monitorar de perto'))

    # 3. Vacinas atrasadas
    from database import listar_vacinas_agenda
    vacs = listar_vacinas_agenda(lote_id)
    atrasadas = [v for v in vacs if v[5] == 'pendente' and str(v[3]) < str(_d.today())]
    if len(atrasadas) >= 3:
        insights.append(dict(tipo='critico', titulo='Vacinas muito atrasadas',
            descricao=f'{len(atrasadas)} vacinas pendentes em atraso.',
            acao='Agendar vacinacao urgente'))
    elif len(atrasadas) > 0:
        insights.append(dict(tipo='aviso', titulo='Vacinas em atraso',
            descricao=f'{len(atrasadas)} vacina(s) pendente(s) atrasada(s).',
            acao='Verificar calendario sanitario'))

    # 4. Custo sanitario elevado
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT COALESCE(SUM(o.custo),0) FROM ocorrencias o"
            f" JOIN animais a ON a.id=o.animal_id WHERE a.lote_id={p}",
            (lote_id,),
        )
        custo_san = float(cur.fetchone()[0] or 0)
    rs = resumo_lote(lote_id)
    if rs['ativos'] > 0:
        custo_por_animal = custo_san / rs['ativos']
        if custo_por_animal > 500:
            insights.append(dict(tipo='critico', titulo='Custo sanitario muito alto',
                descricao=f'R$ {custo_por_animal:.0f}/animal. Total: R$ {custo_san:.0f}.',
                acao='Revisar protocolo sanitario'))
        elif custo_por_animal > 200:
            insights.append(dict(tipo='aviso', titulo='Custo sanitario elevado',
                descricao=f'R$ {custo_por_animal:.0f}/animal. Total: R$ {custo_san:.0f}.',
                acao='Monitorar gastos com saude'))

    # 5. Animais sem pesagem
    sem_pesagem = sum(1 for a in animais if len(listar_pesagens(a[0])) == 0)
    if sem_pesagem > 0:
        insights.append(dict(tipo='info', titulo='Animais sem pesagem',
            descricao=f'{sem_pesagem} animal(is) sem nenhuma pesagem registrada.',
            acao='Registrar pesagem inicial'))

    # 6. Lote saudavel
    if not insights:
        insights.append(dict(tipo='positivo', titulo='Lote saudavel',
            descricao='Nenhum alerta identificado. Continue monitorando.',
            acao=None))

    return insights


# ── QUERIES AGREGADAS (elimina N+1) ─────────────────────────────────────────

def resumo_dashboard(owner_id=None):
    # KPIs do Home filtrados por owner_id
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if owner_id is not None:
            cur.execute(f"SELECT COUNT(*) FROM lotes WHERE owner_id={p}", (owner_id,))
        else:
            cur.execute("SELECT COUNT(*) FROM lotes")
        n_lotes = cur.fetchone()[0]

        if owner_id is not None:
            cur.execute(
                f"SELECT COUNT(*) FROM animais a JOIN lotes l ON l.id=a.lote_id"
                f" WHERE l.owner_id={p} AND COALESCE(a.ativo,1)=1",
                (owner_id,),
            )
        else:
            cur.execute("SELECT COUNT(*) FROM animais WHERE COALESCE(ativo,1)=1")
        n_animais = cur.fetchone()[0]

        if owner_id is not None:
            cur.execute(
                f"SELECT COUNT(*) FROM mortalidade m JOIN animais a ON a.id=m.animal_id"
                f" JOIN lotes l ON l.id=a.lote_id WHERE l.owner_id={p}",
                (owner_id,),
            )
        else:
            cur.execute("SELECT COUNT(*) FROM mortalidade")
        n_mortes = cur.fetchone()[0]

        if owner_id is not None:
            cur.execute(
                f"SELECT COUNT(*) FROM vacinas_agenda v"
                f" WHERE v.lote_id IN (SELECT id FROM lotes WHERE owner_id={p})"
                f" AND v.status='pendente'",
                (owner_id,),
            )
        else:
            cur.execute("SELECT COUNT(*) FROM vacinas_agenda WHERE status='pendente'")
        n_vac = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM medicamentos WHERE estoque_atual<=estoque_minimo")
        n_meds = cur.fetchone()[0]

    return dict(lotes=n_lotes, animais=n_animais, mortes=n_mortes,
                vacinas_pendentes=n_vac, meds_criticos=n_meds)

# ── IA E PREDICAO ────────────────────────────────────────────────────────────

def prever_abate(lote_id, peso_alvo_kg=450.0, preco_kg=10.0, custo_diario=12.0):
    """
    Prevê data e resultado financeiro do abate para cada animal do lote.
    Retorna lista de dicts por animal com previsao.
    """
    import pandas as pd
    from datetime import date as _d, timedelta as _td

    animais = listar_animais_por_lote(lote_id)
    if not animais:
        return []

    pes_todos = listar_pesagens_todos_animais(lote_id)
    pes_map = {}
    for p in pes_todos:
        pes_map.setdefault(p[1], []).append(p)

    resultado = []
    hoje = _d.today()

    for a in animais:
        aid, ident = a[0], a[1]
        ps = sorted(pes_map.get(aid, []), key=lambda x: x[3])

        if len(ps) < 2:
            resultado.append(dict(
                animal_id=aid, identificacao=ident,
                peso_atual=ps[0][2] if ps else None,
                gmd=None, dias_restantes=None,
                data_prevista=None, receita_prevista=None,
                custo_estimado=None, margem_estimada=None,
                status='Sem dados suficientes'
            ))
            continue

        df = pd.DataFrame(ps, columns=['id','aid','peso','data'] + (['ident'] if ps and len(ps[0]) > 4 else []))
        df['data'] = pd.to_datetime(df['data'])
        df = df.sort_values('data')
        dias_total = (df['data'].iloc[-1] - df['data'].iloc[0]).days
        peso_atual = float(df['peso'].iloc[-1])

        if dias_total <= 0:
            gmd = 0.0
        else:
            gmd = (peso_atual - float(df['peso'].iloc[0])) / dias_total

        if gmd <= 0:
            resultado.append(dict(
                animal_id=aid, identificacao=ident,
                peso_atual=peso_atual, gmd=round(gmd, 3),
                dias_restantes=None, data_prevista=None,
                receita_prevista=None, custo_estimado=None,
                margem_estimada=None, status='GMD negativo'
            ))
            continue

        kg_faltando = max(0, peso_alvo_kg - peso_atual)
        dias_rest = int(kg_faltando / gmd) if gmd > 0 else 9999
        data_prev = hoje + _td(days=dias_rest)
        receita = peso_alvo_kg * preco_kg
        custo = custo_diario * dias_rest
        margem = receita - custo

        if dias_rest == 0:
            status = 'Pronto para abate'
        elif dias_rest <= 30:
            status = 'Proximo do abate'
        elif dias_rest <= 90:
            status = 'Em engorda'
        else:
            status = 'Inicio de engorda'

        resultado.append(dict(
            animal_id=aid, identificacao=ident,
            peso_atual=round(peso_atual, 1), gmd=round(gmd, 3),
            dias_restantes=dias_rest,
            data_prevista=str(data_prev),
            receita_prevista=round(receita, 2),
            custo_estimado=round(custo, 2),
            margem_estimada=round(margem, 2),
            status=status
        ))

    return sorted(resultado, key=lambda x: x['dias_restantes'] or 9999)


def detectar_anomalias_peso(lote_id):
    """
    Detecta animais com comportamento anormal de peso.
    Retorna lista de alertas com animal e descricao.
    """
    import pandas as pd

    alertas = []
    pes_todos = listar_pesagens_todos_animais(lote_id)
    animais = listar_animais_por_lote(lote_id)
    nomes = {a[0]: a[1] for a in animais}

    pes_map = {}
    for p in pes_todos:
        pes_map.setdefault(p[1], []).append(p)

    gmds_todos = []
    for aid, ps in pes_map.items():
        if len(ps) >= 2:
            df = pd.DataFrame(ps, columns=['id','aid','peso','data'] + (['ident'] if ps and len(ps[0]) > 4 else []))
            df['data'] = pd.to_datetime(df['data'])
            df = df.sort_values('data')
            dias = (df['data'].iloc[-1] - df['data'].iloc[0]).days
            if dias > 0:
                gmd = (df['peso'].iloc[-1] - df['peso'].iloc[0]) / dias
                gmds_todos.append(gmd)

    if not gmds_todos:
        return []

    media_gmd = sum(gmds_todos) / len(gmds_todos)
    desvio = (sum((g - media_gmd)**2 for g in gmds_todos) / len(gmds_todos)) ** 0.5

    for aid, ps in pes_map.items():
        if len(ps) < 2:
            continue
        df = pd.DataFrame(ps, columns=['id','aid','peso','data'] + (['ident'] if ps and len(ps[0]) > 4 else []))
        df['data'] = pd.to_datetime(df['data'])
        df = df.sort_values('data')
        dias = (df['data'].iloc[-1] - df['data'].iloc[0]).days
        if dias <= 0:
            continue
        gmd = (df['peso'].iloc[-1] - df['peso'].iloc[0]) / dias
        ident = nomes.get(aid, f'ID {aid}')

        # GMD muito abaixo da media (mais de 2 desvios)
        if desvio > 0 and gmd < media_gmd - 2 * desvio:
            alertas.append(dict(
                animal_id=aid, identificacao=ident,
                tipo='GMD anomalo',
                descricao=f'GMD {gmd:.3f} kg/d muito abaixo da media {media_gmd:.3f} kg/d do lote',
                gravidade='Alta'
            ))
        # Perda de peso recente (ultima pesagem menor que penultima)
        if len(df) >= 2:
            if float(df['peso'].iloc[-1]) < float(df['peso'].iloc[-2]):
                perda = float(df['peso'].iloc[-2]) - float(df['peso'].iloc[-1])
                alertas.append(dict(
                    animal_id=aid, identificacao=ident,
                    tipo='Perda de peso',
                    descricao=f'Perdeu {perda:.1f} kg na ultima pesagem',
                    gravidade='Media' if perda < 10 else 'Alta'
                ))

    return alertas


def resumo_ia_fazenda(owner_id=None):
    """
    Resumo de IA para todos os lotes da fazenda.
    Retorna lista de lotes com score de risco e previsao de abate.
    """
    lotes = listar_lotes(owner_id=owner_id)
    resultado = []
    for l in lotes:
        lid = l[0]
        try:
            risco = calcular_risco_sanitario(lid)
            animais = listar_animais_por_lote(lid)
            rs = resumo_lote(lid)
            resultado.append(dict(
                lote_id=lid, lote_nome=l[1],
                risco_score=risco['score'],
                risco_nivel=risco['nivel'],
                animais_ativos=rs['ativos'],
                principal_risco=risco['fatores'][0] if risco['fatores'] else '',
            ))
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)
    return sorted(resultado, key=lambda x: x['risco_score'], reverse=True)


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
def adicionar_receita(vet_id, fazenda_owner_id, medicamento, dose, via, duracao,
                     animal_id=None, lote_id=None, carencia_dias=0,
                     observacoes="", crmv=""):
    """Emite receita e registra ocorrencia Medicacao no prontuario do(s) animal(is)."""
    _garantir_tabelas_vet()
    from datetime import date
    p  = _ph()
    dt = str(date.today())

    # 1. Inserir receita
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO receitas (vet_id,fazenda_owner_id,animal_id,lote_id,"
                f"data_emissao,medicamento,dose,via,duracao,carencia_dias,"
                f"observacoes,crmv_emissao) "
                f"VALUES({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p}) RETURNING id",
                (vet_id, fazenda_owner_id, animal_id, lote_id,
                 dt, medicamento, dose, via, duracao,
                 int(carencia_dias or 0), observacoes or "", crmv or "")
            )
            rid = cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO receitas (vet_id,fazenda_owner_id,animal_id,lote_id,"
                f"data_emissao,medicamento,dose,via,duracao,carencia_dias,"
                f"observacoes,crmv_emissao) "
                f"VALUES({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p})",
                (vet_id, fazenda_owner_id, animal_id, lote_id,
                 dt, medicamento, dose, via, duracao,
                 int(carencia_dias or 0), observacoes or "", crmv or "")
            )
            rid = cur.lastrowid

    # 2. Montar descricao da ocorrencia
    desc = (
        f"Receituario #{rid} | {medicamento} | "
        f"Dose: {dose} | Via: {via} | Duracao: {duracao}"
    )
    if carencia_dias:
        desc += f" | Carencia: {carencia_dias} dias"
    if observacoes:
        desc += f" | Obs: {observacoes}"

    # 3. Registrar ocorrencia nos animais alvo
    alvos = []
    if animal_id:
        alvos = [animal_id]
    elif lote_id:
        alvos = [a[0] for a in listar_animais_por_lote(lote_id)]

    for aid in alvos:
        try:
            adicionar_ocorrencia(
                animal_id=aid,
                data=dt,
                tipo="Medicacao",
                descricao=desc,
                gravidade="Baixa",
                custo=0,
                dias_recuperacao=0,
                status="Resolvido"
            )
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)

    return rid


# ── EXAMES LABORATORIAIS ─────────────────────────────────────
def adicionar_exame(animal_id, vet_id, tipo_exame, data_coleta,
                   laboratorio="", resultado="", interpretacao="",
                   status="aguardando", alerta=0):
    """Registra exame laboratorial. Cria ocorrencia no prontuario."""
    _garantir_tabelas_vet()
    from datetime import date
    p = _ph()
    dt = str(date.today())
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO exames_laboratoriais "
                f"(animal_id,vet_id,data_coleta,tipo_exame,laboratorio,"
                f"resultado,interpretacao,status,alerta,criado_em) "
                f"VALUES({p},{p},{p},{p},{p},{p},{p},{p},{p},{p}) RETURNING id",
                (animal_id, vet_id, str(data_coleta), tipo_exame,
                 laboratorio or "", resultado or "", interpretacao or "",
                 status, int(alerta), dt)
            )
            eid = cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO exames_laboratoriais "
                f"(animal_id,vet_id,data_coleta,tipo_exame,laboratorio,"
                f"resultado,interpretacao,status,alerta,criado_em) "
                f"VALUES({p},{p},{p},{p},{p},{p},{p},{p},{p},{p})",
                (animal_id, vet_id, str(data_coleta), tipo_exame,
                 laboratorio or "", resultado or "", interpretacao or "",
                 status, int(alerta), dt)
            )
            eid = cur.lastrowid

    # Registrar ocorrencia no prontuario
    tipo_oc = "Exame"
    desc_oc = f"Exame #{eid}: {tipo_exame}"
    if laboratorio:
        desc_oc += f" | Lab: {laboratorio}"
    if resultado and status == "concluido":
        desc_oc += f" | Resultado: {resultado[:100]}"
    if alerta:
        desc_oc += " | RESULTADO ALTERADO"
    try:
        adicionar_ocorrencia(
            animal_id=animal_id, data=str(data_coleta),
            tipo=tipo_oc, descricao=desc_oc,
            gravidade="Alta" if alerta else "Baixa",
            custo=0, dias_recuperacao=0, status="Resolvido"
        )
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)
    return eid


def atualizar_exame(exame_id, resultado, interpretacao="", status="concluido", alerta=0):
    """Atualiza resultado do exame e ajusta gravidade da ocorrencia."""
    _garantir_tabelas_vet()
    p = _ph()

    # Buscar dados do exame para atualizar ocorrencia
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT animal_id,tipo_exame,data_coleta,laboratorio "
            f"FROM exames_laboratoriais WHERE id={p}",
            (exame_id,)
        )
        row = cur.fetchone()

    # Atualizar registro do exame
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE exames_laboratoriais SET resultado={p},"
            f"interpretacao={p},status={p},alerta={p} WHERE id={p}",
            (resultado, interpretacao or "", status, int(alerta), exame_id)
        )
        conn.commit()

    # Atualizar gravidade da ocorrencia existente no prontuario
    if row:
        animal_id = row[0]
        tipo_exame = row[1]
        desc_check = f"Exame #{exame_id}:"
        nova_grav  = "Alta" if alerta else "Baixa"
        nova_desc  = f"Exame #{exame_id}: {tipo_exame}"
        if row[3]:  # laboratorio
            nova_desc += f" | Lab: {row[3]}"
        if resultado:
            nova_desc += f" | Resultado: {resultado[:100]}"
        if alerta:
            nova_desc += " | RESULTADO ALTERADO"
        try:
            with _conexao() as conn:
                cur = conn.cursor()
                cur.execute(
                    f"UPDATE ocorrencias SET gravidade={p},descricao={p} "
                    f"WHERE animal_id={p} AND descricao LIKE {p}",
                    (nova_grav, nova_desc, animal_id, f"%{desc_check}%")
                )
                conn.commit()
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)

    return True


def listar_exames(animal_id=None, vet_id=None):
    """Lista exames por animal ou por vet."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if animal_id is not None:
            cur.execute(
                f"SELECT id,animal_id,vet_id,data_coleta,tipo_exame,"
                f"laboratorio,resultado,interpretacao,status,alerta "
                f"FROM exames_laboratoriais WHERE animal_id={p} "
                f"ORDER BY data_coleta DESC",
                (animal_id,)
            )
        elif vet_id is not None:
            cur.execute(
                f"SELECT id,animal_id,vet_id,data_coleta,tipo_exame,"
                f"laboratorio,resultado,interpretacao,status,alerta "
                f"FROM exames_laboratoriais WHERE vet_id={p} "
                f"ORDER BY data_coleta DESC",
                (vet_id,)
            )
        else:
            return []
        return cur.fetchall()


# ── MONITORAMENTO POS-TRATAMENTO ──────────────────────────────
def adicionar_monitoramento(animal_id, vet_id, descricao,
                            data_inicio, data_retorno, receita_id=None):
    """Cria monitoramento pos-tratamento com data de retorno."""
    _garantir_tabelas_vet()
    from datetime import date
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO monitoramento_pos_tratamento "
                f"(animal_id,vet_id,receita_id,descricao,data_inicio,"
                f"data_retorno,status,evolucoes,alerta_enviado) "
                f"VALUES({p},{p},{p},{p},{p},{p},'ativo','[]',0) RETURNING id",
                (animal_id, vet_id, receita_id, descricao,
                 str(data_inicio), str(data_retorno))
            )
            return cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO monitoramento_pos_tratamento "
                f"(animal_id,vet_id,receita_id,descricao,data_inicio,"
                f"data_retorno,status,evolucoes,alerta_enviado) "
                f"VALUES({p},{p},{p},{p},{p},{p},'ativo','[]',0)",
                (animal_id, vet_id, receita_id, descricao,
                 str(data_inicio), str(data_retorno))
            )
            return cur.lastrowid


def registrar_evolucao(monitor_id, texto, data=None, quem="fazendeiro"):
    """Fazendeiro ou vet registra evolucao do animal monitorado."""
    _garantir_tabelas_vet()
    import json
    from datetime import date
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT evolucoes FROM monitoramento_pos_tratamento WHERE id={p}",
            (monitor_id,)
        )
        row = cur.fetchone()
        if not row:
            return False
        try:
            evols = json.loads(row[0] or "[]")
        except Exception:
            evols = []
        evols.append({
            "data": str(data or date.today()),
            "texto": texto,
            "quem": quem
        })
        cur.execute(
            f"UPDATE monitoramento_pos_tratamento SET evolucoes={p} WHERE id={p}",
            (json.dumps(evols, ensure_ascii=False), monitor_id)
        )
        conn.commit()
    return True


def encerrar_monitoramento(monitor_id):
    """Encerra o monitoramento."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE monitoramento_pos_tratamento SET status='encerrado' WHERE id={p}",
            (monitor_id,)
        )
        conn.commit()
    return True


def listar_monitoramentos(animal_id=None, vet_id=None,
                          owner_id=None, apenas_ativos=True):
    """Lista monitoramentos por animal, vet ou fazendeiro."""
    _garantir_tabelas_vet()
    import json
    from datetime import date
    p  = _ph()
    hoje = str(date.today())
    with _conexao() as conn:
        cur = conn.cursor()
        # Prefixo m. em todas as referencias para evitar AmbiguousColumn no JOIN
        filtro_status = "AND m.status='ativo'" if apenas_ativos else ""
        if animal_id is not None:
            cur.execute(
                f"SELECT m.id,m.animal_id,m.vet_id,m.receita_id,m.descricao,"
                f"m.data_inicio,m.data_retorno,m.status,m.evolucoes "
                f"FROM monitoramento_pos_tratamento m "
                f"WHERE m.animal_id={p} {filtro_status} ORDER BY m.data_retorno",
                (animal_id,)
            )
        elif vet_id is not None:
            cur.execute(
                f"SELECT m.id,m.animal_id,m.vet_id,m.receita_id,m.descricao,"
                f"m.data_inicio,m.data_retorno,m.status,m.evolucoes "
                f"FROM monitoramento_pos_tratamento m "
                f"WHERE m.vet_id={p} {filtro_status} ORDER BY m.data_retorno",
                (vet_id,)
            )
        elif owner_id is not None:
            # Usar subquery para evitar AmbiguousColumn no JOIN
            _st_filter = "AND m.status='ativo'" if apenas_ativos else ""
            cur.execute(
                f"SELECT m.id,m.animal_id,m.vet_id,m.receita_id,m.descricao,"
                f"m.data_inicio,m.data_retorno,m.status,m.evolucoes,"
                f"a.identificacao "
                f"FROM monitoramento_pos_tratamento m "
                f"JOIN animais a ON a.id=m.animal_id "
                f"WHERE a.lote_id IN ("
                f"  SELECT id FROM lotes WHERE owner_id={p}"
                f") {_st_filter} ORDER BY m.data_retorno",
                (owner_id,)
            )
        else:
            return []
        rows = cur.fetchall()

    result = []
    for r in rows:
        evols = []
        try:
            evols = json.loads(r[8] or "[]")
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)
        result.append({
            "id":           r[0],
            "animal_id":    r[1],
            "vet_id":       r[2],
            "receita_id":   r[3],
            "descricao":    r[4],
            "data_inicio":  r[5],
            "data_retorno": r[6],
            "status":       r[7],
            "evolucoes":    evols,
            "brinco":       r[9] if len(r) > 9 else None,
            "vencido":      str(r[6]) < hoje,
        })
    return result


def monitoramentos_vencendo(owner_id, dias=3):
    """Retorna monitoramentos vencidos OU com retorno em ate X dias."""
    _garantir_tabelas_vet()
    from datetime import date, timedelta
    hoje   = date.today()
    limite = str(hoje + timedelta(days=dias))
    todos  = listar_monitoramentos(owner_id=owner_id, apenas_ativos=True)
    # Inclui vencidos (data_retorno < hoje) E proximos (ate X dias)
    return [m for m in todos if str(m["data_retorno"]) <= limite]


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
def epidemiologia_por_fazenda(vet_id):
    """Retorna dados epidemiologicos consolidados por fazenda."""
    _garantir_tabelas_vet()
    from database import listar_fazendas_do_vet
    p    = _ph()
    foids = listar_fazendas_do_vet(vet_id)
    result = []
    for foid in foids:
        nome_faz = obter_nome_usuario(foid)
        with _conexao() as conn:
            cur = conn.cursor()
            # Ocorrencias por tipo
            try:
                cur.execute(
                    f"SELECT o.tipo, COUNT(*) "
                    f"FROM ocorrencias o "
                    f"JOIN animais a ON a.id=o.animal_id "
                    f"WHERE a.lote_id IN "
                    f"(SELECT id FROM lotes WHERE owner_id={p}) "
                    f"GROUP BY o.tipo ORDER BY COUNT(*) DESC LIMIT 5",
                    (foid,)
                )
                tipos = cur.fetchall()
            except Exception:
                tipos = []

            # Total animais e mortes
            try:
                cur.execute(
                    f"SELECT COUNT(*), "
                    f"COUNT(CASE WHEN a.status='MORTO' THEN 1 END) "
                    f"FROM animais a "
                    f"WHERE a.lote_id IN "
                    f"(SELECT id FROM lotes WHERE owner_id={p}) "
                    f"AND a.ativo=1",
                    (foid,)
                )
                r = cur.fetchone()
                n_ativos = r[0] or 0
                n_mortos = r[1] or 0
            except Exception:
                n_ativos = n_mortos = 0

        result.append({
            "owner_id":  foid,
            "nome":      nome_faz,
            "n_ativos":  n_ativos,
            "n_mortos":  n_mortos,
            "taxa_mort": round(100 * n_mortos / max(1, n_ativos+n_mortos), 2),
            "por_tipo":  tipos,
        })
    return result


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
_PASSOS_ONBOARDING = [
    ("perfil",     "Complete seu perfil"),
    ("lote",       "Crie seu primeiro lote"),
    ("animais",    "Cadastre seus animais"),
    ("calendario", "Configure o calendario sanitario"),
    ("alertas",    "Configure seus alertas"),
]


def obter_progresso_onboarding(user_id):
    """Retorna dict {passo: completo} para o usuario."""
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            p = _ph()
            cur.execute(
                f"SELECT passo, completo FROM onboarding_log "
                f"WHERE user_id={p}",
                (user_id,)
            )
            rows = {r[0]: bool(r[1]) for r in cur.fetchall()}
        return {passo: rows.get(passo, False)
                for passo, _ in _PASSOS_ONBOARDING}
    except Exception:
        _log_war.debug('excecao tratada: %s', exc_info=True)
        return {passo: False for passo, _ in _PASSOS_ONBOARDING}


def marcar_passo_onboarding(user_id, passo):
    """Marca passo do onboarding como completo."""
    from datetime import date
    p = _ph()
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            if _usar_postgres():
                cur.execute(
                    f"INSERT INTO onboarding_log "
                    f"(user_id,passo,completo,criado_em) "
                    f"VALUES({p},{p},1,{p}) "
                    f"ON CONFLICT(user_id,passo) DO UPDATE SET completo=1",
                    (user_id, passo, str(date.today()))
                )
            else:
                cur.execute(
                    f"INSERT OR REPLACE INTO onboarding_log "
                    f"(user_id,passo,completo,criado_em) "
                    f"VALUES({p},{p},1,{p})",
                    (user_id, passo, str(date.today()))
                )
            conn.commit()
        # Verificar se todos os passos foram concluidos
        prog = obter_progresso_onboarding(user_id)
        if all(prog.values()):
            with _conexao() as conn:
                cur = conn.cursor()
                cur.execute(
                    f"UPDATE usuarios SET onboarding_completo=1 WHERE id={p}",
                    (user_id,)
                )
                conn.commit()
        return True
    except Exception:
        _log_war.debug('excecao tratada: %s', exc_info=True)
        return False


def onboarding_completo(user_id):
    """Verifica se o usuario completou o onboarding."""
    p = _ph()
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT onboarding_completo FROM usuarios WHERE id={p}",
                (user_id,)
            )
            r = cur.fetchone()
        return bool(r and r[0])
    except Exception:
        _log_war.debug('excecao tratada: %s', exc_info=True)
        return True  # Em caso de erro, nao bloquear



def criar_dados_demo(owner_id):
    """Cria fazenda demo com dados fictícios para novo usuário.
    Chamada automaticamente no primeiro login.
    """
    from datetime import date, timedelta
    import random
    p = _ph()
    _log_db.info("Criando dados demo para owner_id=%s", owner_id)
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            # Verificar se já tem lote (não criar duplicado)
            cur.execute(
                f"SELECT COUNT(*) FROM lotes WHERE owner_id={p}", (owner_id,)
            )
            r = cur.fetchone()
            if r and r[0] > 0:
                return True  # já tem dados

            # Lote demo
            dt_entrada = str(date.today() - timedelta(days=90))
            if _usar_postgres():
                cur.execute(
                    f"INSERT INTO lotes (nome,descricao,data_entrada,"
                    f"qtd_comprada,qtd_recebida,preco_por_animal,owner_id,status)"
                    f" VALUES ({p},{p},{p},{p},{p},{p},{p},{p}) RETURNING id",
                    ("Lote Demo — Nelore 2025",
                     "Lote criado automaticamente para demonstração",
                     dt_entrada, 8, 8, 2800.00, owner_id, "ATIVO")
                )
                lote_id = cur.fetchone()[0]
            else:
                cur.execute(
                    f"INSERT INTO lotes (nome,descricao,data_entrada,"
                    f"qtd_comprada,qtd_recebida,preco_por_animal,owner_id,status)"
                    f" VALUES ({p},{p},{p},{p},{p},{p},{p},{p})",
                    ("Lote Demo — Nelore 2025",
                     "Lote criado automaticamente para demonstração",
                     dt_entrada, 8, 8, 2800.00, owner_id, "ATIVO")
                )
                lote_id = cur.lastrowid
            conn.commit()

            # 8 animais demo
            animais = [
                ("DEMO-01","Nelore","M",24,320),("DEMO-02","Nelore","M",22,305),
                ("DEMO-03","Nelore","M",24,332),("DEMO-04","Angus","M",20,348),
                ("DEMO-05","Angus","M",21,338),("DEMO-06","Nelore","F",18,280),
                ("DEMO-07","Nelore","F",20,295),("DEMO-08","Angus","M",23,355),
            ]
            animal_ids = []
            for ident, raca, sexo, idade, peso in animais:
                if _usar_postgres():
                    cur.execute(
                        f"INSERT INTO animais (identificacao,raca,sexo,"
                        f"idade_meses,peso_entrada,lote_id,ativo,status)"
                        f" VALUES ({p},{p},{p},{p},{p},{p},1,'ATIVO') RETURNING id",
                        (ident, raca, sexo, idade, peso, lote_id)
                    )
                    animal_ids.append(cur.fetchone()[0])
                else:
                    cur.execute(
                        f"INSERT INTO animais (identificacao,raca,sexo,"
                        f"idade_meses,peso_entrada,lote_id,ativo,status)"
                        f" VALUES ({p},{p},{p},{p},{p},{p},1,'ATIVO')",
                        (ident, raca, sexo, idade, peso, lote_id)
                    )
                    animal_ids.append(cur.lastrowid)
            conn.commit()

            # Pesagens ao longo de 90 dias
            pesos_base = [320,305,332,348,338,280,295,355]
            for i, aid in enumerate(animal_ids):
                peso = pesos_base[i]
                for dias_atras in [90, 60, 30, 0]:
                    peso += random.randint(18, 32)
                    dt = str(date.today() - timedelta(days=dias_atras))
                    cur.execute(
                        f"INSERT INTO pesagens (animal_id,peso,data)"
                        f" VALUES ({p},{p},{p})",
                        (aid, round(peso, 1), dt)
                    )
            conn.commit()

            # Custos demo
            for cat, desc, val, dias in [
                ("racao","Ração concentrada — 3 meses",4200.00,80),
                ("medicamento","Vermifugação e vacinas",480.00,75),
                ("mao_de_obra","Mão de obra — 3 meses",1800.00,70),
                ("veterinario","Visita técnica",350.00,45),
            ]:
                dt = str(date.today() - timedelta(days=dias))
                cur.execute(
                    f"INSERT INTO custos_lote"
                    f" (lote_id,categoria,descricao,valor,data_lancamento,owner_id)"
                    f" VALUES ({p},{p},{p},{p},{p},{p})",
                    (lote_id, cat, desc, val, dt, owner_id)
                )
            conn.commit()

        # Marcar demo como criado
        marcar_onboarding_completo(owner_id)
        _log_db.info("Dados demo criados: lote_id=%s, %d animais",
                     lote_id, len(animal_ids))
        return True
    except Exception as _e:
        _log_err.error("criar_dados_demo: %s", _e)
        return False


# ── IMPORTACAO CSV ────────────────────────────────────────────


def lancar_honorario(vet_id, fazenda_owner_id, descricao, valor,
                     tipo="consulta", visita_id=None,
                     itens=None, observacoes=""):
    """Lanca honorario do vet. itens = lista de dicts com
    {descricao, quantidade, valor_unitario}."""
    _garantir_tabelas_vet()
    from datetime import date
    p = _ph()
    dt = str(date.today())

    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO honorarios_vet "
                f"(vet_id,fazenda_owner_id,visita_id,data_lancamento,"
                f"descricao,tipo,valor,status,observacoes) "
                f"VALUES({p},{p},{p},{p},{p},{p},{p},'pendente',{p}) RETURNING id",
                (vet_id, fazenda_owner_id, visita_id, dt,
                 descricao, tipo, float(valor), observacoes or "")
            )
            hid = cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO honorarios_vet "
                f"(vet_id,fazenda_owner_id,visita_id,data_lancamento,"
                f"descricao,tipo,valor,status,observacoes) "
                f"VALUES({p},{p},{p},{p},{p},{p},{p},'pendente',{p})",
                (vet_id, fazenda_owner_id, visita_id, dt,
                 descricao, tipo, float(valor), observacoes or "")
            )
            hid = cur.lastrowid

    # Inserir itens se fornecidos
    if itens:
        for item in itens:
            qtd   = float(item.get("quantidade", 1))
            v_un  = float(item.get("valor_unitario", 0))
            v_tot = round(qtd * v_un, 2)
            try:
                with _conexao() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        f"INSERT INTO honorarios_itens "
                        f"(honorario_id,descricao,quantidade,"
                        f"valor_unitario,valor_total) "
                        f"VALUES({p},{p},{p},{p},{p})",
                        (hid, item.get("descricao",""),
                         qtd, v_un, v_tot)
                    )
                    conn.commit()
            except Exception as _ew:
                _log_err.error("erro em lancar_honorario: %s", _ew)
    return hid


def listar_honorarios(vet_id, fazenda_owner_id=None, status=None):
    """Lista honorarios do vet, opcionalmente por fazenda e status."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        sql = (
            f"SELECT id,vet_id,fazenda_owner_id,visita_id,"
            f"data_lancamento,descricao,tipo,valor,status,"
            f"data_pagamento,forma_pagamento,observacoes "
            f"FROM honorarios_vet WHERE vet_id={p}"
        )
        params = [vet_id]
        if fazenda_owner_id is not None:
            sql += f" AND fazenda_owner_id={p}"
            params.append(fazenda_owner_id)
        if status:
            sql += f" AND status={p}"
            params.append(status)
        sql += " ORDER BY data_lancamento DESC"
        cur.execute(sql, tuple(params))
        return cur.fetchall()


def listar_itens_honorario(honorario_id):
    """Lista itens de um honorario."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id,honorario_id,descricao,quantidade,"
            f"valor_unitario,valor_total "
            f"FROM honorarios_itens WHERE honorario_id={p}",
            (honorario_id,)
        )
        return cur.fetchall()


def registrar_pagamento_honorario(honorario_id, forma_pagamento,
                                  data_pagamento=None):
    """Marca honorario como pago."""
    _garantir_tabelas_vet()
    from datetime import date
    p  = _ph()
    dt = str(data_pagamento or date.today())
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE honorarios_vet SET status='pago',"
            f"data_pagamento={p},forma_pagamento={p} WHERE id={p}",
            (dt, forma_pagamento, honorario_id)
        )
        conn.commit()
    return True


def cancelar_honorario(honorario_id):
    """Cancela um honorario pendente."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE honorarios_vet SET status='cancelado' WHERE id={p}",
            (honorario_id,)
        )
        conn.commit()
    return True


def listar_receitas(vet_id=None, fazenda_owner_id=None):
    """Lista receitas. Vet ve as proprias, fazendeiro ve as recebidas."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if vet_id is not None:
            cur.execute(
                f"SELECT id,vet_id,fazenda_owner_id,animal_id,lote_id,"
                f"data_emissao,medicamento,dose,via,duracao,carencia_dias,"
                f"observacoes,crmv_emissao FROM receitas "
                f"WHERE vet_id={p} ORDER BY data_emissao DESC",
                (vet_id,)
            )
        elif fazenda_owner_id is not None:
            cur.execute(
                f"SELECT id,vet_id,fazenda_owner_id,animal_id,lote_id,"
                f"data_emissao,medicamento,dose,via,duracao,carencia_dias,"
                f"observacoes,crmv_emissao FROM receitas "
                f"WHERE fazenda_owner_id={p} ORDER BY data_emissao DESC",
                (fazenda_owner_id,)
            )
        else:
            return []
        return cur.fetchall()


# ── PROTOCOLOS SANITARIOS ─────────────────────────────────────
def adicionar_protocolo(vet_id, nome, descricao="", categoria="geral"):
    """Cria novo protocolo sanitario."""
    _garantir_tabelas_vet()
    from datetime import date
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO protocolos_sanitarios (vet_id,nome,descricao,categoria,criado_em) "
                f"VALUES({p},{p},{p},{p},{p}) RETURNING id",
                (vet_id, nome, descricao or "", categoria, str(date.today()))
            )
            return cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO protocolos_sanitarios (vet_id,nome,descricao,categoria,criado_em) "
                f"VALUES({p},{p},{p},{p},{p})",
                (vet_id, nome, descricao or "", categoria, str(date.today()))
            )
            return cur.lastrowid


def listar_protocolos(vet_id):
    """Lista protocolos do veterinario."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id,vet_id,nome,descricao,categoria,criado_em "
            f"FROM protocolos_sanitarios WHERE vet_id={p} ORDER BY nome",
            (vet_id,)
        )
        return cur.fetchall()


def adicionar_item_protocolo(protocolo_id, ordem, tipo, nome, dia_offset, observacao=""):
    """Adiciona item (vacina/medicacao) ao protocolo."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO protocolo_itens (protocolo_id,ordem,tipo,nome,dia_offset,observacao) "
            f"VALUES({p},{p},{p},{p},{p},{p})",
            (protocolo_id, int(ordem), tipo, nome, int(dia_offset), observacao or "")
        )
        conn.commit()
        return True


def listar_itens_protocolo(protocolo_id):
    """Lista itens de um protocolo na ordem correta."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id,protocolo_id,ordem,tipo,nome,dia_offset,observacao "
            f"FROM protocolo_itens WHERE protocolo_id={p} ORDER BY dia_offset",
            (protocolo_id,)
        )
        return cur.fetchall()


def aplicar_protocolo_no_lote(protocolo_id, lote_id, data_inicio, vet_id):
    """Aplica um protocolo ao lote criando vacinas agendadas."""
    _garantir_tabelas_vet()
    from datetime import datetime, timedelta
    try:
        dt_inicio = datetime.strptime(str(data_inicio)[:10], "%Y-%m-%d").date()
    except Exception:
        from datetime import date
        dt_inicio = date.today()

    itens = listar_itens_protocolo(protocolo_id)
    n_criados = 0
    for item in itens:
        _, _, ordem, tipo, nome_item, dia_offset, obs_item = item
        data_prev = dt_inicio + timedelta(days=int(dia_offset))
        try:
            adicionar_vacina_agenda(
                lote_id=lote_id,
                nome_vacina=nome_item,
                data_prevista=str(data_prev),
                observacao=f"Protocolo: {obs_item or 'sem obs'}",
                agendado_por=vet_id
            )
            n_criados += 1
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)
    return n_criados


# ── VISITAS TECNICAS ──────────────────────────────────────────
def adicionar_visita(vet_id, fazenda_owner_id, data_visita, objetivo,
                    duracao_min=60, observacoes=""):
    """Agenda nova visita tecnica."""
    _garantir_tabelas_vet()
    from datetime import date
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO visitas_tecnicas (vet_id,fazenda_owner_id,data_visita,"
                f"objetivo,duracao_min,status,observacoes,criado_em) "
                f"VALUES({p},{p},{p},{p},{p},'agendada',{p},{p}) RETURNING id",
                (vet_id, fazenda_owner_id, str(data_visita), objetivo,
                 int(duracao_min or 60), observacoes or "", str(date.today()))
            )
            return cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO visitas_tecnicas (vet_id,fazenda_owner_id,data_visita,"
                f"objetivo,duracao_min,status,observacoes,criado_em) "
                f"VALUES({p},{p},{p},{p},{p},'agendada',{p},{p})",
                (vet_id, fazenda_owner_id, str(data_visita), objetivo,
                 int(duracao_min or 60), observacoes or "", str(date.today()))
            )
            return cur.lastrowid


def listar_visitas(vet_id=None, fazenda_owner_id=None):
    """Lista visitas - vet ve as proprias, fazendeiro ve as recebidas."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if vet_id is not None:
            cur.execute(
                f"SELECT id,vet_id,fazenda_owner_id,data_visita,objetivo,"
                f"duracao_min,status,observacoes FROM visitas_tecnicas "
                f"WHERE vet_id={p} ORDER BY data_visita DESC",
                (vet_id,)
            )
        elif fazenda_owner_id is not None:
            cur.execute(
                f"SELECT id,vet_id,fazenda_owner_id,data_visita,objetivo,"
                f"duracao_min,status,observacoes FROM visitas_tecnicas "
                f"WHERE fazenda_owner_id={p} ORDER BY data_visita DESC",
                (fazenda_owner_id,)
            )
        else:
            return []
        return cur.fetchall()


def atualizar_status_visita(visita_id, status):
    """Atualiza status da visita (agendada/realizada/cancelada)."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE visitas_tecnicas SET status={p} WHERE id={p}",
            (status, visita_id)
        )
        conn.commit()
        return True


# ── RELATORIOS DE VISITA ──────────────────────────────────────
def adicionar_relatorio_visita(vet_id, fazenda_owner_id, achados, tratamentos,
                              recomendacoes, animais_inspecionados=0,
                              visita_id=None, proxima_visita=None, crmv=""):
    """Cria relatorio tecnico da visita."""
    _garantir_tabelas_vet()
    from datetime import date
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO relatorios_visita (visita_id,vet_id,fazenda_owner_id,"
                f"data_relatorio,animais_inspecionados,achados,tratamentos,"
                f"recomendacoes,proxima_visita,crmv_emissao) "
                f"VALUES({p},{p},{p},{p},{p},{p},{p},{p},{p},{p}) RETURNING id",
                (visita_id, vet_id, fazenda_owner_id, str(date.today()),
                 int(animais_inspecionados or 0), achados, tratamentos,
                 recomendacoes, str(proxima_visita) if proxima_visita else None,
                 crmv or "")
            )
            return cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO relatorios_visita (visita_id,vet_id,fazenda_owner_id,"
                f"data_relatorio,animais_inspecionados,achados,tratamentos,"
                f"recomendacoes,proxima_visita,crmv_emissao) "
                f"VALUES({p},{p},{p},{p},{p},{p},{p},{p},{p},{p})",
                (visita_id, vet_id, fazenda_owner_id, str(date.today()),
                 int(animais_inspecionados or 0), achados, tratamentos,
                 recomendacoes, str(proxima_visita) if proxima_visita else None,
                 crmv or "")
            )
            return cur.lastrowid


def listar_relatorios(vet_id=None, fazenda_owner_id=None):
    """Lista relatorios de visita."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if vet_id is not None:
            cur.execute(
                f"SELECT id,visita_id,vet_id,fazenda_owner_id,data_relatorio,"
                f"animais_inspecionados,achados,tratamentos,recomendacoes,"
                f"proxima_visita,crmv_emissao FROM relatorios_visita "
                f"WHERE vet_id={p} ORDER BY data_relatorio DESC",
                (vet_id,)
            )
        elif fazenda_owner_id is not None:
            cur.execute(
                f"SELECT id,visita_id,vet_id,fazenda_owner_id,data_relatorio,"
                f"animais_inspecionados,achados,tratamentos,recomendacoes,"
                f"proxima_visita,crmv_emissao FROM relatorios_visita "
                f"WHERE fazenda_owner_id={p} ORDER BY data_relatorio DESC",
                (fazenda_owner_id,)
            )
        else:
            return []
        return cur.fetchall()


# ── CARENCIA ──────────────────────────────────────────────────
# ── PAINEL DE SAUDE DO REBANHO ────────────────────────────────
def painel_saude_rebanho(owner_id):
    """Retorna estatisticas sanitarias do rebanho."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()

        # Total de ocorrencias por tipo
        try:
            cur.execute(
                f"SELECT o.tipo, COUNT(*) FROM ocorrencias o "
                f"JOIN animais a ON a.id=o.animal_id "
                f"JOIN lotes l ON l.id=a.lote_id "
                f"WHERE l.owner_id={p} GROUP BY o.tipo ORDER BY COUNT(*) DESC",
                (owner_id,)
            )
            por_tipo = cur.fetchall()
        except Exception:
            por_tipo = []

        # Total de mortes
        try:
            cur.execute(
                f"SELECT COUNT(*) FROM animais a "
                f"JOIN lotes l ON l.id=a.lote_id "
                f"WHERE l.owner_id={p} AND COALESCE(a.status,'')='MORTO'",
                (owner_id,)
            )
            n_mortes = cur.fetchone()[0]
        except Exception:
            n_mortes = 0

        # Total de animais ativos
        try:
            cur.execute(
                f"SELECT COUNT(*) FROM animais a "
                f"JOIN lotes l ON l.id=a.lote_id "
                f"WHERE l.owner_id={p} AND a.ativo=1",
                (owner_id,)
            )
            n_ativos = cur.fetchone()[0]
        except Exception:
            n_ativos = 0

        # Ocorrencias graves (gravidade Alta)
        try:
            cur.execute(
                f"SELECT COUNT(*) FROM ocorrencias o "
                f"JOIN animais a ON a.id=o.animal_id "
                f"JOIN lotes l ON l.id=a.lote_id "
                f"WHERE l.owner_id={p} AND o.gravidade='Alta'",
                (owner_id,)
            )
            n_graves = cur.fetchone()[0]
        except Exception:
            n_graves = 0

    return {
        "por_tipo":   por_tipo,
        "n_mortes":   n_mortes,
        "n_ativos":   n_ativos,
        "n_graves":   n_graves,
        "taxa_mortalidade": round(100 * n_mortes / max(1, n_mortes + n_ativos), 2),
    }






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


def _garantir_coluna_onboarding():
    """Garante que a coluna onboarding_completo existe na tabela usuarios."""
    with _conexao() as conn:
        cur = conn.cursor()
        try:
            if _usar_postgres():
                cur.execute(
                    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS "
                    "onboarding_completo INTEGER DEFAULT 0"
                )
            else:
                # SQLite: verificar antes de adicionar
                cur.execute("PRAGMA table_info(usuarios)")
                cols = [r[1] for r in cur.fetchall()]
                if 'onboarding_completo' not in cols:
                    cur.execute(
                        "ALTER TABLE usuarios ADD COLUMN "
                        "onboarding_completo INTEGER DEFAULT 0"
                    )
            conn.commit()
            return True
        except Exception:
            _log_war.debug('excecao tratada: %s', exc_info=True)
            return False


def marcar_onboarding_completo(uid):
    """Marca o onboarding como concluido para o usuario."""
    _garantir_coluna_onboarding()
    with _conexao() as conn:
        cur = conn.cursor()
        p = _ph()
        try:
            cur.execute(
                f"UPDATE usuarios SET onboarding_completo=1 WHERE id={p}",
                (uid,)
            )
            conn.commit()
            # Verificar se UPDATE afetou alguma linha
            if hasattr(cur, 'rowcount') and cur.rowcount == 0:
                # Usuario nao encontrado - nao e erro critico
                pass
            return True
        except Exception as e:
            try:
                conn.rollback()
            except Exception as _ew:
                _log_war.debug("excecao ignorada: %s", _ew)
            return False


def onboarding_concluido(uid):
    """Verifica se o usuario ja completou o onboarding."""
    _garantir_coluna_onboarding()
    with _conexao() as conn:
        cur = conn.cursor()
        p = _ph()
        try:
            cur.execute(
                f"SELECT onboarding_completo FROM usuarios WHERE id={p}",
                (uid,)
            )
            r = cur.fetchone()
            return bool(r and r[0])
        except Exception:
            _log_war.debug('excecao tratada: %s', exc_info=True)
            return False


def criar_dados_exemplo(uid):
    """Cria uma fazenda demo com 1 lote e 5 animais ficticios.
    Bloqueia se ultrapassar o limite do plano."""
    import random
    from datetime import date as _d, timedelta as _td

    # Verificar se ja tem dados exemplo
    lotes_user = listar_lotes(owner_id=uid)
    if any('[DEMO]' in (l[1] or '') for l in lotes_user):
        return dict(ja_existe=True, bloqueado=False,
                    msg="Voce ja tem dados de exemplo cadastrados.")

    # Verificar limite do plano (5 animais sao criados)
    try:
        lim = verificar_limite_animais(uid, 5)
        if not lim["pode"]:
            return dict(
                ja_existe=False,
                bloqueado=True,
                msg=(f"Limite do plano atingido. Voce tem {lim['atual']} de "
                     f"{lim['limite']} animais e os dados de exemplo criariam "
                     f"mais 5. Disponiveis: {lim['disponiveis']}. "
                     f"Faca upgrade ou remova animais antes de criar dados de exemplo.")
            )
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)

    hoje = _d.today()
    inicio = hoje - _td(days=90)

    # Criar lote demo
    lote_id = adicionar_lote(
        nome="[DEMO] Pasto Vitrine",
        descricao="Lote de exemplo - pode excluir quando quiser",
        data_entrada=str(inicio),
        qtd_comprada=5,
        qtd_recebida=5,
        transporte="Demo",
        owner_id=uid
    )

    # Criar 5 animais com pesagens
    nomes = ["DEMO-001", "DEMO-002", "DEMO-003", "DEMO-004", "DEMO-005"]
    pesos_iniciais = [280, 295, 310, 270, 305]
    ganhos = [0.85, 0.75, 0.90, 0.65, 0.80]  # kg/dia

    for i, nome in enumerate(nomes):
        aid = adicionar_animal(nome, 24, lote_id)
        # Pesagem inicial
        adicionar_pesagem(aid, pesos_iniciais[i], str(inicio))
        # Pesagem ha 30 dias
        peso_30 = pesos_iniciais[i] + ganhos[i] * 60
        adicionar_pesagem(aid, round(peso_30, 1), str(inicio + _td(days=60)))
        # Pesagem atual
        peso_hoje = pesos_iniciais[i] + ganhos[i] * 90
        adicionar_pesagem(aid, round(peso_hoje, 1), str(hoje))

    # Adicionar uma ocorrencia exemplo
    primeiro_animal = listar_animais_por_lote(lote_id)[0]
    adicionar_ocorrencia(
        primeiro_animal[0],
        str(inicio + _td(days=30)),
        "Vacina",
        "Vacinacao contra Aftosa (exemplo)",
        "Baixa",
        15.0,
        0,
        "Resolvido"
    )

    return dict(ja_existe=False, bloqueado=False,
                msg="Fazenda exemplo criada! Explore o sistema.",
                lote_id=lote_id)


def remover_dados_exemplo(uid):
    """Remove os dados de exemplo do usuario - cascade manual."""
    lotes_demo = [l for l in listar_lotes(owner_id=uid)
                  if '[DEMO]' in (l[1] or '')]
    n_removidos = 0
    p = _ph()
    for lote in lotes_demo:
        lid = lote[0]
        with _conexao() as conn:
            cur = conn.cursor()
            try:
                # 1. Buscar animais do lote
                cur.execute(
                    f"SELECT id FROM animais WHERE lote_id={p}", (lid,)
                )
                aids = [r[0] for r in cur.fetchall()]

                # 2. Remover registros dos animais
                for aid in aids:
                    for tbl in ['pesagens', 'ocorrencias', 'medicamentos_uso']:
                        try:
                            cur.execute(
                                f"DELETE FROM {tbl} WHERE animal_id={p}",
                                (aid,)
                            )
                        except Exception as _ew:
                            _log_war.debug("excecao ignorada: %s", _ew)
                if aids:
                    cur.execute(
                        f"UPDATE animais SET ativo=0 WHERE lote_id={p}",
                        (lid,)
                    )
                    cur.execute(
                        f"DELETE FROM animais WHERE lote_id={p}",
                        (lid,)
                    )

                # 4. Remover vacinas e outros do lote
                for tbl in ['vacinas_agenda', 'reproducao',
                            'piquetes_historico', 'vendas_lote']:
                    try:
                        cur.execute(
                            f"DELETE FROM {tbl} WHERE lote_id={p}", (lid,)
                        )
                    except Exception as _ew:
                        _log_war.debug("excecao ignorada: %s", _ew)
                cur.execute(f"DELETE FROM lotes WHERE id={p}", (lid,))
                conn.commit()
                n_removidos += 1
            except Exception as e:
                try:
                    conn.rollback()
                except Exception as _ew:
                    _log_war.debug("excecao ignorada: %s", _ew)
    return n_removidos


def kpis_executivos(owner_id=None, lote_ids=None):
    """
    KPIs consolidados para o Dashboard Executivo.
    Retorna metricas financeiras, sanitarias e produtivas da fazenda.
    lote_ids: lista de IDs especifica (para vet com fazendas aprovadas)
    """
    import pandas as pd
    from datetime import date as _d, timedelta as _td

    if lote_ids is not None:
        # Buscar lotes pelo ID diretamente
        lotes = [l for l in listar_lotes(owner_id=None) if l[0] in lote_ids]
    else:
        lotes = listar_lotes(owner_id=owner_id)
    if not lotes:
        return {}

    ids_lotes = [l[0] for l in lotes]

    # ── Contagens basicas ─────────────────────────────────────────────────────
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        placeholders = ','.join([str(p)] * len(ids_lotes)) if _usar_postgres() else ','.join(['?'] * len(ids_lotes))

        cur.execute(f"SELECT COUNT(*) FROM animais a JOIN lotes l ON l.id=a.lote_id WHERE l.id IN ({placeholders}) AND COALESCE(a.ativo,1)=1", ids_lotes)
        total_animais = cur.fetchone()[0]

        cur.execute(f"SELECT COUNT(*) FROM mortalidade m JOIN animais a ON a.id=m.animal_id JOIN lotes l ON l.id=a.lote_id WHERE l.id IN ({placeholders})", ids_lotes)
        total_mortes = cur.fetchone()[0]

        cur.execute(f"SELECT COALESCE(SUM(o.custo),0) FROM ocorrencias o JOIN animais a ON a.id=o.animal_id JOIN lotes l ON l.id=a.lote_id WHERE l.id IN ({placeholders})", ids_lotes)
        custo_sanitario = float(cur.fetchone()[0] or 0)

        cur.execute(f"SELECT COUNT(*) FROM vacinas_agenda v WHERE v.lote_id IN ({placeholders}) AND v.status='pendente'", ids_lotes)
        vacinas_pend = cur.fetchone()[0]

        cur.execute(f"SELECT COUNT(*) FROM ocorrencias o JOIN animais a ON a.id=o.animal_id JOIN lotes l ON l.id=a.lote_id WHERE l.id IN ({placeholders}) AND o.status='Em tratamento'", ids_lotes)
        em_tratamento = cur.fetchone()[0]

    # ── GMD medio geral ───────────────────────────────────────────────────────
    todos_gmds = []
    for lid in ids_lotes:
        gmds = calcular_gmds_lote(lid)
        todos_gmds.extend(g for g in gmds.values() if g > 0)

    gmd_geral = sum(todos_gmds) / len(todos_gmds) if todos_gmds else 0

    # ── Taxa de mortalidade geral ─────────────────────────────────────────────
    total_cabecas = sum(listar_lotes(owner_id=owner_id)[i][4] or 0 for i in range(len(lotes)))
    taxa_mort_geral = round(total_mortes / max(total_cabecas, 1) * 100, 2)

    # ── Risco medio dos lotes ─────────────────────────────────────────────────
    riscos = []
    for lid in ids_lotes:
        try:
            r = calcular_risco_sanitario(lid)
            riscos.append(r['score'])
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)
    risco_medio = round(sum(riscos) / len(riscos), 1) if riscos else 0

    # ── Lote mais critico ─────────────────────────────────────────────────────
    resumo_r = resumo_ia_fazenda(owner_id=owner_id)
    lote_critico = resumo_r[0] if resumo_r else None

    # ── Evolucao de animais (ultimos 6 meses) ────────────────────────────────
    evolucao = []
    hoje = _d.today()
    for m in range(5, -1, -1):
        mes_ref = hoje.replace(day=1) - _td(days=m*30)
        mes_str = mes_ref.strftime('%b/%y')
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT COUNT(*) FROM animais a JOIN lotes l ON l.id=a.lote_id"
                f" WHERE l.id IN ({placeholders})"
                f" AND COALESCE(a.ativo,1)=1",
                ids_lotes,
            )
            n = cur.fetchone()[0]
        evolucao.append({'mes': mes_str, 'animais': n})

    return dict(
        total_lotes=len(lotes),
        total_animais=total_animais,
        total_mortes=total_mortes,
        taxa_mortalidade=taxa_mort_geral,
        custo_sanitario=custo_sanitario,
        custo_por_animal=round(custo_sanitario / max(total_animais, 1), 2),
        vacinas_pendentes=vacinas_pend,
        em_tratamento=em_tratamento,
        gmd_geral=round(gmd_geral, 3),
        risco_medio=risco_medio,
        lote_critico=lote_critico,
        evolucao_animais=evolucao,
        n_lotes_alto_risco=sum(1 for r in riscos if r >= 40),
    )


def sincronizar_todos_lotes():
    lotes = listar_lotes()
    resultados = []
    for l in lotes:
        n = atualizar_qtd_lote(l[0])
        resultados.append((l[0], l[1], n))
    return resultados
