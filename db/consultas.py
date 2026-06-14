# db/consultas.py -- Consultas e utilitarios transversais
# Funcoes auxiliares que cruzam multiplos dominios: busca global de animais,
# contagens, status de lotes, historico clinico consolidado, calendario de
# abate, limites e sincronizacao.
# Depende de db.core e db.schema. Deps de outros dominios via lazy import.

from datetime import date, datetime, timedelta

from db.core import (
    _conexao, _ph, _fetch, _fetchone, _usar_postgres, _cached,
    _date_add, _cast_date,
    UPGRADE_MSG_FAZENDEIRO, UPGRADE_MSG_VETERINARIO,
)
from db.schema import _log_db, _log_err, _log_war


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


def listar_tratamentos_vencidos(owner_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        hoje = str(date.today())
        filtro_owner = f" AND l.owner_id={p}" if owner_id is not None else ""
        params = (owner_id,) if owner_id is not None else ()
        cur.execute(
            "SELECT o.id,o.animal_id,a.identificacao,l.nome,o.data,o.tipo,o.descricao,o.gravidade,o.custo,o.dias_recuperacao,o.status"
            " FROM ocorrencias o JOIN animais a ON a.id=o.animal_id JOIN lotes l ON l.id=a.lote_id"
            f" WHERE o.status='Em tratamento' AND o.dias_recuperacao > 0{filtro_owner}",
            params,
        )
        rows = _fetch(cur)
        vencidos = []
        for r in rows:
            try:
                dt_oc = datetime.strptime(str(r["data"])[:10], "%Y-%m-%d").date()
                dt_alta = dt_oc + timedelta(days=int(r["dias_recuperacao"] or 0))
                if dt_alta < date.today():
                    vencidos.append(tuple(r.values()))
            except Exception as _ew:
                _log_war.debug("excecao ignorada: %s", _ew)
        return vencidos


def converter_para_pago(usuario_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE usuarios SET plano='pago',plano_expira=NULL WHERE id={p}", (usuario_id,))


def verificar_limite_animais(owner_id, n_novos=0):
    from database import obter_limites_usuario  # lazy import
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


def listar_solicitacoes_pendentes():
    from database import listar_acessos_vet  # lazy import
    return listar_acessos_vet(status='pendente')


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


def atualizar_qtd_lote(lote_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM animais WHERE lote_id={p} AND COALESCE(ativo,1)=1", (lote_id,))
        n = cur.fetchone()[0]
        cur.execute(f"UPDATE lotes SET qtd_recebida={p} WHERE id={p}", (n, lote_id))
    return n


def historico_clinico_animal(animal_id):
    from database import listar_exames, listar_ocorrencias, listar_pesagens, animal_em_carencia  # lazy import
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


def calendario_abate(owner_id):
    from database import listar_animais_por_lote, listar_lotes, listar_pesagens, _gmd_animal, obter_ultima_cotacao  # lazy import
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
            cotacao = obter_ultima_cotacao() or 15.0
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


def sincronizar_todos_lotes():
    from database import listar_lotes  # lazy import
    lotes = listar_lotes()
    resultados = []
    for l in lotes:
        n = atualizar_qtd_lote(l[0])
        resultados.append((l[0], l[1], n))
    return resultados
