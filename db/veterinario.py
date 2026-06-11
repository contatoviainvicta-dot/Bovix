# db/veterinario.py -- Modulo veterinario
# Ocorrencias, vacinas, medicamentos, piquetes, campanhas, carencias, acesso vet.
# Depende de db.core e db.schema. Deps de outros dominios via lazy import.

from datetime import date, datetime, timedelta

from db.core import _conexao, _ph, _fetch, _fetchone, _usar_postgres, _cached
from db.schema import (
    _log_db, _log_err, _log_war, _garantir_tabelas_vet,
    _garantir_colunas_vacinas_agenda, _garantir_coluna_crmv,
)


def adicionar_ocorrencia(animal_id, data, tipo, descricao, gravidade, custo, dias_recuperacao, status):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO ocorrencias (animal_id,data,tipo,descricao,gravidade,custo,dias_recuperacao,status) VALUES({p},{p},{p},{p},{p},{p},{p},{p}) RETURNING id",
                (animal_id, data, tipo, descricao, gravidade, custo, dias_recuperacao, status),
            )
            return cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO ocorrencias (animal_id,data,tipo,descricao,gravidade,custo,dias_recuperacao,status) VALUES({p},{p},{p},{p},{p},{p},{p},{p})",
                (animal_id, data, tipo, descricao, gravidade, custo, dias_recuperacao, status),
            )
            return cur.lastrowid


def listar_ocorrencias(animal_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id,animal_id,data,tipo,descricao,gravidade,custo,dias_recuperacao,status FROM ocorrencias WHERE animal_id={p} ORDER BY data ASC,id ASC",
            (animal_id,),
        )
        rows = _fetch(cur)
        return [(r["id"],r["animal_id"],r["data"],r["tipo"],r["descricao"],r["gravidade"],r["custo"],r["dias_recuperacao"],r["status"]) for r in rows]


def atualizar_ocorrencia(ocorrencia_id, tipo, descricao, gravidade, custo, dias_recuperacao, status, data=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if data:
            cur.execute(
                f"UPDATE ocorrencias SET tipo={p},descricao={p},gravidade={p},custo={p},dias_recuperacao={p},status={p},data={p} WHERE id={p}",
                (tipo, descricao, gravidade, custo, dias_recuperacao, status, data, ocorrencia_id),
            )
        else:
            cur.execute(
                f"UPDATE ocorrencias SET tipo={p},descricao={p},gravidade={p},custo={p},dias_recuperacao={p},status={p} WHERE id={p}",
                (tipo, descricao, gravidade, custo, dias_recuperacao, status, ocorrencia_id),
            )


def excluir_ocorrencia(ocorrencia_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM ocorrencias WHERE id={p}", (ocorrencia_id,))


def listar_ocorrencias_em_tratamento():
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT o.id,o.animal_id,a.identificacao,l.nome,o.data,o.tipo,o.descricao,o.gravidade,o.custo,o.dias_recuperacao,o.status"
            " FROM ocorrencias o JOIN animais a ON a.id=o.animal_id JOIN lotes l ON l.id=a.lote_id"
            " WHERE o.status='Em tratamento' ORDER BY o.data ASC"
        )
        rows = _fetch(cur)
        return [tuple(r.values()) for r in rows]


def solicitar_acesso_vet(vet_id, owner_id):
    p = _ph()
    from datetime import date as _d
    with _conexao() as conn:
        cur = conn.cursor()
        # Verificar se ja existe
        cur.execute(
            f"SELECT id,status FROM vet_fazenda_acesso WHERE vet_id={p} AND owner_id={p}",
            (vet_id, owner_id),
        )
        existente = _fetchone(cur)
        if existente:
            return dict(ok=False, msg=f'Solicitacao ja existe com status: {existente["status"]}')
        # Verificar limite de fazendas do vet
        lim = verificar_limite_fazendas(vet_id)
        if not lim['ok']:
            return dict(ok=False, msg=lim['msg'])
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO vet_fazenda_acesso (vet_id,owner_id,status,data_request)"
                f" VALUES({p},{p},'pendente',{p}) RETURNING id",
                (vet_id, owner_id, str(_d.today())),
            )
        else:
            cur.execute(
                f"INSERT INTO vet_fazenda_acesso (vet_id,owner_id,status,data_request)"
                f" VALUES({p},{p},'pendente',{p})",
                (vet_id, owner_id, str(_d.today())),
            )
        conn.commit()
    return dict(ok=True, msg='Solicitacao enviada ao administrador')


def aprovar_acesso_vet(vet_id, owner_id, admin_id, aprovar=True):
    from database import registrar_auditoria  # lazy import
    p = _ph()
    from datetime import date as _d
    status = 'aprovado' if aprovar else 'rejeitado'
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE vet_fazenda_acesso SET status={p}, aprovado_por={p},"
            f" data_aprovacao={p} WHERE vet_id={p} AND owner_id={p}",
            (status, admin_id, str(_d.today()), vet_id, owner_id),
        )
        conn.commit()
    registrar_auditoria(admin_id, f'acesso_vet_{status}', 'vet_fazenda_acesso', vet_id,
                        f'owner_id={owner_id}')
    return dict(ok=True, msg=f'Acesso {status}')


def revogar_acesso_vet(vet_id, owner_id, admin_id):
    return aprovar_acesso_vet(vet_id, owner_id, admin_id, aprovar=False)


