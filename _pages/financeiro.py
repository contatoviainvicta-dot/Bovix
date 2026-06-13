# db/financeiro.py -- DRE, scores, cotacoes, margem bruta, dashboards
# Depende de db.core e db.schema. Deps de outros dominios via lazy import.

from datetime import date, datetime, timedelta

from db.core import (
    _conexao, _ph, _fetch, _fetchone, _usar_postgres, _cached,
    _date_add, _cast_date,
)
from db.schema import _log_db, _log_err, _log_war


def calcular_score_saude(animal_id):
    from database import listar_ocorrencias, listar_pesagens, listar_reproducao  # lazy import
    import pandas as pd
    pesagens = listar_pesagens(animal_id)
    gmd = 0.0
    if len(pesagens) >= 2:
        df = pd.DataFrame(pesagens, columns=["id","aid","peso","data"])
        df["data"] = pd.to_datetime(df["data"])
        df = df.sort_values("data")
        dias = (df["data"].iloc[-1] - df["data"].iloc[0]).days
        if dias > 0:
            gmd = (df["peso"].iloc[-1] - df["peso"].iloc[0]) / dias
    pts_gmd = 50 if gmd>=1.2 else 45 if gmd>=1.0 else 38 if gmd>=0.8 else 30 if gmd>=0.6 else 20 if gmd>=0.4 else 10 if gmd>=0.0 else 0
    ocs = listar_ocorrencias(animal_id)
    pen = min(35, sum(1 for o in ocs if o[5]=="Alta")*15 + sum(1 for o in ocs if o[5]=="Media")*7 + sum(1 for o in ocs if o[5]=="Baixa")*3)
    pts_oc = max(0, 35 - pen)
    repros = listar_reproducao(animal_id)
    pts_rep = 5 if repros and repros[0][5]=="negativo" else 10 if repros and repros[0][5]=="pendente" else 15
    score = pts_gmd + pts_oc + pts_rep
    classif = "Excelente" if score>=80 else "Bom" if score>=60 else "Regular" if score>=40 else "Critico"
    return dict(score=score, classificacao=classif,
                detalhes=dict(pts_gmd=pts_gmd, pts_ocorrencias=pts_oc, pts_reproducao=pts_rep, gmd=round(gmd,3), n_ocorrencias=len(ocs)))


def calcular_previsao_abate(animal_id):
    from database import listar_pesagens, obter_animal  # lazy import
    import pandas as pd
    from datetime import date as dt
    animal = obter_animal(animal_id)
    if not animal: return {}
    peso_alvo = animal[7]
    pesagens  = listar_pesagens(animal_id)
    if len(pesagens) < 2 or peso_alvo <= 0:
        return dict(erro="Necessario >= 2 pesagens e peso alvo definido")
    df = pd.DataFrame(pesagens, columns=["id","aid","peso","data"])
    df["data"] = pd.to_datetime(df["data"])
    df = df.sort_values("data")
    peso_atual = df["peso"].iloc[-1]
    dias_hist  = (df["data"].iloc[-1] - df["data"].iloc[0]).days
    if dias_hist == 0: return dict(erro="Datas de pesagem identicas")
    gmd = (peso_atual - df["peso"].iloc[0]) / dias_hist
    if gmd <= 0: return dict(erro="GMD negativo")
    if peso_atual >= peso_alvo:
        return dict(gmd=round(gmd,3), peso_atual=peso_atual, peso_alvo=peso_alvo, dias_restantes=0, data_prevista=str(dt.today()), confianca="pronto")
    dias_rest = int((peso_alvo - peso_atual) / gmd)
    data_prev = dt.today() + _td(days=dias_rest)
    confianca = "alta" if len(pesagens)>=5 else "media" if len(pesagens)>=3 else "baixa"
    return dict(gmd=round(gmd,3), peso_atual=round(peso_atual,1), peso_alvo=round(peso_alvo,1),
                dias_restantes=dias_rest, data_prevista=str(data_prev), confianca=confianca)


