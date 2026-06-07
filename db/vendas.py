# db/vendas.py -- Ciclo de venda de lotes e animais
# Venda total, venda parcial, marcacao de status e historico.
# Depende de db.core e db.schema. Dependencias de outros dominios
# usam lazy import dentro das funcoes.

import csv
import io
from datetime import date, datetime, timedelta

from db.core import (
    _conexao, _ph, _fetch, _fetchone, _usar_postgres, _cached,
)
from db.schema import _log_db, _log_err, _log_war


def marcar_animal_vendido(animal_id, data_venda=None, preco_kg=0,
                          peso_abate=0, observacao="",
                          preco_arroba=0, frigorifico="", gta=""):
    """Marca animal como VENDIDO. Salva dados na tabela vendas_animais."""
    from datetime import date
    p  = _ph()
    dt = str(data_venda or date.today())
    # Calcular preco_arroba se não informado (converter de preco_kg)
    if not preco_arroba and preco_kg:
        preco_arroba = preco_kg * 15 / 0.5
    # Calcular receita
    arrobas = peso_abate * 0.5 / 15 if peso_abate else 0
    receita = arrobas * preco_arroba if preco_arroba else 0

    with _conexao() as conn:
        cur = conn.cursor()
        # Atualizar status do animal
        cur.execute(
            f"UPDATE animais SET status='VENDIDO', ativo=0 WHERE id={p}",
            (animal_id,)
        )
        # Normalizar status para MAIÚSCULO
        try:
            cur.execute(
                f"UPDATE animais SET status=UPPER(status) "
                f"WHERE lote_id=(SELECT lote_id FROM animais WHERE id={p})"
                f" AND status != UPPER(status)",
                (animal_id,)
            )
        except Exception:
            pass
        # Garantir que tabela vendas_animais existe
        try:
            _pk_va = "SERIAL PRIMARY KEY" if _usar_postgres()                      else "INTEGER PRIMARY KEY AUTOINCREMENT"
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS vendas_animais ("
                f"id {_pk_va}, animal_id INTEGER NOT NULL, "
                f"lote_id INTEGER NOT NULL, owner_id INTEGER DEFAULT NULL, "
                f"data_venda TEXT NOT NULL, peso_abate REAL DEFAULT 0, "
                f"preco_arroba REAL DEFAULT 0, receita REAL DEFAULT 0, "
                f"frigorifico TEXT DEFAULT '', gta_numero TEXT DEFAULT '', "
                f"obs TEXT DEFAULT '')"
            )
            if _usar_postgres():
                for _col, _tipo in [
                    ("owner_id","INTEGER"),("peso_abate","REAL"),
                    ("preco_arroba","REAL"),("receita","REAL"),
                    ("frigorifico","TEXT"),("gta_numero","TEXT"),("obs","TEXT")
                ]:
                    try:
                        cur.execute(
                            f"ALTER TABLE vendas_animais "
                            f"ADD COLUMN IF NOT EXISTS {_col} {_tipo}"
                        )
                    except Exception:
                        pass
            conn.commit()
        except Exception:
            pass
        # Salvar dados da venda na tabela dedicada
        # Buscar lote_id e owner_id primeiro (compatível PG e SQLite)
        try:
            cur.execute(
                f"SELECT a.lote_id, COALESCE(l.owner_id,0) "
                f"FROM animais a LEFT JOIN lotes l ON l.id=a.lote_id "
                f"WHERE a.id={p}",
                (animal_id,)
            )
            _row = cur.fetchone()
            _lote_id  = _row[0] if _row else None
            _owner_id = _row[1] if _row and len(_row) > 1 else None

            if _lote_id:
                cur.execute(
                    f"INSERT INTO vendas_animais "
                    f"(animal_id,lote_id,owner_id,data_venda,"
                    f"peso_abate,preco_arroba,receita,"
                    f"frigorifico,gta_numero,obs) "
                    f"VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p})",
                    (animal_id, _lote_id, _owner_id, dt,
                     float(peso_abate or 0), float(preco_arroba or 0),
                     round(receita, 2), frigorifico or "",
                     gta or "", observacao or "")
                )
                _log_db.info(
                    "Venda animal %s salva: R$ %.2f (lote %s)",
                    animal_id, receita, _lote_id
                )
        except Exception as _ev:
            _log_err.error("vendas_animais insert FALHOU: %s", _ev)
        conn.commit()
    # Registrar ocorrencia no prontuario
    try:
        desc = f"Animal vendido em {dt}"
        if peso_abate:
            desc += f" | Peso abate: {peso_abate}kg"
        if preco_kg:
            desc += f" | Preco: R${preco_kg:.2f}/kg"
        if observacao:
            desc += f" | {observacao}"
        from database import adicionar_ocorrencia  # lazy import (evita circular)
        adicionar_ocorrencia(
            animal_id=animal_id, data=dt,
            tipo="Venda", descricao=desc,
            gravidade="Baixa", custo=0,
            dias_recuperacao=0, status="Resolvido"
        )
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)
    return True


