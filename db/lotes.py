# db/lotes.py -- Gestao de lotes, custos e ciclo de vida
# Depende de db.core e db.schema.
# listar_animais_por_lote: lazy import para evitar circular.

from db.core import _conexao, _ph, _fetch, _fetchone, _usar_postgres, _cached
from db.schema import _log_db, _log_err, _log_war


def adicionar_lote(nome, descricao, data_entrada, qtd_comprada, qtd_recebida, transporte, owner_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO lotes (nome,descricao,data_entrada,qtd_comprada,qtd_recebida,transporte,owner_id)"
                f" VALUES({p},{p},{p},{p},{p},{p},{p}) RETURNING id",
                (nome, descricao, data_entrada, qtd_comprada, qtd_recebida, transporte, owner_id),
            )
            return cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO lotes (nome,descricao,data_entrada,qtd_comprada,qtd_recebida,transporte,owner_id)"
                f" VALUES({p},{p},{p},{p},{p},{p},{p})",
                (nome, descricao, data_entrada, qtd_comprada, qtd_recebida, transporte, owner_id),
            )
            return cur.lastrowid


def listar_lotes(owner_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if owner_id is not None:
            cur.execute(
                f"SELECT id,nome,descricao,data_entrada,qtd_comprada,"
                f"qtd_recebida,transporte,"
                f"COALESCE(tipo_alimentacao,''),COALESCE(tipo_dieta,''),"
                f"COALESCE(preco_por_animal,0),COALESCE(data_venda,''),"
                f"COALESCE(owner_id,0),"
                f"COALESCE(status,'ATIVO') "
                f"FROM lotes WHERE owner_id={p} "
                f"AND COALESCE(ativo,1)=1 "
                f"AND UPPER(COALESCE(status,'ATIVO')) "
                f"NOT IN ('VENDIDO','ARQUIVADO','ENCERRADO') "
                f"ORDER BY data_entrada DESC,id DESC",
                (owner_id,),
            )
        else:
            cur.execute(
                "SELECT id,nome,descricao,data_entrada,qtd_comprada,"
                "qtd_recebida,transporte,"
                "COALESCE(tipo_alimentacao,''),COALESCE(tipo_dieta,''),"
                "COALESCE(preco_por_animal,0),COALESCE(data_venda,''),"
                "COALESCE(owner_id,0) "
                "FROM lotes ORDER BY data_entrada DESC,id DESC"
            )
        # Usar fetchall() com indices posicionais para evitar KeyError
        rows = cur.fetchall()
        return [
            (r[0],r[1],r[2],r[3],r[4],r[5],r[6],
             r[7],r[8],float(r[9] or 0),str(r[10] or ''),r[11],
             str(r[12] or 'ATIVO'))
            for r in rows
        ]


def obter_lote(lote_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id,nome,descricao,data_entrada,qtd_comprada,qtd_recebida,"
            f"transporte,"
            f"COALESCE(tipo_alimentacao,''),COALESCE(tipo_dieta,''),"
            f"COALESCE(preco_por_animal,0),COALESCE(data_venda,''),"
            f"COALESCE(owner_id,0) "
            f"FROM lotes WHERE id={p}",
            (lote_id,)
        )
        r = cur.fetchone()
        if not r:
            return None
        return (
            r[0],r[1],r[2],r[3],r[4],r[5],r[6],
            r[7],r[8],float(r[9] or 0),str(r[10] or ''),r[11]
        )


def atualizar_lote(lote_id, nome, descricao, data_entrada, qtd_comprada, qtd_recebida, transporte, preco_por_animal=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT COUNT(*) FROM animais "
            f"WHERE lote_id={p} "
            f"AND COALESCE(ativo,1)=1 "
            f"AND UPPER(COALESCE(status,'ATIVO')) NOT IN ('VENDIDO','MORTO','DESCARTADO')",
            (lote_id,)
        )
        ativos = cur.fetchone()[0]
        if preco_por_animal is not None:
            cur.execute(
                f"UPDATE lotes SET nome={p},descricao={p},data_entrada={p},"
                f"qtd_comprada={p},qtd_recebida={p},transporte={p},"
                f"preco_por_animal={p} WHERE id={p}",
                (nome, descricao, data_entrada, qtd_comprada, ativos,
                 transporte, preco_por_animal, lote_id),
            )
        else:
            cur.execute(
                f"UPDATE lotes SET nome={p},descricao={p},data_entrada={p},"
                f"qtd_comprada={p},qtd_recebida={p},transporte={p} WHERE id={p}",
                (nome, descricao, data_entrada, qtd_comprada, ativos,
                 transporte, lote_id),
            )


def excluir_lote(lote_id):
    """Exclui lote com cada passo em transacao independente."""
    p = _ph()

    # Passo 1: buscar animais
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT id FROM animais WHERE lote_id={p}", (lote_id,))
        aids = [r[0] for r in cur.fetchall()]

    # Passo 2: excluir registros dos animais
    for aid in aids:
        for tbl in ['pesagens', 'ocorrencias', 'medicamentos_uso']:
            try:
                with _conexao() as conn:
                    cur = conn.cursor()
                    cur.execute(f"DELETE FROM {tbl} WHERE animal_id={p}", (aid,))
                    conn.commit()
            except Exception as _ew:
                _log_war.debug("excecao ignorada: %s", _ew)
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(f"DELETE FROM animais WHERE lote_id={p}", (lote_id,))
            conn.commit()
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)
    for tbl in ['vacinas_agenda', 'reproducao', 'vendas_lote']:
        try:
            with _conexao() as conn:
                cur = conn.cursor()
                cur.execute(f"DELETE FROM {tbl} WHERE lote_id={p}", (lote_id,))
                conn.commit()
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM lotes WHERE id={p}", (lote_id,))
        conn.commit()