def listar_acessos_vet(vet_id=None, owner_id=None, status=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        sql = (
            "SELECT v.id, v.vet_id, uv.nome as vet_nome, uv.email as vet_email,"
            " v.owner_id, uf.nome as fazenda_nome, uf.email as fazenda_email,"
            " v.status, v.data_request, v.data_aprovacao"
            " FROM vet_fazenda_acesso v"
            " JOIN usuarios uv ON uv.id=v.vet_id"
            " JOIN usuarios uf ON uf.id=v.owner_id"
            " WHERE 1=1"
        )
        params = []
        if vet_id:   sql += f" AND v.vet_id={p}";   params.append(vet_id)
        if owner_id: sql += f" AND v.owner_id={p}"; params.append(owner_id)
        if status:   sql += f" AND v.status={p}";   params.append(status)
        sql += " ORDER BY v.data_request DESC"
        cur.execute(sql, params)
        rows = _fetch(cur)
        return [tuple(r.values()) for r in rows]


def listar_lotes_vet(vet_id):
    from database import listar_lotes  # lazy import
    # Lotes de todas as fazendas aprovadas para o veterinario
    fazendas = listar_fazendas_do_vet(vet_id)
    if not fazendas:
        return []
    todos = []
    for fid in fazendas:
        todos.extend(listar_lotes(owner_id=fid))
    return todos


def adicionar_vacina_agenda(lote_id, nome_vacina, data_prevista, observacao="",
                           medicamento_id=None, quantidade_dose=0,
                           agendado_por=None, animal_id=None):
    """Agenda vacina. Verifica colunas existentes antes de inserir."""
    p = _ph()

    # Descobrir colunas existentes na tabela
    _cols_existentes = set()
    if _usar_postgres():
        try:
            with _conexao() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='vacinas_agenda' AND table_schema='public'"
                )
                _cols_existentes = {r[0] for r in cur.fetchall()}
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)
    cols   = ["lote_id", "nome_vacina", "data_prevista", "observacao"]
    vals   = [lote_id, nome_vacina, str(data_prevista), observacao or ""]

    # Colunas extras - incluir apenas se existirem no banco
    extras = [
        ("medicamento_id",  medicamento_id),
        ("quantidade_dose", float(quantidade_dose or 0)),
        ("agendado_por",    agendado_por),
        ("animal_id",       animal_id),
    ]
    for col, val in extras:
        if not _usar_postgres() or col in _cols_existentes:
            cols.append(col)
            vals.append(val)

    placeholders = ",".join([p] * len(cols))
    cols_str     = ",".join(cols)

    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO vacinas_agenda ({cols_str}) "
                f"VALUES({placeholders}) RETURNING id",
                tuple(vals)
            )
            vid = cur.fetchone()[0]
            conn.commit()
            return vid
        else:
            cur.execute(
                f"INSERT INTO vacinas_agenda ({cols_str}) VALUES({placeholders})",
                tuple(vals)
            )
            return cur.lastrowid


def registrar_vacina_realizada(vacina_id, data_realizada,
                               confirmado_por=None, obs_extra="",
                               animal_id_override=None):
    from database import listar_animais_por_lote  # lazy import
    """Confirma vacina: atualiza agenda, baixa no estoque de quem agendou,
    e registra ocorrencia Vacinacao nos animais do lote."""
    p = _ph()

    # Descobrir colunas existentes
    _cols = set()
    if _usar_postgres():
        try:
            with _conexao() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='vacinas_agenda' AND table_schema='public'"
                )
                _cols = {r[0] for r in cur.fetchall()}
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)
    _extras_disp = [c for c in
                    ["medicamento_id","quantidade_dose","agendado_por","animal_id"]
                    if not _cols or c in _cols]
    sel_extras_str = ("," + ",".join(_extras_disp)) if _extras_disp else ""

    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT lote_id,nome_vacina{sel_extras_str} "
            f"FROM vacinas_agenda WHERE id={p}",
            (vacina_id,)
        )
        row = cur.fetchone()

    if not row:
        return False

    # Mapear por posicao baseada nas colunas realmente buscadas
    _row_cols = ["lote_id","nome_vacina"] + _extras_disp
    _row_map  = {c: row[i] for i, c in enumerate(_row_cols)}

    lote_id   = _row_map["lote_id"]
    nome_vac  = _row_map["nome_vacina"]
    med_id    = _row_map.get("medicamento_id")
    qtd_dose  = float(_row_map.get("quantidade_dose") or 0)
    animal_id = _row_map.get("animal_id")

    # Marcar como realizada
    set_extra = ""
    set_vals  = [data_realizada]
    if ("confirmado_por" in _cols or not _cols) and confirmado_por:
        set_extra = f",confirmado_por={p}"
        set_vals.append(confirmado_por)
    set_vals.append(vacina_id)

    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE vacinas_agenda SET data_realizada={p},"
            f"status='realizado'{set_extra} WHERE id={p}",
            tuple(set_vals)
        )
        conn.commit()

    # Dar baixa no estoque do medicamento vinculado
    if med_id and qtd_dose > 0:
        try:
            atualizar_estoque(med_id, qtd_dose)
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)
    obs_ocorr = f"Vacinacao: {nome_vac}"
    if obs_extra:
        obs_ocorr += f" | {obs_extra}"

    # animal_id_override permite redefinir o alvo na confirmacao
    _animal_alvo = animal_id_override if animal_id_override is not None else animal_id
    animais_lote = listar_animais_por_lote(lote_id)
    alvos = [_animal_alvo] if _animal_alvo else [a[0] for a in animais_lote]
    for aid in alvos:
        adicionar_ocorrencia(
            animal_id=aid, data=data_realizada,
            tipo="Vacinacao", descricao=obs_ocorr,
            gravidade="Baixa", custo=0,
            dias_recuperacao=0, status="Resolvido"
        )

    invalidar_cache("listar_animais")
    invalidar_cache("listar_lotes")
    return True