def registrar_receita_parcial(lote_id, data_venda, preco_arroba,
                               peso_total, frigorifico="", obs=""):
    """Registra receita de venda parcial no lote SEM encerrar o ciclo.
    O lote permanece ATIVO. Diferente de registrar_venda_lote que encerra.
    """
    p = _ph()
    arrobas = peso_total * 0.5 / 15
    receita = arrobas * preco_arroba
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            # Lançar como custo negativo (receita) na tabela custos_lote
            # Tentar com owner_id; se falhar, inserir sem
            _desc = f"Venda parcial — {frigorifico or 'sem frigorífico'} | {obs or ''}"
            try:
                cur.execute(
                    f"INSERT INTO custos_lote "
                    f"(lote_id, categoria, descricao, valor, data_lancamento) "
                    f"VALUES ({p},'venda_parcial',{p},{p},{p})",
                    (lote_id, _desc, -round(receita, 2), data_venda)
                )
            except Exception:
                pass
            conn.commit()
        _log_db.info(
            "Receita parcial lote %s: R$ %.2f (%.1f@ @ R$ %.2f)",
            lote_id, receita, arrobas, preco_arroba
        )
        return True, round(receita, 2), round(arrobas, 2)
    except Exception as _e:
        _log_err.error("registrar_receita_parcial: %s", _e)
        return False, 0, 0


def venda_parcial_lote(lote_id, animal_ids, preco_kg=0,
                       peso_total=0, frigorifico="",
                       data_venda=None, observacao=""):
    """Venda parcial: marca animais selecionados como VENDIDO.
    Registra a venda proporcional. Lote continua ativo."""
    from datetime import date
    dt = str(data_venda or date.today())

    # Calcular preco_arroba e peso médio por animal
    _preco_arr = preco_kg * 15 / 0.5 if preco_kg else 0
    _n = len(animal_ids)
    _peso_por_animal = peso_total / _n if _n and peso_total else 0

    # Marcar cada animal com dados completos de venda
    for aid in animal_ids:
        marcar_animal_vendido(
            aid, data_venda=dt,
            preco_kg=preco_kg,
            peso_abate=_peso_por_animal,
            preco_arroba=_preco_arr,
            frigorifico=frigorifico or "",
            observacao=f"Venda parcial | {frigorifico or ''}"
        )

    # Registrar receita parcial SEM encerrar o lote
    n = len(animal_ids)
    if peso_total > 0 and preco_kg > 0:
        _preco_arroba = preco_kg * 15 / 0.5
        registrar_receita_parcial(
            lote_id=lote_id,
            data_venda=dt,
            preco_arroba=_preco_arroba,
            peso_total=peso_total,
            frigorifico=frigorifico or "",
            obs=f"Venda parcial ({n} animais) | {observacao or ''}"
        )

    # Verificar se restaram animais ativos — se nao, encerrar lote
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT COUNT(*) FROM animais "
            f"WHERE lote_id={p} AND ativo=1",
            (lote_id,)
        )
        restantes = cur.fetchone()[0]

    # Não encerrar automaticamente — usuário deve usar "Vender lote inteiro"
    # para encerrar o ciclo completo com status VENDIDO
    if restantes == 0:
        # Avisar mas não encerrar — lote fica com 0 animais ativos
        _log_db.info(
            "Venda parcial: lote %s com 0 animais ativos. "
            "Use 'Vender lote inteiro' para encerrar o ciclo.",
            lote_id
        )

    return {"n_vendidos": n, "restantes": restantes}