def atualizar_status_lote(lote_id, status):
    p = _ph()
    ativo = 1 if status == 'ATIVO' else 0
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE lotes SET status={p}, ativo={p} WHERE id={p}",
            (status, ativo, lote_id),
        )


def verificar_limite_fazendas(vet_id):
    limites = obter_limites_usuario(vet_id)
    if not limites: return dict(ok=False, atual=0, limite=0, msg='Usuario nao encontrado')
    if limites['perfil'] == 'admin': return dict(ok=True, atual=0, limite=9999, msg='Admin sem limite')
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT COUNT(*) FROM vet_fazenda_acesso WHERE vet_id={p} AND status='aprovado'",
            (vet_id,),
        )
        atual = cur.fetchone()[0]
    limite = limites['limite_fazendas']
    return dict(ok=atual < limite, atual=atual, limite=limite,
                msg=f'{atual}/{limite} fazendas' if atual < limite else f'Limite atingido ({limite} fazendas)')


def encerrar_lote(lote_id, data_encerramento=None, motivo="venda_total"):
    """Encerra lote: marca todos animais como VENDIDO e lote como encerrado."""
    from datetime import date
    p  = _ph()
    dt = str(data_encerramento or date.today())

    # Marcar todos os animais ativos como vendidos
    from database import listar_animais_por_lote  # lazy import
    animais = listar_animais_por_lote(lote_id)
    for a in animais:
        if a and len(a) > 0:
            try:
                marcar_animal_vendido(a[0], data_venda=dt)
            except Exception as _ew:
                _log_war.debug("excecao ignorada: %s", _ew)
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE lotes SET status='encerrado', ativo=0, "
            f"data_venda={p} WHERE id={p}",
            (dt, lote_id)
        )
        conn.commit()
    invalidar_cache("listar_lotes")
    return True


