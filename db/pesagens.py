# db/pesagens.py -- Funcoes de pesagem e calculo de GMD
# Depende de db.core e db.schema. Funcoes de outros dominios sao
# importadas de forma lazy (dentro das funcoes) para evitar import circular.

import csv
import io
from datetime import date, datetime, timedelta

from db.core import _conexao, _ph, _fetch, _cached, _usar_postgres
from db.schema import _log_db, _log_err, _log_war


def adicionar_pesagem(animal_id, peso, data):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO pesagens (animal_id,peso,data) "
                f"VALUES({p},{p},{p}) RETURNING id",
                (animal_id, float(peso), str(data))
            )
            rid = cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO pesagens (animal_id,peso,data) "
                f"VALUES({p},{p},{p})",
                (animal_id, float(peso), str(data))
            )
            rid = cur.lastrowid
        conn.commit()
    return rid


def listar_pesagens(animal_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT id,animal_id,peso,data FROM pesagens WHERE animal_id={p} ORDER BY data ASC,id ASC", (animal_id,))
        rows = _fetch(cur)
        return [(r["id"],r["animal_id"],r["peso"],r["data"]) for r in rows]


def atualizar_pesagem(pesagem_id, peso, data):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE pesagens SET peso={p},data={p} WHERE id={p}", (peso, data, pesagem_id))


def excluir_pesagem(pesagem_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM pesagens WHERE id={p}", (pesagem_id,))


def listar_pesagens_lote(lote_id, incluir_vendidos=False):
    """Lista pesagens do lote. Por padrão exclui animais vendidos/inativos."""
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if incluir_vendidos:
            cur.execute(
                f"SELECT p.id,a.lote_id,p.peso,p.data,a.identificacao,"
                f"a.id as animal_id "
                f"FROM pesagens p JOIN animais a ON a.id=p.animal_id "
                f"WHERE a.lote_id={p} ORDER BY p.data ASC",
                (lote_id,),
            )
        else:
            # Excluir pesagens de animais vendidos ou inativos
            cur.execute(
                f"SELECT p.id,a.lote_id,p.peso,p.data,a.identificacao,"
                f"a.id as animal_id "
                f"FROM pesagens p JOIN animais a ON a.id=p.animal_id "
                f"WHERE a.lote_id={p} "
                f"AND COALESCE(a.ativo,1)=1 "
                f"AND UPPER(COALESCE(a.status,'ATIVO')) != 'VENDIDO' "
                f"ORDER BY p.data ASC",
                (lote_id,),
            )
        rows = _fetch(cur)
        return [(r["id"],r["lote_id"],r["peso"],r["data"],
                 r["identificacao"],r["animal_id"]) for r in rows]


def calcular_gmd_temporal(lote_id, janela_dias=14):
    import pandas as pd
    from database import listar_animais_por_lote  # lazy import (evita circular)
    animais = listar_animais_por_lote(lote_id)
    todos = [{"animal_id":a[0],"peso":p[2],"data":p[3]} for a in animais for p in listar_pesagens(a[0])]
    if len(todos) < 2: return []
    df = pd.DataFrame(todos)
    df["data"] = pd.to_datetime(df["data"])
    df = df.sort_values("data")
    resultado = []
    data_atual = df["data"].min() + pd.Timedelta(days=janela_dias)
    while data_atual <= df["data"].max():
        janela = df[df["data"] <= data_atual]
        gmds = []
        for aid in janela["animal_id"].unique():
            sub = janela[janela["animal_id"]==aid].sort_values("data")
            if len(sub) >= 2:
                dias = (sub["data"].iloc[-1]-sub["data"].iloc[0]).days
                if dias > 0:
                    g = (sub["peso"].iloc[-1]-sub["peso"].iloc[0])/dias
                    if 0 < g <= 2: gmds.append(g)
        if gmds: resultado.append((str(data_atual.date()), round(sum(gmds)/len(gmds),4)))
        data_atual += pd.Timedelta(days=janela_dias)
    return resultado


def listar_pesagens_todos_animais(lote_id):
    # Uma unica query retorna todas as pesagens de todos os animais do lote
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT p.id,p.animal_id,p.peso,p.data,a.identificacao"
            f" FROM pesagens p JOIN animais a ON a.id=p.animal_id"
            f" WHERE a.lote_id={p} AND COALESCE(a.ativo,1)=1"
            f" AND UPPER(COALESCE(a.status,'ATIVO')) != 'VENDIDO'"
            f" ORDER BY p.animal_id,p.data ASC",
            (lote_id,),
        )
        rows = _fetch(cur)
        return [(r['id'],r['animal_id'],r['peso'],r['data'],r['identificacao']) for r in rows]


def calcular_gmds_lote(lote_id):
    # Calcula GMD de todos os animais do lote com uma unica query
    import pandas as pd
    rows = listar_pesagens_todos_animais(lote_id)
    if not rows:
        return {}
    df = pd.DataFrame(rows, columns=['id','animal_id','peso','data','ident'])
    df['data'] = pd.to_datetime(df['data'])
    resultado = {}
    for aid, grp in df.groupby('animal_id'):
        grp = grp.sort_values('data')
        if len(grp) >= 2:
            dias = (grp['data'].iloc[-1] - grp['data'].iloc[0]).days
            if dias > 0:
                gmd = (grp['peso'].iloc[-1] - grp['peso'].iloc[0]) / dias
                resultado[aid] = round(gmd, 4)
    return resultado


def _gmd_animal(pesagens):
    """Calcula GMD medio de um animal a partir de lista de pesagens."""
    from datetime import datetime
    if len(pesagens) < 2:
        return 0.0
    try:
        # Ordenar por data
        pares = []
        for p in pesagens:
            try:
                dt = datetime.strptime(str(p[3])[:10], "%Y-%m-%d")
                pares.append((dt, float(p[2])))
            except Exception:
                _log_war.debug('excecao tratada: %s', exc_info=True)
                continue
        pares.sort(key=lambda x: x[0])
        if len(pares) < 2:
            return 0.0
        dias = (pares[-1][0] - pares[0][0]).days
        if dias <= 0:
            return 0.0
        gmd = (pares[-1][1] - pares[0][1]) / dias
        return gmd if 0 < gmd <= 3.0 else 0.0
    except Exception:
        _log_war.debug('excecao tratada: %s', exc_info=True)
        return 0.0


def importar_pesagens_csv(linhas_csv, owner_id):
    """Importa pesagens de lista de dicts.
    Colunas esperadas: identificacao (brinco), data (YYYY-MM-DD), peso.
    Retorna (n_ok, n_erro, erros)."""
    from datetime import datetime
    n_ok = n_erro = 0
    erros = []
    p = _ph()

    # Pre-carregar mapa de identificacao -> animal_id para o owner
    # Busca ampla: tenta owner_id direto e sem owner_id (lotes legados)
    mapa_animais = {}
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT a.identificacao, a.id "
                f"FROM animais a "
                f"JOIN lotes l ON l.id = a.lote_id "
                f"WHERE l.owner_id = {p} "
                f"AND COALESCE(a.ativo, 1) = 1",
                (owner_id,)
            )
            for row in cur.fetchall():
                mapa_animais[str(row[0]).strip().upper()] = row[1]
        _log_db.info(
            "importar_pesagens: mapa carregado com %d animais para owner %s",
            len(mapa_animais), owner_id
        )
    except Exception as e:
        _log_err.error("importar_pesagens: erro ao carregar mapa: %s", e)
        erros.append(f"Erro ao carregar animais: {e}")
        return n_ok, n_erro, erros

    if not mapa_animais:
        erros.append(
            f"Nenhum animal encontrado para este usuario (owner_id={owner_id}). "
            f"Cadastre os animais antes de importar pesagens."
        )
        return n_ok, n_erro, erros

    for i, linha in enumerate(linhas_csv, 1):
        try:
            ident = str(linha.get("identificacao", "")
                        or linha.get("Identificacao", "")
                        or linha.get("IDENTIFICACAO", "")).strip()
            data  = str(linha.get("data", "")
                        or linha.get("Data", "")
                        or linha.get("DATA", "")).strip()
            peso_raw = (linha.get("peso", 0)
                        or linha.get("Peso", 0)
                        or linha.get("PESO", 0) or 0)
            peso  = float(str(peso_raw).replace(",", ".") or 0)

            if not ident or not data or not peso:
                erros.append(
                    f"Linha {i}: campos vazios — "
                    f"ident='{ident}' data='{data}' peso='{peso_raw}'"
                )
                n_erro += 1
                continue

            # Normalizar data
            data_norm = data
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y",
                        "%Y/%m/%d", "%m/%d/%Y"):
                try:
                    data_norm = datetime.strptime(data, fmt).strftime("%Y-%m-%d")
                    break
                except ValueError:
                    continue

            # Buscar animal — case insensitive
            animal_id = (mapa_animais.get(ident.upper())
                         or mapa_animais.get(ident)
                         or mapa_animais.get(ident.lower()))

            if not animal_id:
                erros.append(
                    f"Linha {i}: animal '{ident}' nao encontrado. "
                    f"Disponiveis: {', '.join(list(mapa_animais.keys())[:5])}"
                )
                n_erro += 1
                continue

            adicionar_pesagem(animal_id, peso, data_norm)
            n_ok += 1
            _log_db.debug(
                "pesagem importada: animal_id=%s peso=%s data=%s",
                animal_id, peso, data_norm
            )

        except Exception as e:
            erros.append(f"Linha {i}: {e}")
            _log_err.error("importar_pesagens linha %s: %s", i, e)
            n_erro += 1

    _log_db.info(
        "importar_pesagens concluido: ok=%s erro=%s owner=%s",
        n_ok, n_erro, owner_id
    )
    return n_ok, n_erro, erros