def salvar_cotacao(data, preco, fonte="manual"):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(f"INSERT INTO cotacoes (data,preco,fonte) VALUES({p},{p},{p}) ON CONFLICT (data) DO UPDATE SET preco=EXCLUDED.preco,fonte=EXCLUDED.fonte RETURNING id", (data, preco, fonte))
            return cur.fetchone()[0]
        else:
            cur.execute(f"INSERT INTO cotacoes (data,preco,fonte) VALUES({p},{p},{p}) ON CONFLICT(data) DO UPDATE SET preco=excluded.preco,fonte=excluded.fonte", (data, preco, fonte))
            return cur.lastrowid


def listar_cotacoes(dias=30):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if dias <= 0:
            cur.execute("SELECT id,data,preco,fonte FROM cotacoes ORDER BY data ASC")
        else:
            cur.execute(
                f"SELECT id,data,preco,fonte FROM cotacoes WHERE {_cast_date('data')}>={_date_add(dias, chr(45))} ORDER BY data ASC"
            )
        rows = _fetch(cur)
        return [(r["id"],r["data"],r["preco"],r["fonte"]) for r in rows]


def obter_ultima_cotacao():
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id,data,preco,fonte FROM cotacoes ORDER BY data DESC LIMIT 1")
        r = _fetchone(cur)
        return (r["id"],r["data"],r["preco"],r["fonte"]) if r else None


def calcular_scores_lote(lote_id):
    from database import listar_animais_por_lote, listar_pesagens_todos_animais, listar_ocorrencias_todos_animais  # lazy import
    # Calcula score de todos os animais do lote de forma agregada
    import pandas as pd
    animais = listar_animais_por_lote(lote_id)
    if not animais:
        return {}

    pesagens = listar_pesagens_todos_animais(lote_id)
    ocorrencias = listar_ocorrencias_todos_animais(lote_id)

    # Agrupar por animal_id
    pes_por_animal = {}
    for row in pesagens:
        aid = row[1]
        pes_por_animal.setdefault(aid, []).append(row)

    oc_por_animal = {}
    for row in ocorrencias:
        aid = row[1]
        oc_por_animal.setdefault(aid, []).append(row)

    scores = {}
    for a in animais:
        aid = a[0]
        ps = pes_por_animal.get(aid, [])
        ocs = oc_por_animal.get(aid, [])

        # GMD
        gmd = 0.0
        if len(ps) >= 2:
            df = pd.DataFrame(ps, columns=['id','aid','peso','data'] + (['ident'] if ps and len(ps[0]) > 4 else []))
            df['data'] = pd.to_datetime(df['data'])
            df = df.sort_values('data')
            dias = (df['data'].iloc[-1] - df['data'].iloc[0]).days
            if dias > 0:
                gmd = (df['peso'].iloc[-1] - df['peso'].iloc[0]) / dias

        pts_gmd = (50 if gmd>=1.2 else 45 if gmd>=1.0 else 38 if gmd>=0.8
                   else 30 if gmd>=0.6 else 20 if gmd>=0.4 else 10 if gmd>=0 else 0)
        pen = min(35, sum(15 if o[5]=='Alta' else 7 if o[5]=='Media' else 3 for o in ocs))
        pts_oc = max(0, 35 - pen)
        score = pts_gmd + pts_oc + 15
        classif = ("Excelente" if score>=80 else "Bom" if score>=60
                   else "Regular" if score>=40 else "Critico")
        scores[aid] = dict(score=score, classificacao=classif, gmd=round(gmd,3),
                           n_ocorrencias=len(ocs))
    return scores


