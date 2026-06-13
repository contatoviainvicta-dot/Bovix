# db/clinica.py -- Modulo clinico veterinario
# Monitoramento/exames, honorarios/receitas, protocolos sanitarios, visitas tecnicas.
# Depende de db.core e db.schema. Deps de outros dominios via lazy import.

from datetime import date, datetime, timedelta

from db.core import (
    _conexao, _ph, _fetch, _fetchone, _usar_postgres, _cached,
    _date_add, _cast_date,
)
from db.schema import _log_db, _log_err, _log_war, _garantir_tabelas_vet


def adicionar_exame(animal_id, vet_id, tipo_exame, data_coleta,
                   laboratorio="", resultado="", interpretacao="",
                   status="aguardando", alerta=0):
    from database import adicionar_ocorrencia  # lazy import
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


def adicionar_receita(vet_id, fazenda_owner_id, medicamento, dose, via, duracao,
                     animal_id=None, lote_id=None, carencia_dias=0,
                     observacoes="", crmv=""):
    from database import adicionar_ocorrencia, listar_animais_por_lote  # lazy import
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


def adicionar_protocolo(vet_id, nome, descricao="", categoria="geral"):
    """Cria novo protocolo sanitario.
    Resiliente: insere descricao apenas se a coluna existir no schema."""
    _garantir_tabelas_vet()
    from datetime import date
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        # Detectar colunas disponiveis
        cols = set()
        try:
            if _usar_postgres():
                cur.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='protocolos_sanitarios'"
                )
                cols = {r[0] for r in cur.fetchall()}
            else:
                cur.execute("PRAGMA table_info(protocolos_sanitarios)")
                cols = {r[1] for r in cur.fetchall()}
        except Exception as _ew:
            _log_war.debug("nao foi possivel ler colunas: %s", _ew)

        # Montar colunas/valores dinamicamente
        campos = ["vet_id", "nome", "categoria"]
        valores = [vet_id, nome, categoria]
        if "descricao" in cols:
            campos.append("descricao")
            valores.append(descricao or "")
        if "data_criacao" in cols:
            campos.append("data_criacao")
            valores.append(str(date.today()))
        elif "criado_em" in cols:
            campos.append("criado_em")
            valores.append(str(date.today()))

        cols_sql = ",".join(campos)
        ph_sql = ",".join([p] * len(valores))
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO protocolos_sanitarios ({cols_sql}) "
                f"VALUES({ph_sql}) RETURNING id",
                tuple(valores)
            )
            return cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO protocolos_sanitarios ({cols_sql}) VALUES({ph_sql})",
                tuple(valores)
            )
            return cur.lastrowid


def listar_protocolos(vet_id):
    """Lista protocolos do veterinario.
    Resiliente a variacoes de schema: detecta colunas existentes e
    sempre retorna 6 campos (id, vet_id, nome, descricao, categoria, data)."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        # Descobrir quais colunas a tabela realmente tem
        cols = set()
        try:
            if _usar_postgres():
                cur.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='protocolos_sanitarios'"
                )
                cols = {r[0] for r in cur.fetchall()}
            else:
                cur.execute("PRAGMA table_info(protocolos_sanitarios)")
                cols = {r[1] for r in cur.fetchall()}
        except Exception as _ew:
            _log_war.debug("nao foi possivel ler colunas: %s", _ew)

        # Montar SELECT so com colunas que existem (fallback para literais)
        col_desc = "descricao" if "descricao" in cols else "''"
        if "data_criacao" in cols:
            col_data = "data_criacao"
        elif "criado_em" in cols:
            col_data = "criado_em"
        else:
            col_data = "''"
        col_cat = "categoria" if "categoria" in cols else "'geral'"

        cur.execute(
            f"SELECT id, vet_id, nome, {col_desc}, {col_cat}, {col_data} "
            f"FROM protocolos_sanitarios WHERE vet_id={p} ORDER BY nome",
            (vet_id,)
        )
        return cur.fetchall()


def adicionar_item_protocolo(protocolo_id, ordem, tipo, nome, dia_offset, observacao=""):
    """Adiciona item (vacina/medicacao) ao protocolo.
    Mapeia para o schema real: nome->descricao, dia_offset->dia_aplicacao,
    observacao->observacoes. O parametro 'ordem' e mantido na assinatura por
    compatibilidade com as telas, mas a tabela usa dia_aplicacao para ordenar."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO protocolo_itens "
            f"(protocolo_id,tipo,descricao,dia_aplicacao,observacoes) "
            f"VALUES({p},{p},{p},{p},{p})",
            (protocolo_id, tipo, nome, int(dia_offset), observacao or "")
        )
        conn.commit()
        return True


def listar_itens_protocolo(protocolo_id):
    """Lista itens de um protocolo na ordem correta.
    Retorna 7 campos (id, protocolo_id, ordem, tipo, nome, dia, obs) mapeando
    do schema real (descricao->nome, dia_aplicacao->dia, observacoes->obs).
    Como nao ha coluna 'ordem', usa dia_aplicacao para ordenar."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, protocolo_id, dia_aplicacao, tipo, descricao, "
            f"dia_aplicacao, observacoes "
            f"FROM protocolo_itens WHERE protocolo_id={p} ORDER BY dia_aplicacao",
            (protocolo_id,)
        )
        return cur.fetchall()


def aplicar_protocolo_no_lote(protocolo_id, lote_id, data_inicio, vet_id):
    from database import adicionar_vacina_agenda  # lazy import
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
                f"objetivo,duracao_min,status,observacoes) "
                f"VALUES({p},{p},{p},{p},{p},'agendada',{p}) RETURNING id",
                (vet_id, fazenda_owner_id, str(data_visita), objetivo,
                 int(duracao_min or 60), observacoes or "")
            )
            return cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO visitas_tecnicas (vet_id,fazenda_owner_id,data_visita,"
                f"objetivo,duracao_min,status,observacoes) "
                f"VALUES({p},{p},{p},{p},{p},'agendada',{p})",
                (vet_id, fazenda_owner_id, str(data_visita), objetivo,
                 int(duracao_min or 60), observacoes or "")
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