def listar_vendas_lote(lote_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT id,lote_id,data_venda,preco_venda_kg,peso_total_kg,frigorific,observacao FROM vendas_lote WHERE lote_id={p} ORDER BY data_venda DESC", (lote_id,))
        rows = _fetch(cur)
        return [(r["id"],r["lote_id"],r["data_venda"],r["preco_venda_kg"],r["peso_total_kg"],r["frigorific"],r["observacao"]) for r in rows]


def registrar_venda_lote(lote_id, data_venda, preco_arroba,
                          peso_venda_total, frigorifico="",
                          gta_numero="", obs=""):
    """Registra a venda de um lote e calcula a receita automaticamente.
    Status muda para VENDIDO e lote sai do workspace ativo.
    """
    p = _ph()
    arrobas = peso_venda_total * 0.5 / 15
    receita = arrobas * preco_arroba

    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"UPDATE lotes SET "
                f"status={p}, ativo=0, "
                f"data_venda={p}, preco_arroba={p}, "
                f"peso_venda_total={p}, frigorifico={p}, "
                f"gta_numero={p}, obs_venda={p}, "
                f"receita_venda={p} "
                f"WHERE id={p}",
                ("VENDIDO", data_venda, preco_arroba,
                 peso_venda_total, frigorifico or "",
                 gta_numero or "", obs or "",
                 round(receita, 2), lote_id)
            )
            conn.commit()
        _log_db.info(
            "Lote %s vendido: R$ %.2f (%.1f arrobas @ R$ %.2f)",
            lote_id, receita, arrobas, preco_arroba
        )
        return True, receita, arrobas
    except Exception as _e:
        _log_err.error("registrar_venda_lote: %s", _e)
        return False, 0, 0


def marcar_em_venda(lote_id):
    """Muda status para EM_VENDA — negociação em andamento."""
    p = _ph()
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"UPDATE lotes SET status={p} WHERE id={p}",
                ("EM_VENDA", lote_id)
            )
            conn.commit()
        return True
    except Exception as _e:
        _log_err.error("marcar_em_venda: %s", _e)
        return False


def cancelar_venda_lote(lote_id):
    """Reverte EM_VENDA → ATIVO."""
    p = _ph()
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"UPDATE lotes SET status={p}, ativo=1 WHERE id={p}",
                ("ATIVO", lote_id)
            )
            conn.commit()
        return True
    except Exception as _e:
        _log_err.error("cancelar_venda_lote: %s", _e)
        return False


def listar_lotes_historico(owner_id):
    """Lista lotes VENDIDOS e ARQUIVADOS para o histórico."""
    p = _ph()
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT id,nome,descricao,data_entrada,qtd_comprada,"
                f"qtd_recebida,transporte,"
                f"COALESCE(tipo_alimentacao,''),COALESCE(tipo_dieta,''),"
                f"COALESCE(preco_por_animal,0),COALESCE(data_venda,''),"
                f"COALESCE(owner_id,0),COALESCE(status,'ATIVO'),"
                f"COALESCE(preco_arroba,0),COALESCE(peso_venda_total,0),"
                f"COALESCE(frigorifico,''),COALESCE(gta_numero,''),"
                f"COALESCE(receita_venda,0),COALESCE(obs_venda,'') "
                f"FROM lotes "
                f"WHERE owner_id={p} AND status IN ('VENDIDO','ARQUIVADO') "
                f"ORDER BY data_venda DESC",
                (owner_id,)
            )
            return cur.fetchall()
    except Exception as _e:
        _log_err.error("listar_lotes_historico: %s", _e)
        return []


def obter_resumo_venda_lote(lote_id):
    """Retorna dados completos da venda + custos para DRE automático."""
    p = _ph()
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT id,nome,data_entrada,data_venda,"
                f"COALESCE(preco_por_animal,0) as custo_compra_por_animal,"
                f"COALESCE(qtd_recebida,0) as qtd,"
                f"COALESCE(preco_arroba,0),COALESCE(peso_venda_total,0),"
                f"COALESCE(frigorifico,''),COALESCE(gta_numero,''),"
                f"COALESCE(receita_venda,0),COALESCE(obs_venda,'')"
                f" FROM lotes WHERE id={p}",
                (lote_id,)
            )
            lote = cur.fetchone()
            if not lote:
                return None

            # Buscar custos lançados
            cur.execute(
                f"SELECT COALESCE(SUM(valor),0) FROM custos_lote WHERE lote_id={p}",
                (lote_id,)
            )
            total_custos = (cur.fetchone() or [0])[0]

            # Buscar custos por categoria
            cur.execute(
                f"SELECT categoria, SUM(valor) FROM custos_lote "
                f"WHERE lote_id={p} GROUP BY categoria",
                (lote_id,)
            )
            custos_cats = dict(cur.fetchall())

        qtd          = lote[5] or 1
        custo_compra = lote[4] * qtd
        receita      = lote[10]
        custo_total  = custo_compra + total_custos
        margem       = receita - custo_total
        arrobas      = lote[7] * 0.5 / 15 if lote[7] else 0
        custo_arroba = custo_total / arrobas if arrobas else 0

        return {
            "lote_id":      lote_id,
            "nome":         lote[1],
            "data_entrada": lote[2],
            "data_venda":   lote[3],
            "qtd":          qtd,
            "preco_arroba": lote[6],
            "peso_total":   lote[7],
            "arrobas":      round(arrobas, 2),
            "frigorifico":  lote[8],
            "gta":          lote[9],
            "receita":      round(receita, 2),
            "custo_compra": round(custo_compra, 2),
            "custo_operacional": round(total_custos, 2),
            "custo_total":  round(custo_total, 2),
            "margem":       round(margem, 2),
            "margem_pct":   round(margem / custo_total * 100, 1) if custo_total else 0,
            "custo_arroba": round(custo_arroba, 2),
            "custos_cats":  custos_cats,
            "obs":          lote[11],
        }
    except Exception as _e:
        _log_err.error("obter_resumo_venda_lote: %s", _e)
        return None


