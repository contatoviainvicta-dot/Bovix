"""Testes de CRUD do modulo veterinario."""
import pytest


def test_lancar_e_listar_honorario(db_temp, usuario_vet, usuario_fazendeiro):
    """Lancamento de honorario aparece na listagem."""
    hid = db_temp.lancar_honorario(
        vet_id=usuario_vet,
        fazenda_owner_id=usuario_fazendeiro,
        descricao="Visita tecnica teste",
        valor=350.50,
        tipo="consulta"
    )
    assert hid is not None

    hons = db_temp.listar_honorarios(usuario_vet)
    assert len(hons) == 1
    assert hons[0][5] == "Visita tecnica teste"
    assert float(hons[0][7]) == 350.50
    assert hons[0][8] == "pendente"


def test_registrar_pagamento_honorario(db_temp, usuario_vet, usuario_fazendeiro):
    """Marcar como pago atualiza status."""
    hid = db_temp.lancar_honorario(
        vet_id=usuario_vet,
        fazenda_owner_id=usuario_fazendeiro,
        descricao="Teste pgto", valor=100, tipo="consulta"
    )
    db_temp.registrar_pagamento_honorario(hid, "PIX")

    pagos = db_temp.listar_honorarios(usuario_vet, status="pago")
    assert len(pagos) == 1
    assert pagos[0][10] == "PIX"  # forma_pagamento


def test_enviar_e_listar_mensagem(db_temp, usuario_vet, usuario_fazendeiro):
    """Mensagem enviada aparece na caixa de entrada do destinatario."""
    mid = db_temp.enviar_mensagem(
        remetente_id=usuario_vet,
        destinatario_id=usuario_fazendeiro,
        corpo="Olá, animal precisa de cuidados",
        assunto="Alerta clinico"
    )
    assert mid is not None

    entrada = db_temp.listar_mensagens(usuario_fazendeiro, caixa="entrada")
    assert len(entrada) == 1
    assert entrada[0][3] == "Alerta clinico"
    assert entrada[0][5] == 0  # lida=0

    n_nl = db_temp.contar_mensagens_nao_lidas(usuario_fazendeiro)
    assert n_nl == 1


def test_marcar_mensagem_lida(db_temp, usuario_vet, usuario_fazendeiro):
    """Marcar como lida diminui contador."""
    mid = db_temp.enviar_mensagem(
        remetente_id=usuario_vet,
        destinatario_id=usuario_fazendeiro,
        corpo="Teste", assunto=""
    )
    assert db_temp.contar_mensagens_nao_lidas(usuario_fazendeiro) == 1

    db_temp.marcar_mensagem_lida(mid)
    assert db_temp.contar_mensagens_nao_lidas(usuario_fazendeiro) == 0


def test_criar_campanha_e_listar(db_temp, usuario_vet):
    """Campanha criada aparece na lista do vet."""
    cid = db_temp.criar_campanha(
        vet_id=usuario_vet,
        nome="Aftosa 2026", vacina="Aftosa", safra="2026",
        data_inicio="2026-01-01", data_fim="2026-06-30",
        meta_cobertura=100
    )
    assert cid is not None

    camps = db_temp.listar_campanhas(usuario_vet)
    assert len(camps) == 1
    assert camps[0][2] == "Aftosa 2026"


def test_resumo_financeiro_vet_calcula_totais(db_temp, usuario_vet, usuario_fazendeiro):
    """Resumo financeiro soma honorarios corretamente."""
    # Lancar 3 honorarios
    h1 = db_temp.lancar_honorario(
        vet_id=usuario_vet, fazenda_owner_id=usuario_fazendeiro,
        descricao="Visita 1", valor=200, tipo="consulta"
    )
    h2 = db_temp.lancar_honorario(
        vet_id=usuario_vet, fazenda_owner_id=usuario_fazendeiro,
        descricao="Visita 2", valor=300, tipo="consulta"
    )
    h3 = db_temp.lancar_honorario(
        vet_id=usuario_vet, fazenda_owner_id=usuario_fazendeiro,
        descricao="Visita 3", valor=500, tipo="consulta"
    )

    # Marcar 1 como pago
    db_temp.registrar_pagamento_honorario(h1, "PIX")

    res = db_temp.resumo_financeiro_vet(usuario_vet)
    assert res["pago"] == 200
    assert res["pendente"] == 800  # 300 + 500