def margem_bruta_lote(lote_id):
    from database import listar_animais_por_lote, listar_pesagens, obter_lote  # lazy import
    """Calcula margem bruta completa do lote.
    Retorna dict com todos os componentes financeiros."""
    from datetime import date
    p = _ph()

    # Dados básicos do lote
    lote = obter_lote(lote_id)
    if not lote:
        return {}

    nome_lote  = lote[1]
    qtd        = int(lote[5] or lote[4] or 0)  # qtd_recebida ou comprada
    preco_ua   = float(lote[9] or 0)            # preco_por_animal
    data_entr  = str(lote[3])[:10]
    data_vend  = str(lote[10])[:10] if len(lote) > 10 and lote[10] else None

    # Custo de compra
    custo_compra = preco_ua * qtd

    # Custos variáveis lançados
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT COALESCE(SUM(valor),0),categoria "
                f"FROM custos_lote WHERE lote_id={p} "
                f"GROUP BY categoria",
                (lote_id,)
            )
            custos_var = {r[1]: float(r[0]) for r in cur.fetchall()}
    except Exception:
        custos_var = {}

    total_custos_var = sum(custos_var.values())

    # Receita de venda (se lote já foi vendido)
    receita_venda = 0.0
    preco_venda_kg = 0.0
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT preco_venda_kg,peso_total_kg FROM vendas_lote "
                f"WHERE lote_id={p} ORDER BY id DESC LIMIT 1",
                (lote_id,)
            )
            row = cur.fetchone()
            if row:
                preco_venda_kg = float(row[0])
                receita_venda  = preco_venda_kg * float(row[1])
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)
    receita_projetada = 0.0
    animais = listar_animais_por_lote(lote_id)
    n_ativos = len([a for a in animais if a])
    peso_medio_atual = 0.0
    peso_medio_alvo  = 0.0

    if animais:
        pesos_atuais = []
        pesos_alvo   = []
        for a in animais:
            pes = listar_pesagens(a[0])
            if pes:
                pesos_atuais.append(float(pes[-1][2]))
            peso_alvo_a = float(a[7] or 0) if len(a) > 7 else 0
            if peso_alvo_a:
                pesos_alvo.append(peso_alvo_a)

        if pesos_atuais:
            peso_medio_atual = sum(pesos_atuais) / len(pesos_atuais)
        if pesos_alvo:
            peso_medio_alvo = sum(pesos_alvo) / len(pesos_alvo)

        # Usar cotação CEPEA ou padrão R$15/kg
        try:
            cotacao = obter_ultima_cotacao() or 15.0
        except Exception:
            cotacao = 15.0

        peso_ref = peso_medio_alvo if peso_medio_alvo > 0 else peso_medio_atual
        if peso_ref > 0 and cotacao > 0:
            # @ = arroba = 15kg
            receita_projetada = (peso_ref / 15) * cotacao * n_ativos

    # Cálculos finais
    custo_total = custo_compra + total_custos_var
    receita     = receita_venda if receita_venda > 0 else receita_projetada
    margem_r    = receita - custo_total
    margem_pct  = round(100 * margem_r / max(receita, 1), 1) if receita > 0 else 0

    # Dias no confinamento
    try:
        from datetime import datetime
        d_ini = datetime.strptime(data_entr, "%Y-%m-%d").date()
        d_ref = datetime.strptime(data_vend, "%Y-%m-%d").date()                 if data_vend else date.today()
        dias_conf = (d_ref - d_ini).days
    except Exception:
        dias_conf = 0

    return {
        "lote_id":          lote_id,
        "nome":             nome_lote,
        "n_animais":        n_ativos,
        "qtd_comprada":     qtd,
        "custo_compra":     custo_compra,
        "custo_compra_ua":  preco_ua,
        "custos_var":       custos_var,
        "total_custos_var": total_custos_var,
        "custo_total":      custo_total,
        "custo_ua":         custo_total / max(n_ativos, 1),
        "receita_venda":    receita_venda,
        "receita_projetada":receita_projetada,
        "receita":          receita,
        "vendido":          receita_venda > 0,
        "margem_r":         margem_r,
        "margem_pct":       margem_pct,
        "peso_medio_atual": round(peso_medio_atual, 1),
        "peso_medio_alvo":  round(peso_medio_alvo, 1),
        "dias_confinamento":dias_conf,
        "data_entrada":     data_entr,
        "data_venda":       data_vend,
    }