def listar_vacinas_agenda(lote_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if lote_id:
            cur.execute(f"SELECT id,lote_id,nome_vacina,data_prevista,data_realizada,status,observacao FROM vacinas_agenda WHERE lote_id={p} ORDER BY data_prevista", (lote_id,))
        else:
            cur.execute("SELECT id,lote_id,nome_vacina,data_prevista,data_realizada,status,observacao FROM vacinas_agenda ORDER BY data_prevista")
        rows = _fetch(cur)
        return [(r["id"],r["lote_id"],r["nome_vacina"],r["data_prevista"],r["data_realizada"],r["status"],r["observacao"]) for r in rows]


def listar_vacinas_pendentes(owner_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if owner_id is not None:
            cur.execute(
                f"SELECT v.id,v.lote_id,l.nome,v.nome_vacina,v.data_prevista,v.status,v.observacao"
                f" FROM vacinas_agenda v JOIN lotes l ON l.id=v.lote_id"
                f" WHERE v.status='pendente' AND l.owner_id={p} ORDER BY v.data_prevista",
                (owner_id,),
            )
        else:
            cur.execute(
                "SELECT v.id,v.lote_id,l.nome,v.nome_vacina,v.data_prevista,v.status,v.observacao"
                " FROM vacinas_agenda v JOIN lotes l ON l.id=v.lote_id"
                " WHERE v.status='pendente' ORDER BY v.data_prevista"
            )
        rows = _fetch(cur)
        return [(r["id"],r["lote_id"],r["nome"],r["nome_vacina"],r["data_prevista"],r["status"],r["observacao"]) for r in rows]


def adicionar_medicamento(nome, unidade, estoque_atual, estoque_minimo, validade, custo_unitario, owner_id=None):
    if owner_id is None:
        return None
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO medicamentos (nome,unidade,estoque_atual,estoque_minimo,validade,custo_unitario,owner_id)"
                f" VALUES({p},{p},{p},{p},{p},{p},{p}) RETURNING id",
                (nome, unidade, estoque_atual, estoque_minimo, validade, custo_unitario, owner_id),
            )
            return cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO medicamentos (nome,unidade,estoque_atual,estoque_minimo,validade,custo_unitario,owner_id)"
                f" VALUES({p},{p},{p},{p},{p},{p},{p})",
                (nome, unidade, estoque_atual, estoque_minimo, validade, custo_unitario, owner_id),
            )
            return cur.lastrowid


def listar_medicamentos(owner_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if owner_id is not None:
            cur.execute(
                f"SELECT id,nome,unidade,estoque_atual,estoque_minimo,validade,custo_unitario"
                f" FROM medicamentos WHERE owner_id={p} ORDER BY nome",
                (owner_id,),
            )
        else:
            cur.execute(
                "SELECT id,nome,unidade,estoque_atual,estoque_minimo,validade,custo_unitario"
                " FROM medicamentos ORDER BY nome"
            )
        rows = _fetch(cur)
        return [(r["id"],r["nome"],r["unidade"],r["estoque_atual"],r["estoque_minimo"],r["validade"],r["custo_unitario"]) for r in rows]


def atualizar_estoque(medicamento_id, quantidade):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE medicamentos SET estoque_atual=GREATEST(0,estoque_atual-{p}) WHERE id={p}" if _usar_postgres() else f"UPDATE medicamentos SET estoque_atual=MAX(0,estoque_atual-{p}) WHERE id={p}", (quantidade, medicamento_id))


def registrar_uso_medicamento(medicamento_id, animal_id, data_uso, quantidade, ocorrencia_id=None):
    p = _ph()
    atualizar_estoque(medicamento_id, quantidade)
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(f"INSERT INTO medicamentos_uso (medicamento_id,animal_id,ocorrencia_id,data_uso,quantidade) VALUES({p},{p},{p},{p},{p}) RETURNING id", (medicamento_id, animal_id, ocorrencia_id, data_uso, quantidade))
            return cur.fetchone()[0]
        else:
            cur.execute(f"INSERT INTO medicamentos_uso (medicamento_id,animal_id,ocorrencia_id,data_uso,quantidade) VALUES({p},{p},{p},{p},{p})", (medicamento_id, animal_id, ocorrencia_id, data_uso, quantidade))
            return cur.lastrowid


def listar_medicamentos_criticos(owner_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        filtro = f" AND owner_id={p}" if owner_id is not None else ""
        params = (owner_id,) if owner_id is not None else ()
        try:
            # IMPORTANTE: parenteses para que AND owner_id se aplique a toda a condicao
            cur.execute(
                f"SELECT id,nome,unidade,estoque_atual,estoque_minimo,validade,custo_unitario FROM medicamentos"
                f" WHERE (estoque_atual<=estoque_minimo OR (validade IS NOT NULL AND {_cast_date('validade')}<={_date_add(30)}))"
                f"{filtro}",
                params,
            )
            rows = _fetch(cur)
            return [(r["id"],r["nome"],r["unidade"],r["estoque_atual"],r["estoque_minimo"],r["validade"],r["custo_unitario"]) for r in rows]
        except Exception:
            try: conn.rollback()
            except: pass
            return []


def verificar_carencia(animal_id):
    """Verifica carencia do animal em medicamentos_uso E carencias_ativas."""
    import datetime
    p  = _ph()
    hoje = datetime.date.today()
    meds = []

    # Fonte 1: medicamentos_uso (registro de uso de estoque)
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT mu.data_uso,m.nome,m.carencia_dias "
                f"FROM medicamentos_uso mu "
                f"JOIN medicamentos m ON m.id=mu.medicamento_id "
                f"WHERE mu.animal_id={p} AND m.carencia_dias>0",
                (animal_id,),
            )
            for r in _fetch(cur):
                try:
                    dt = datetime.datetime.strptime(
                        str(r["data_uso"])[:10], "%Y-%m-%d").date()
                    libera = dt + datetime.timedelta(days=int(r["carencia_dias"]))
                    if libera >= hoje:
                        meds.append(dict(
                            medicamento=r["nome"],
                            uso=str(r["data_uso"]),
                            carencia_dias=r["carencia_dias"],
                            libera_em=str(libera)
                        ))
                except Exception as _ew:
                    _log_war.debug("excecao ignorada: %s", _ew)
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT medicamento,data_aplicacao,carencia_dias,data_liberacao "
                f"FROM carencias_ativas "
                f"WHERE animal_id={p} AND ativo=1 AND data_liberacao >= {p}",
                (animal_id, str(hoje)),
            )
            for r in cur.fetchall():
                meds.append(dict(
                    medicamento=r[0],
                    uso=str(r[1]),
                    carencia_dias=r[2],
                    libera_em=str(r[3])
                ))
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)

    if not meds:
        return dict(em_carencia=False, medicamentos=[], liberado_em=None)

    liberado_em = max(m["libera_em"] for m in meds)
    return dict(em_carencia=True, medicamentos=meds, liberado_em=liberado_em)