def listar_animais_vendidos_lote(owner_id):
    """Lista animais vendidos individualmente com todos os dados da venda."""
    p = _ph()
    # Garantir que a tabela existe antes de consultar
    try:
        pk = "SERIAL PRIMARY KEY" if _usar_postgres() else "INTEGER PRIMARY KEY AUTOINCREMENT"
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS vendas_animais ("
                f"id {pk}, animal_id INTEGER NOT NULL, "
                f"lote_id INTEGER NOT NULL, owner_id INTEGER DEFAULT NULL, "
                f"data_venda TEXT NOT NULL, peso_abate REAL DEFAULT 0, "
                f"preco_arroba REAL DEFAULT 0, receita REAL DEFAULT 0, "
                f"frigorifico TEXT DEFAULT '', gta_numero TEXT DEFAULT '', "
                f"obs TEXT DEFAULT '')"
            )
            if _usar_postgres():
                for _col, _tipo in [
                    ("owner_id","INTEGER"),("peso_abate","REAL"),
                    ("preco_arroba","REAL"),("receita","REAL"),
                    ("frigorifico","TEXT"),("gta_numero","TEXT"),("obs","TEXT")
                ]:
                    try:
                        cur.execute(
                            f"ALTER TABLE vendas_animais "
                            f"ADD COLUMN IF NOT EXISTS {_col} {_tipo}"
                        )
                    except Exception:
                        pass
            conn.commit()
    except Exception:
        pass
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT a.id, a.identificacao, "
                f"COALESCE(a.raca,'') as raca, "
                f"COALESCE(a.sexo,'') as sexo, "
                f"COALESCE(a.peso_entrada,0) as peso_entrada, "
                f"l.id as lote_id, l.nome as lote_nome, "
                f"UPPER(COALESCE(l.status,'ATIVO')) as lote_status, "
                f"v.data_venda, "
                f"COALESCE(v.peso_abate,0) as peso_abate, "
                f"COALESCE(v.preco_arroba,0) as preco_arroba, "
                f"COALESCE(v.receita,0) as receita, "
                f"COALESCE(v.frigorifico,'') as frigorifico, "
                f"COALESCE(v.gta_numero,'') as gta_numero, "
                f"COALESCE(v.obs,'') as obs "
                f"FROM animais a "
                f"JOIN lotes l ON l.id = a.lote_id "
                f"LEFT JOIN vendas_animais v ON v.animal_id = a.id "
                f"WHERE l.owner_id={p} "
                f"AND UPPER(COALESCE(a.status,'ATIVO')) = 'VENDIDO' "
                f"AND UPPER(COALESCE(l.status,'ATIVO')) "
                f"NOT IN ('VENDIDO','ARQUIVADO','ENCERRADO') "
                f"ORDER BY v.data_venda DESC, l.nome, a.identificacao",
                (owner_id,)
            )
            rows = _fetch(cur)
            return [
                (r['id'], r['identificacao'], r['raca'], r['sexo'],
                 r['peso_entrada'], r['lote_id'], r['lote_nome'],
                 r['lote_status'], r['data_venda'], r['peso_abate'],
                 r['preco_arroba'], r['receita'], r['frigorifico'],
                 r['gta_numero'], r['obs'])
                for r in rows
            ] if rows else []
    except Exception as _e:
        _log_err.error("listar_animais_vendidos_lote: %s", _e)
        return []


def listar_todas_vendas(owner_id):
    """Lista todas as vendas do fazendeiro."""
    p = _ph()
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT v.id, v.lote_id, l.nome, v.data_venda,"
                f"v.preco_venda_kg, v.peso_total_kg, v.frigorific,"
                f"v.observacao, "
                f"(v.preco_venda_kg * v.peso_total_kg) as valor_liquido "
                f"FROM vendas_lote v "
                f"JOIN lotes l ON l.id=v.lote_id "
                f"WHERE l.owner_id={p} ORDER BY v.data_venda DESC",
                (owner_id,)
            )
            return cur.fetchall()
    except Exception:
        _log_war.debug('excecao tratada: %s', exc_info=True)
        return []