def dashboard_financeiro_fazendeiro(owner_id):
    from database import listar_lotes  # lazy import
    """Consolida todos os indicadores financeiros do fazendeiro.
    Retorna dict com KPIs, lotes e alertas."""
    from datetime import date
    p = _ph()

    # Buscar lotes: tenta owner_id direto, depois busca por fazenda_id
    lotes = listar_lotes(owner_id=owner_id)

    if not lotes:
        # Fallback: buscar lotes onde fazenda_id aponta para uma fazenda do owner
        try:
            with _conexao() as conn:
                cur = conn.cursor()
                cur.execute(
                    f"SELECT id,nome,descricao,data_entrada,qtd_comprada,"
                    f"qtd_recebida,transporte,tipo_alimentacao,tipo_dieta,"
                    f"COALESCE(preco_por_animal,0),COALESCE(data_venda,''),owner_id "
                    f"FROM lotes WHERE owner_id={p} OR id IN ("
                    f"  SELECT id FROM lotes WHERE owner_id IS NULL"
                    f") ORDER BY data_entrada DESC",
                    (owner_id,)
                )
                rows = cur.fetchall()
                lotes = [
                    (r[0],r[1],r[2],r[3],r[4],r[5],r[6],
                     r[7],r[8],float(r[9]),str(r[10]),r[11])
                    for r in rows if r[11] == owner_id or r[11] is None
                ]
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)

    if not lotes:
        return {"lotes": [], "kpis": {}, "alertas": [], "dre": {}}

    # Calcular margem de cada lote
    margens = []
    for l in lotes:
        try:
            m = margem_bruta_lote(l[0])
            if m:
                margens.append(m)
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)

    if not margens:
        return {"lotes": [], "kpis": {}, "alertas": [], "dre": {}}

    # KPIs consolidados
    total_investido  = sum(m["custo_total"] for m in margens)
    total_receita    = sum(m["receita"] for m in margens)
    total_margem     = sum(m["margem_r"] for m in margens)
    margem_media_pct = round(total_margem / max(total_receita, 1) * 100, 1)

    lotes_positivos  = [m for m in margens if m["margem_r"] >= 0]
    lotes_negativos  = [m for m in margens if m["margem_r"] < 0]
    total_animais    = sum(m["n_animais"] for m in margens)
    receita_proj     = sum(m["receita_projetada"] for m in margens
                          if not m["vendido"])
    vendidos         = [m for m in margens if m["vendido"]]
    receita_real     = sum(m["receita_venda"] for m in vendidos)

    kpis = {
        "total_lotes":       len(margens),
        "total_animais":     total_animais,
        "total_investido":   total_investido,
        "total_receita":     total_receita,
        "total_margem":      total_margem,
        "margem_pct":        margem_media_pct,
        "lotes_positivos":   len(lotes_positivos),
        "lotes_negativos":   len(lotes_negativos),
        "receita_realizada": receita_real,
        "receita_projetada": receita_proj,
        "lotes_vendidos":    len(vendidos),
    }

    # Alertas financeiros
    alertas = []
    for m in margens:
        if m["margem_pct"] < 0:
            alertas.append({
                "tipo": "perda",
                "lote": m["nome"],
                "msg":  f"Margem negativa: R$ {m['margem_r']:,.0f} "
                        f"({m['margem_pct']}%)",
                "prioridade": "alta",
            })
        elif m["margem_pct"] < 10:
            alertas.append({
                "tipo": "margem_baixa",
                "lote": m["nome"],
                "msg":  f"Margem baixa: {m['margem_pct']}% "
                        f"(R$ {m['margem_r']:,.0f})",
                "prioridade": "media",
            })
        if m["dias_confinamento"] > 180 and not m["vendido"]:
            alertas.append({
                "tipo": "prazo",
                "lote": m["nome"],
                "msg":  f"{m['dias_confinamento']} dias em confinamento "
                        f"sem venda — custos crescendo",
                "prioridade": "media",
            })

    # Ranking de lotes por margem
    ranking = sorted(margens, key=lambda x: x["margem_r"], reverse=True)

    # DRE simplificado
    dre = {
        "receita_bruta":    total_receita,
        "custo_compra":     sum(m["custo_compra"] for m in margens),
        "custos_var":       sum(m["total_custos_var"] for m in margens),
        "custo_total":      total_investido,
        "margem_bruta":     total_margem,
        "margem_bruta_pct": margem_media_pct,
    }

    return {
        "lotes":    margens,
        "kpis":     kpis,
        "alertas":  alertas,
        "ranking":  ranking,
        "dre":      dre,
    }