def adicionar_piquete(nome, area_ha, capacidade_ua, fazenda_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(f"INSERT INTO piquetes (nome,area_ha,capacidade_ua,fazenda_id) VALUES({p},{p},{p},{p}) RETURNING id", (nome, area_ha, capacidade_ua, fazenda_id))
            return cur.fetchone()[0]
        else:
            cur.execute(f"INSERT INTO piquetes (nome,area_ha,capacidade_ua,fazenda_id) VALUES({p},{p},{p},{p})", (nome, area_ha, capacidade_ua, fazenda_id))
            return cur.lastrowid


def listar_piquetes(fazenda_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if fazenda_id:
            cur.execute(f"SELECT id,fazenda_id,nome,area_ha,capacidade_ua FROM piquetes WHERE fazenda_id={p} ORDER BY nome", (fazenda_id,))
        else:
            cur.execute("SELECT id,fazenda_id,nome,area_ha,capacidade_ua FROM piquetes ORDER BY nome")
        rows = _fetch(cur)
        return [(r["id"],r["fazenda_id"],r["nome"],r["area_ha"],r["capacidade_ua"]) for r in rows]


def alocar_lote_piquete(piquete_id, lote_id, data_entrada):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(f"INSERT INTO piquetes_historico (piquete_id,lote_id,entrada) VALUES({p},{p},{p}) RETURNING id", (piquete_id, lote_id, data_entrada))
            return cur.fetchone()[0]
        else:
            cur.execute(f"INSERT INTO piquetes_historico (piquete_id,lote_id,entrada) VALUES({p},{p},{p})", (piquete_id, lote_id, data_entrada))
            return cur.lastrowid


def liberar_piquete(piquete_id, data_saida):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE piquetes_historico SET saida={p} WHERE piquete_id={p} AND saida IS NULL", (data_saida, piquete_id))


def historico_piquete(piquete_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT ph.id,l.nome,ph.entrada,ph.saida FROM piquetes_historico ph JOIN lotes l ON l.id=ph.lote_id WHERE ph.piquete_id={p} ORDER BY ph.entrada DESC", (piquete_id,))
        rows = _fetch(cur)
        return [(r["id"],r["nome"],r["entrada"],r["saida"]) for r in rows]


def listar_ocorrencias_todos_animais(lote_id):
    # Uma unica query retorna todas as ocorrencias de todos os animais do lote
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT o.id,o.animal_id,o.data,o.tipo,o.descricao,"
            f"o.gravidade,o.custo,o.dias_recuperacao,o.status,a.identificacao"
            f" FROM ocorrencias o JOIN animais a ON a.id=o.animal_id"
            f" WHERE a.lote_id={p}"
            f" ORDER BY o.animal_id,o.data ASC",
            (lote_id,),
        )
        rows = _fetch(cur)
        return [(r['id'],r['animal_id'],r['data'],r['tipo'],r['descricao'],
                 r['gravidade'],r['custo'],r['dias_recuperacao'],r['status'],r['identificacao']) for r in rows]


def calcular_risco_sanitario(lote_id):
    from database import listar_animais_por_lote  # lazy import
    """
    Calcula score de risco sanitário 0-100 do lote.
    Fatores: mortalidade, ocorrencias graves, vacinas atrasadas, GMD negativo.
    Retorna: dict(score, nivel, fatores, recomendacoes)
    """
    import pandas as pd
    from datetime import date as _d

    score = 0
    fatores = []
    recomendacoes = []

    animais = listar_animais_por_lote(lote_id)
    if not animais:
        return dict(score=0, nivel='Sem dados', fatores=[], recomendacoes=[])

    total = len(animais)

    # ── Fator 1: Mortalidade ──────────────────────────────────────────────────
    mort = taxa_mortalidade_lote(lote_id)
    taxa_mort = mort['taxa']
    if taxa_mort >= 5:
        score += 35
        fatores.append(f"Mortalidade critica: {taxa_mort}%")
        recomendacoes.append("Acionar veterinario imediatamente")
    elif taxa_mort >= 3:
        score += 20
        fatores.append(f"Mortalidade elevada: {taxa_mort}%")
        recomendacoes.append("Investigar causa das mortes")
    elif taxa_mort >= 1:
        score += 10
        fatores.append(f"Mortalidade acima do normal: {taxa_mort}%")

    # ── Fator 2: Ocorrencias dos ultimos 60 dias ─────────────────────────────
    ocs = listar_ocorrencias_todos_animais(lote_id)
    from datetime import date as _dt, timedelta as _td2
    limite_60 = str(_dt.today() - _td2(days=60))
    # o[2] = data_ocorrencia
    ocs_recentes = [o for o in ocs if o[2] and str(o[2]) >= limite_60]
    graves_at  = [o for o in ocs_recentes if o[5] == 'Alta' and o[8] == 'Em tratamento']
    graves_tot = [o for o in ocs_recentes if o[5] == 'Alta']
    medias_at  = [o for o in ocs_recentes if o[5] == 'Media' and o[8] == 'Em tratamento']
    medias_tot = [o for o in ocs_recentes if o[5] == 'Media']

    if len(graves_at) >= 3:
        score += 30
        fatores.append(f"{len(graves_at)} ocorrencias graves em tratamento")
        recomendacoes.append("Revisar protocolo sanitario urgente")
    elif len(graves_at) > 0:
        score += 20
        fatores.append(f"{len(graves_at)} ocorrencia(s) grave(s) ativa(s)")
        recomendacoes.append("Monitorar animais com ocorrencias graves")
    elif len(graves_tot) >= 2:
        score += 10
        fatores.append(f"{len(graves_tot)} ocorrencias graves nos ultimos 60 dias")

    if len(medias_at) >= 5:
        score += 12
        fatores.append(f"{len(medias_at)} ocorrencias medias em tratamento")
    elif len(medias_at) > 0:
        score += 6
        fatores.append(f"{len(medias_at)} ocorrencia(s) media(s) ativa(s)")
    elif len(medias_tot) >= 3:
        score += 4
        fatores.append(f"{len(medias_tot)} ocorrencias medias nos ultimos 60 dias")

    # ── Fator 3: GMD negativo ou muito baixo ─────────────────────────────────
    gmds = list(calcular_gmds_lote(lote_id).values())
    if gmds:
        gmd_medio = sum(gmds) / len(gmds)
        negativos = sum(1 for g in gmds if g < 0)
        pct_neg = negativos / len(gmds) * 100
        if pct_neg >= 30:
            score += 20
            fatores.append(f"{pct_neg:.0f}% dos animais com GMD negativo")
            recomendacoes.append("Revisar alimentacao e saude do lote")
        elif gmd_medio < 0.3:
            score += 10
            fatores.append(f"GMD medio muito baixo: {gmd_medio:.3f} kg/dia")
            recomendacoes.append("Avaliar dieta e condicao corporal")

    # ── Fator 4: Vacinas atrasadas ────────────────────────────────────────────
    vacs = listar_vacinas_agenda(lote_id)
    hoje = str(_d.today())
    atrasadas = [v for v in vacs if v[5] == 'pendente' and str(v[4]) < hoje]
    if len(atrasadas) >= 5:
        score += 15
        fatores.append(f"{len(atrasadas)} vacinas muito atrasadas")
        recomendacoes.append("Agendar vacinacao com urgencia")
    elif len(atrasadas) > 0:
        score += 7
        fatores.append(f"{len(atrasadas)} vacina(s) em atraso")
        recomendacoes.append("Verificar calendario sanitario")

    # ── Fator 5: Animais sem pesagem ─────────────────────────────────────────
    pes_map = {}
    for p in listar_pesagens_todos_animais(lote_id):
        pes_map.setdefault(p[1], []).append(p)
    sem_peso = sum(1 for a in animais if a[0] not in pes_map)
    pct_sem = sem_peso / total * 100
    if pct_sem >= 50:
        score += 5
        fatores.append(f"{pct_sem:.0f}% dos animais sem pesagem")
        recomendacoes.append("Registrar pesagem inicial dos animais")

    # ── Nivel de risco ────────────────────────────────────────────────────────
    score = min(100, score)
    if score >= 70:   nivel = 'Critico'
    elif score >= 40: nivel = 'Alto'
    elif score >= 20: nivel = 'Medio'
    elif score >= 5:  nivel = 'Baixo'
    else:             nivel = 'Saudavel'

    if not fatores:
        fatores = ['Nenhum fator de risco identificado']
    if not recomendacoes:
        recomendacoes = ['Manter monitoramento regular']

    return dict(score=score, nivel=nivel, fatores=fatores,
                recomendacoes=recomendacoes, mortalidade=taxa_mort,
                ocorrencias_graves=len(graves_tot), gmds=gmds)


def criar_campanha(vet_id, nome, vacina, safra, data_inicio,
                  data_fim, meta_cobertura=100, observacoes=""):
    """Cria campanha de vacinacao."""
    _garantir_tabelas_vet()
    from datetime import date
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO campanhas_vacinacao "
                f"(vet_id,nome,vacina,safra,data_inicio,data_fim,"
                f"meta_cobertura,status,observacoes,criado_em) "
                f"VALUES({p},{p},{p},{p},{p},{p},{p},'ativa',{p},{p}) RETURNING id",
                (vet_id, nome, vacina, safra,
                 str(data_inicio), str(data_fim),
                 float(meta_cobertura), observacoes or "",
                 str(date.today()))
            )
            return cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO campanhas_vacinacao "
                f"(vet_id,nome,vacina,safra,data_inicio,data_fim,"
                f"meta_cobertura,status,observacoes,criado_em) "
                f"VALUES({p},{p},{p},{p},{p},{p},{p},'ativa',{p},{p})",
                (vet_id, nome, vacina, safra,
                 str(data_inicio), str(data_fim),
                 float(meta_cobertura), observacoes or "",
                 str(date.today()))
            )
            return cur.lastrowid