def calcular_margem_lote(lote_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        lote = obter_lote(lote_id)
        if not lote: return {}
        cur.execute(f"SELECT COALESCE(preco_por_animal,0) FROM lotes WHERE id={p}", (lote_id,))
        preco_animal = cur.fetchone()[0]
        custo_compra = preco_animal * lote[5]
        cur.execute(f"SELECT preco_venda_kg,peso_total_kg,data_venda,frigorific FROM vendas_lote WHERE lote_id={p} ORDER BY id DESC LIMIT 1", (lote_id,))
        venda = cur.fetchone()
        receita_real = (venda[0]*venda[1]) if venda else 0.0
        from database import listar_animais_por_lote  # lazy import
        animais = listar_animais_por_lote(lote_id)
        custo_san = sum(o[6] for a in animais for o in listar_ocorrencias(a[0]) if o[6])
        margem = receita_real - custo_compra - custo_san
        margem_pct = (margem/custo_compra*100) if custo_compra > 0 else 0
    return dict(custo_compra=round(custo_compra,2), receita_real=round(receita_real,2),
                custo_sanitario=round(custo_san,2), margem=round(margem,2), margem_pct=round(margem_pct,1),
                data_venda=venda[2] if venda else None, frigorific=venda[3] if venda else "",
                venda_registrada=venda is not None)


def resumo_lote(lote_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM animais WHERE lote_id={p} AND COALESCE(ativo,1)=1", (lote_id,))
        ativos = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM mortalidade m JOIN animais a ON a.id=m.animal_id WHERE a.lote_id={p}", (lote_id,))
        mortos = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM animais WHERE lote_id={p}", (lote_id,))
        total = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*),COALESCE(SUM(quantidade),0) FROM gta WHERE lote_id={p}", (lote_id,))
        gtas = cur.fetchone()
        cur.execute(f"SELECT COALESCE(SUM(o.custo),0) FROM ocorrencias o JOIN animais a ON a.id=o.animal_id WHERE a.lote_id={p}", (lote_id,))
        custo = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM ocorrencias o JOIN animais a ON a.id=o.animal_id WHERE a.lote_id={p}", (lote_id,))
        ocorr = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM vacinas_agenda WHERE lote_id={p} AND status='pendente'", (lote_id,))
        vac_pend = cur.fetchone()[0]
    return dict(total_animais=total, ativos=ativos, mortos=mortos,
                gtas_emitidas=gtas[0], animais_saida_gta=int(gtas[1]),
                ocorrencias=ocorr, custo_sanitario=round(float(custo),2), vacinas_pendentes=vac_pend)


def adicionar_custo_lote(lote_id, categoria, descricao, valor,
                         data_lancamento, observacoes=""):
    """Lança custo variável no lote (ração, medicamento, frete, etc)."""
    _garantir_tabelas_vet()
    from datetime import date
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO custos_lote "
                f"(lote_id,categoria,descricao,valor,data_lancamento,observacoes)"
                f" VALUES({p},{p},{p},{p},{p},{p}) RETURNING id",
                (lote_id, categoria, descricao, float(valor),
                 str(data_lancamento or date.today()), observacoes or "")
            )
            rid = cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO custos_lote "
                f"(lote_id,categoria,descricao,valor,data_lancamento,observacoes)"
                f" VALUES({p},{p},{p},{p},{p},{p})",
                (lote_id, categoria, descricao, float(valor),
                 str(data_lancamento or date.today()), observacoes or "")
            )
            rid = cur.lastrowid
        conn.commit()
    _log_db.info("custo_lote inserido id=%s lote=%s valor=%s", rid, lote_id, valor)
    return rid


def listar_custos_lote(lote_id):
    """Lista todos os custos de um lote."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id,lote_id,categoria,descricao,valor,"
            f"data_lancamento,observacoes "
            f"FROM custos_lote WHERE lote_id={p} ORDER BY data_lancamento DESC",
            (lote_id,)
        )
        return cur.fetchall()