def dre_por_periodo(owner_id, ano=None, mes=None):
    """DRE filtrado por período (ano e/ou mês).
    Retorna dict com receitas, custos e margem do período."""
    from datetime import date
    import calendar

    hoje  = date.today()
    _ano  = ano  or hoje.year
    _mes  = mes  # None = ano inteiro

    # Montar filtro de data
    if _mes:
        dt_ini = f"{_ano}-{_mes:02d}-01"
        ultimo_dia = calendar.monthrange(_ano, _mes)[1]
        dt_fim = f"{_ano}-{_mes:02d}-{ultimo_dia:02d}"
    else:
        dt_ini = f"{_ano}-01-01"
        dt_fim = f"{_ano}-12-31"

    p = _ph()

    # Receitas de venda no período
    receitas_venda = 0.0
    n_vendas = 0
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT COALESCE(SUM(v.preco_venda_kg * v.peso_total_kg),0),"
                f"COUNT(*) "
                f"FROM vendas_lote v "
                f"JOIN lotes l ON l.id=v.lote_id "
                f"WHERE l.owner_id={p} "
                f"AND v.data_venda BETWEEN {p} AND {p}",
                (owner_id, dt_ini, dt_fim)
            )
            row = cur.fetchone()
            receitas_venda = float(row[0] or 0)
            n_vendas       = int(row[1] or 0)
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)
    custo_compra = 0.0
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT COALESCE(SUM("
                f"COALESCE(preco_por_animal,0) * "
                f"COALESCE(qtd_recebida,qtd_comprada,0)"
                f"),0) "
                f"FROM lotes "
                f"WHERE owner_id={p} "
                f"AND data_entrada BETWEEN {p} AND {p}",
                (owner_id, dt_ini, dt_fim)
            )
            custo_compra = float(cur.fetchone()[0] or 0)
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)
    custos_var  = 0.0
    custos_cats = {}
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT cl.categoria, COALESCE(SUM(cl.valor),0) "
                f"FROM custos_lote cl "
                f"JOIN lotes l ON l.id=cl.lote_id "
                f"WHERE l.owner_id={p} "
                f"AND cl.data_lancamento BETWEEN {p} AND {p} "
                f"GROUP BY cl.categoria",
                (owner_id, dt_ini, dt_fim)
            )
            for row in cur.fetchall():
                custos_cats[row[0]] = float(row[1])
            custos_var = sum(custos_cats.values())
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)

    custo_total  = custo_compra + custos_var
    margem_bruta = receitas_venda - custo_total
    margem_pct   = round(100 * margem_bruta / max(receitas_venda, 1), 1)

    return {
        "periodo":       f"{_mes:02d}/{_ano}" if _mes else str(_ano),
        "dt_ini":        dt_ini,
        "dt_fim":        dt_fim,
        "receita_venda": receitas_venda,
        "n_vendas":      n_vendas,
        "custo_compra":  custo_compra,
        "custos_var":    custos_var,
        "custos_cats":   custos_cats,
        "custo_total":   custo_total,
        "margem_bruta":  margem_bruta,
        "margem_pct":    margem_pct,
    }


def curva_resultado_mensal(owner_id, ano=None):
    """Retorna resultado mensal para gráficos.
    Lista de 12 dicts com receita, custo e margem por mês."""
    from datetime import date
    _ano = ano or date.today().year
    meses = []
    acum  = 0.0

    for m in range(1, 13):
        dre = dre_por_periodo(owner_id, ano=_ano, mes=m)
        acum += dre["margem_bruta"]
        meses.append({
            "mes":         f"{m:02d}/{_ano}",
            "mes_num":     m,
            "receita":     dre["receita_venda"],
            "custo":       dre["custo_total"],
            "margem":      dre["margem_bruta"],
            "margem_acum": acum,
        })
    return meses