def listar_campanhas(vet_id):
    """Lista campanhas do vet."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id,vet_id,nome,vacina,safra,data_inicio,data_fim,"
            f"meta_cobertura,status,observacoes "
            f"FROM campanhas_vacinacao WHERE vet_id={p} "
            f"ORDER BY criado_em DESC",
            (vet_id,)
        )
        return cur.fetchall()


def adicionar_lote_campanha(campanha_id, lote_id, meta_animais):
    """Adiciona lote a campanha e agenda a vacina no calendario sanitario."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO campanha_lotes "
            f"(campanha_id,lote_id,meta_animais,vacinados,status) "
            f"VALUES({p},{p},{p},0,'pendente')",
            (campanha_id, lote_id, int(meta_animais))
        )
        conn.commit()

    # Buscar dados da campanha para agendar no calendario
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT vet_id,nome,vacina,data_inicio "
                f"FROM campanhas_vacinacao WHERE id={p}",
                (campanha_id,)
            )
            camp = cur.fetchone()
        if camp:
            vet_id, nome_camp, vacina, dt_ini = camp
            obs = f"Campanha: {nome_camp}"
            adicionar_vacina_agenda(
                lote_id=lote_id,
                nome_vacina=vacina,
                data_prevista=str(dt_ini),
                observacao=obs,
                agendado_por=vet_id
            )
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)

    return True


