# db/animais.py -- Cadastro e gestao de animais
# Modulo isolado. Depende apenas de db.core e db.schema.

import csv
import io

from db.core import _conexao, _ph, _fetch, _fetchone, _usar_postgres, _cached
from db.schema import _log_db, _log_err, _log_war

# Status validos para animais
STATUS_ANIMAL = ['ATIVO', 'VENDIDO', 'MORTO', 'TRANSFERIDO', 'DESCARTADO']


def listar_animais(incluir_inativos=False):
    with _conexao() as conn:
        cur = conn.cursor()
        sql = "SELECT id,identificacao,idade,lote_id FROM animais"
        if not incluir_inativos:
            sql += " WHERE COALESCE(ativo,1)=1"
        sql += " ORDER BY id"
        cur.execute(sql)
        rows = _fetch(cur)
        return [(r["id"],r["identificacao"],r["idade"],r["lote_id"]) for r in rows]


def listar_animais_por_lote(lote_id, incluir_inativos=False):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if incluir_inativos:
            cur.execute(f"SELECT id,identificacao,idade,lote_id FROM animais WHERE lote_id={p} ORDER BY id", (lote_id,))
        else:
            cur.execute(
                f"SELECT id,identificacao,idade,lote_id FROM animais "
                f"WHERE lote_id={p} "
                f"AND COALESCE(ativo,1)=1 "
                f"AND UPPER(COALESCE(status,'ATIVO')) != 'VENDIDO' "
                f"ORDER BY id",
                (lote_id,)
            )
        rows = _fetch(cur)
        return [(r["id"],r["identificacao"],r["idade"],r["lote_id"]) for r in rows]


def adicionar_animal(identificacao, idade, lote_id, sexo="indefinido",
                     raca="", peso_entrada=0.0, peso_alvo=0.0, observacoes=""):
    """Cadastra um novo animal no lote."""
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO animais (identificacao,idade,lote_id,sexo,raca,"
                f"peso_entrada,peso_alvo,observacoes,ativo,status) "
                f"VALUES({p},{p},{p},{p},{p},{p},{p},{p},1,'ATIVO') RETURNING id",
                (str(identificacao), int(idade or 0), int(lote_id),
                 sexo or "indefinido", raca or "",
                 float(peso_entrada or 0), float(peso_alvo or 0),
                 observacoes or "")
            )
            return cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO animais (identificacao,idade,lote_id,sexo,raca,"
                f"peso_entrada,peso_alvo,observacoes,ativo,status) "
                f"VALUES({p},{p},{p},{p},{p},{p},{p},{p},1,'ATIVO')",
                (str(identificacao), int(idade or 0), int(lote_id),
                 sexo or "indefinido", raca or "",
                 float(peso_entrada or 0), float(peso_alvo or 0),
                 observacoes or "")
            )
            return cur.lastrowid


def obter_animal(animal_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id,identificacao,idade,lote_id,"
            f"COALESCE(sexo,'indefinido') as sexo,COALESCE(raca,'') as raca,"
            f"COALESCE(peso_entrada,0) as peso_entrada,COALESCE(peso_alvo,0) as peso_alvo,"
            f"COALESCE(observacoes,'') as observacoes,foto_path FROM animais WHERE id={p}",
            (animal_id,),
        )
        r = _fetchone(cur)
        return (r["id"],r["identificacao"],r["idade"],r["lote_id"],r["sexo"],r["raca"],r["peso_entrada"],r["peso_alvo"],r["observacoes"],r["foto_path"]) if r else None


def atualizar_animal(animal_id, identificacao, idade, raca="", sexo="indefinido",
                     peso_entrada=0.0, peso_alvo=0.0, observacoes=""):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE animais SET identificacao={p}, idade={p}, raca={p}, "
            f"sexo={p}, peso_entrada={p}, peso_alvo={p}, observacoes={p} "
            f"WHERE id={p}",
            (identificacao, idade, raca, sexo,
             peso_entrada, peso_alvo, observacoes, animal_id)
        )


def excluir_animal(animal_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM animais WHERE id={p}", (animal_id,))


def atualizar_status_animal(animal_id, status):
    p = _ph()
    ativo = 1 if status == 'ATIVO' else 0
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE animais SET status={p}, ativo={p} WHERE id={p}",
            (status, ativo, animal_id),
        )


def listar_animais_por_status(lote_id, status=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if status and status.upper() == 'VENDIDO':
            # Mostrar só vendidos — para histórico/relatório
            cur.execute(
                f"SELECT id,identificacao,idade,lote_id,"
                f"UPPER(COALESCE(status,'ATIVO')) as status"
                f" FROM animais WHERE lote_id={p}"
                f" AND UPPER(COALESCE(status,'ATIVO'))='VENDIDO'"
                f" ORDER BY id",
                (lote_id,),
            )
        elif status:
            # Filtro específico — excluindo VENDIDO dos ativos
            cur.execute(
                f"SELECT id,identificacao,idade,lote_id,"
                f"UPPER(COALESCE(status,'ATIVO')) as status"
                f" FROM animais WHERE lote_id={p}"
                f" AND UPPER(COALESCE(status,'ATIVO'))=UPPER({p})"
                f" ORDER BY id",
                (lote_id, status),
            )
        else:
            # Sem filtro — excluir VENDIDO (padrão do workspace)
            cur.execute(
                f"SELECT id,identificacao,idade,lote_id,"
                f"UPPER(COALESCE(status,'ATIVO')) as status"
                f" FROM animais WHERE lote_id={p}"
                f" AND UPPER(COALESCE(status,'ATIVO')) != 'VENDIDO'"
                f" ORDER BY id",
                (lote_id,),
            )
        rows = _fetch(cur)
        return [(r['id'],r['identificacao'],r['idade'],r['lote_id'],r['status'])
                for r in rows]


def contagem_status_animais(lote_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT COALESCE(status,'ATIVO') as status, COUNT(*) as total"
            f" FROM animais WHERE lote_id={p} GROUP BY COALESCE(status,'ATIVO')",
            (lote_id,),
        )
        rows = _fetch(cur)
        base = {s: 0 for s in STATUS_ANIMAL}
        for r in rows:
            base[r['status']] = r['total']
        return base


# Status válidos para lotes
STATUS_LOTE = ['ATIVO', 'ENCERRADO', 'QUARENTENA', 'VENDIDO', 'CRITICO']


def importar_animais_csv(linhas, lote_id):
    ok = erros = 0; msgs = []
    existentes = {a[1] for a in listar_animais_por_lote(lote_id)}
    for i, linha in enumerate(linhas, 1):
        try:
            ident = str(linha.get("identificacao","")).strip()
            if not ident: erros+=1; msgs.append(f"Linha {i}: vazio"); continue
            if ident in existentes: erros+=1; msgs.append(f"Linha {i}: {ident} existe"); continue
            idade = int(float(str(linha.get("idade",0)).replace(",",".") or 0))
            aid = adicionar_animal(ident, idade, lote_id)
            pa = float(str(linha.get("peso_alvo",0)).replace(",",".") or 0)
            ob = str(linha.get("observacoes",""))
            from database import atualizar_animal_detalhes  # lazy
            atualizar_animal_detalhes(aid, peso_alvo=pa if pa>0 else None, observacoes=ob if ob else None)
            existentes.add(ident); ok += 1
        except Exception as e:
            erros+=1; msgs.append(f"Linha {i}: {e}")
    if ok > 0:
        from database import atualizar_qtd_lote  # lazy
        atualizar_qtd_lote(lote_id)
    return dict(importados=ok, erros=erros, mensagens=msgs)