def listar_lotes_campanha(campanha_id):
    """Lista lotes de uma campanha com progresso."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT cl.id,cl.campanha_id,cl.lote_id,l.nome,"
            f"cl.meta_animais,cl.vacinados,cl.status,cl.data_execucao "
            f"FROM campanha_lotes cl "
            f"JOIN lotes l ON l.id=cl.lote_id "
            f"WHERE cl.campanha_id={p} ORDER BY l.nome",
            (campanha_id,)
        )
        return cur.fetchall()


def registrar_vacinacao_campanha(campanha_lote_id, vacinados, data_exec=None):
    from database import listar_animais_por_lote  # lazy import
    """Registra execucao: atualiza campanha, insere no calendario
    e registra ocorrencia Vacinacao no prontuario dos animais."""
    _garantir_tabelas_vet()
    from datetime import date
    p  = _ph()
    dt = str(data_exec or date.today())

    # 1. Buscar dados do lote e campanha (sem try/except para ver erros)
    lote_id = None
    vacina  = None
    nome_camp = None
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT cl.lote_id, c.vacina, c.nome "
            f"FROM campanha_lotes cl "
            f"JOIN campanhas_vacinacao c ON c.id=cl.campanha_id "
            f"WHERE cl.id={p}",
            (campanha_lote_id,)
        )
        row = cur.fetchone()
        if row:
            lote_id, vacina, nome_camp = row[0], row[1], row[2]

    # 2. Atualizar campanha_lotes
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE campanha_lotes SET vacinados={p},"
            f"status='concluido',data_execucao={p} WHERE id={p}",
            (int(vacinados), dt, campanha_lote_id)
        )
        conn.commit()

    if not lote_id or not vacina:
        return True

    obs_oc = f"Vacinacao em campanha: {nome_camp} | {vacina}"

    # 3. Verificar se ja existe vacina pendente no calendario para este lote
    vac_pendente = None
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT id FROM vacinas_agenda "
                f"WHERE lote_id={p} AND nome_vacina={p} "
                f"AND status='pendente' LIMIT 1",
                (lote_id, vacina)
            )
            vac_row = cur.fetchone()
            if vac_row:
                vac_pendente = vac_row[0]
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)

    if vac_pendente:
        # Confirmar vacina ja agendada
        try:
            registrar_vacina_realizada(
                vac_pendente, dt,
                obs_extra=f"Campanha: {nome_camp}"
            )
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)
    else:
        # Criar entrada ja como realizada no calendario
        try:
            vid = adicionar_vacina_agenda(
                lote_id=lote_id,
                nome_vacina=vacina,
                data_prevista=dt,
                observacao=f"Campanha: {nome_camp}"
            )
            if vid:
                # Marcar imediatamente como realizada
                with _conexao() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        f"UPDATE vacinas_agenda SET "
                        f"data_realizada={p}, status='realizado' "
                        f"WHERE id={p}",
                        (dt, vid)
                    )
                    conn.commit()
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)
    animais = listar_animais_por_lote(lote_id)
    for an in animais:
        try:
            adicionar_ocorrencia(
                animal_id=an[0], data=dt,
                tipo="Vacinacao",
                descricao=obs_oc,
                gravidade="Baixa",
                custo=0, dias_recuperacao=0,
                status="Resolvido"
            )
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)

    return True


def sincronizar_campanha_executada(campanha_lote_id, data_exec=None):
    from database import listar_animais_por_lote  # lazy import
    """Re-processa uma campanha ja executada para garantir
    que o calendario e prontuario estejam atualizados."""
    _garantir_tabelas_vet()
    from datetime import date
    p  = _ph()
    dt = str(data_exec or date.today())

    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT cl.lote_id, cl.vacinados, c.vacina, c.nome "
            f"FROM campanha_lotes cl "
            f"JOIN campanhas_vacinacao c ON c.id=cl.campanha_id "
            f"WHERE cl.id={p}",
            (campanha_lote_id,)
        )
        row = cur.fetchone()

    if not row:
        return 0

    lote_id, vacinados, vacina, nome_camp = row
    obs_oc = f"Vacinacao em campanha: {nome_camp} | {vacina}"

    # Calendário: criar entrada realizada se nao existir
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT COUNT(*) FROM vacinas_agenda "
                f"WHERE lote_id={p} AND nome_vacina={p}",
                (lote_id, vacina)
            )
            existe = cur.fetchone()[0]
        if not existe:
            vid = adicionar_vacina_agenda(
                lote_id=lote_id, nome_vacina=vacina,
                data_prevista=dt,
                observacao=f"Campanha: {nome_camp}"
            )
            if vid:
                with _conexao() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        f"UPDATE vacinas_agenda SET "
                        f"data_realizada={p}, status='realizado' WHERE id={p}",
                        (dt, vid)
                    )
                    conn.commit()
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)
    animais = listar_animais_por_lote(lote_id)
    n_criadas = 0
    for an in animais:
        try:
            with _conexao() as conn:
                cur = conn.cursor()
                cur.execute(
                    f"SELECT COUNT(*) FROM ocorrencias "
                    f"WHERE animal_id={p} AND descricao LIKE {p}",
                    (an[0], f"%{nome_camp}%")
                )
                ja_existe = cur.fetchone()[0]
            if not ja_existe:
                adicionar_ocorrencia(
                    animal_id=an[0], data=dt,
                    tipo="Vacinacao", descricao=obs_oc,
                    gravidade="Baixa", custo=0,
                    dias_recuperacao=0, status="Resolvido"
                )
                n_criadas += 1
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)

    return n_criadas


def resumo_campanha(campanha_id):
    """Retorna progresso consolidado da campanha."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT COUNT(*),COALESCE(SUM(meta_animais),0),"
            f"COALESCE(SUM(vacinados),0),"
            f"COUNT(CASE WHEN status='concluido' THEN 1 END) "
            f"FROM campanha_lotes WHERE campanha_id={p}",
            (campanha_id,)
        )
        r = cur.fetchone()
        if not r or not r[0]:
            return {"n_lotes":0,"meta":0,"vacinados":0,"concluidos":0,"pct":0}
        n_lotes, meta, vac, conc = r[0], r[1], r[2], r[3]
        pct = round(100 * vac / max(1, meta), 1)
        return {
            "n_lotes": n_lotes, "meta": meta,
            "vacinados": vac, "concluidos": conc, "pct": pct
        }


def resumo_financeiro_vet(vet_id, mes=None, ano=None):
    """Retorna resumo financeiro do vet por periodo."""
    _garantir_tabelas_vet()
    from datetime import date
    p = _ph()
    hoje = date.today()
    _mes = mes or hoje.month
    _ano = ano or hoje.year
    prefixo = f"{_ano}-{_mes:02d}"

    with _conexao() as conn:
        cur = conn.cursor()

        # Total por status
        try:
            cur.execute(
                f"SELECT status, COUNT(*), COALESCE(SUM(valor),0) "
                f"FROM honorarios_vet WHERE vet_id={p} "
                f"AND data_lancamento LIKE {p} "
                f"GROUP BY status",
                (vet_id, f"{prefixo}%")
            )
            por_status = {r[0]: {"count": r[1], "valor": float(r[2])}
                         for r in cur.fetchall()}
        except Exception:
            por_status = {}

        # Total por fazenda no mes
        try:
            cur.execute(
                f"SELECT fazenda_owner_id, COUNT(*), COALESCE(SUM(valor),0) "
                f"FROM honorarios_vet WHERE vet_id={p} "
                f"AND data_lancamento LIKE {p} "
                f"GROUP BY fazenda_owner_id ORDER BY SUM(valor) DESC",
                (vet_id, f"{prefixo}%")
            )
            por_fazenda = cur.fetchall()
        except Exception:
            por_fazenda = []

        # Ultimos 12 meses (faturamento mensal)
        try:
            if _usar_postgres():
                cur.execute(
                    f"SELECT TO_CHAR(data_lancamento::date, 'YYYY-MM') as mes,"
                    f"COALESCE(SUM(valor),0) "
                    f"FROM honorarios_vet WHERE vet_id={p} AND status!='cancelado'"
                    f"GROUP BY mes ORDER BY mes DESC LIMIT 12",
                    (vet_id,)
                )
            else:
                cur.execute(
                    f"SELECT strftime('%Y-%m',data_lancamento) as mes,"
                    f"COALESCE(SUM(valor),0) "
                    f"FROM honorarios_vet WHERE vet_id={p} AND status!='cancelado'"
                    f"GROUP BY mes ORDER BY mes DESC LIMIT 12",
                    (vet_id,)
                )
            mensal = cur.fetchall()
        except Exception:
            mensal = []

    pend  = por_status.get("pendente", {})
    pago  = por_status.get("pago",     {})
    canc  = por_status.get("cancelado",{})

    return {
        "mes":         f"{_mes:02d}/{_ano}",
        "pendente":    pend.get("valor", 0),
        "pago":        pago.get("valor", 0),
        "cancelado":   canc.get("valor", 0),
        "n_pendente":  pend.get("count", 0),
        "n_pago":      pago.get("count", 0),
        "por_fazenda": por_fazenda,
        "mensal":      mensal,
    }


def sincronizar_ocorrencias_receitas():
    from database import listar_animais_por_lote  # lazy import
    """Cria ocorrencias para receitas antigas que nao as geraram.
    Chamada uma vez para sincronizar o historico."""
    p  = _ph()
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id,vet_id,animal_id,lote_id,data_emissao,"
                "medicamento,dose,via,duracao,carencia_dias,observacoes "
                "FROM receitas ORDER BY id"
            )
            receitas = cur.fetchall()
    except Exception:
        _log_war.debug('excecao tratada: %s', exc_info=True)
        return 0

    ok = 0
    for r in receitas:
        rid, vet_id, animal_id, lote_id, dt, med, dose, via, dur, carc, obs = r
        # Verificar se ja existe ocorrencia com essa receita
        desc_check = f"Receituario #{rid}"
        alvos = []
        if animal_id:
            alvos = [animal_id]
        elif lote_id:
            alvos = [a[0] for a in listar_animais_por_lote(lote_id)]

        for aid in alvos:
            try:
                with _conexao() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        f"SELECT id FROM ocorrencias "
                        f"WHERE animal_id={p} AND descricao LIKE {p}",
                        (aid, f"%{desc_check}%")
                    )
                    if cur.fetchone():
                        continue  # Ja existe
                # Criar ocorrencia
                desc = (
                    f"Receituario #{rid} | {med} | "
                    f"Dose: {dose} | Via: {via} | Duracao: {dur}"
                )
                if carc:
                    desc += f" | Carencia: {carc} dias"
                adicionar_ocorrencia(
                    animal_id=aid, data=str(dt),
                    tipo="Medicacao", descricao=desc,
                    gravidade="Baixa", custo=0,
                    dias_recuperacao=0, status="Resolvido"
                )
                ok += 1
            except Exception as _ew:
                _log_war.debug("excecao ignorada: %s", _ew)
    return ok


def adicionar_carencia(animal_id, medicamento, data_aplicacao, carencia_dias):
    """Registra periodo de carencia para abate."""
    _garantir_tabelas_vet()
    from datetime import datetime, timedelta
    try:
        dt = datetime.strptime(str(data_aplicacao)[:10], "%Y-%m-%d").date()
    except Exception:
        from datetime import date
        dt = date.today()
    data_lib = dt + timedelta(days=int(carencia_dias))
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO carencias_ativas (animal_id,medicamento,data_aplicacao,"
            f"carencia_dias,data_liberacao,ativo) VALUES({p},{p},{p},{p},{p},1)",
            (animal_id, medicamento, str(dt), int(carencia_dias), str(data_lib))
        )
        conn.commit()
        return str(data_lib)


def listar_carencias_ativas(owner_id=None):
    """Lista animais em carencia (filtrado por dono do lote)."""
    _garantir_tabelas_vet()
    from datetime import date
    p = _ph()
    hoje = str(date.today())
    with _conexao() as conn:
        cur = conn.cursor()
        if owner_id is not None:
            cur.execute(
                f"SELECT c.id,c.animal_id,a.identificacao,c.medicamento,"
                f"c.data_aplicacao,c.carencia_dias,c.data_liberacao "
                f"FROM carencias_ativas c "
                f"JOIN animais a ON a.id=c.animal_id "
                f"WHERE c.ativo=1 AND c.data_liberacao >= {p} "
                f"AND a.lote_id IN (SELECT id FROM lotes WHERE owner_id={p}) "
                f"ORDER BY c.data_liberacao",
                (hoje, owner_id)
            )
        else:
            cur.execute(
                f"SELECT c.id,c.animal_id,a.identificacao,c.medicamento,"
                f"c.data_aplicacao,c.carencia_dias,c.data_liberacao "
                f"FROM carencias_ativas c "
                f"JOIN animais a ON a.id=c.animal_id "
                f"WHERE c.ativo=1 AND c.data_liberacao >= {p} "
                f"ORDER BY c.data_liberacao",
                (hoje,)
            )
        return cur.fetchall()


def listar_animais_em_carencia_fazendeiro(owner_id):
    """Lista todos os animais em carencia para o fazendeiro.
    Consulta carencias_ativas vinculadas aos lotes do fazendeiro."""
    import datetime
    hoje = str(datetime.date.today())
    p = _ph()
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT c.animal_id, a.identificacao, c.medicamento, "
                f"c.data_liberacao, c.carencia_dias "
                f"FROM carencias_ativas c "
                f"JOIN animais a ON a.id = c.animal_id "
                f"WHERE c.ativo = 1 AND c.data_liberacao >= {p} "
                f"AND a.lote_id IN (SELECT id FROM lotes WHERE owner_id = {p}) "
                f"ORDER BY c.data_liberacao",
                (hoje, owner_id)
            )
            return cur.fetchall()
    except Exception:
        _log_war.debug('excecao tratada: %s', exc_info=True)
        return []


def animal_em_carencia(animal_id):
    """Retorna lista de carencias ativas para o animal."""
    _garantir_tabelas_vet()
    from datetime import date
    p = _ph()
    hoje = str(date.today())
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT medicamento,data_liberacao FROM carencias_ativas "
            f"WHERE animal_id={p} AND ativo=1 AND data_liberacao >= {p} "
            f"ORDER BY data_liberacao DESC",
            (animal_id, hoje)
        )
        return cur.fetchall()
