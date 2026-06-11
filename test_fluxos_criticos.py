"""
Suíte de testes dos fluxos críticos do Auroque.

Cobre: login/cadastro, lote, animal, pesagem e venda (total e parcial).
Roda contra SQLite em memória — isolado, rápido, sem tocar o banco real.

Como rodar:
    pytest test_fluxos_criticos.py -v
    pytest test_fluxos_criticos.py -v -k login    # só testes de login
    pytest test_fluxos_criticos.py -x              # para no primeiro erro

Requer: pytest, bcrypt (já no requirements.txt)
"""

import os
import sys
import importlib
import pytest

# Forçar SQLite (sem DATABASE_URL) e isolar o módulo
os.environ["DATABASE_URL"] = ""
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Recarrega o módulo database com um SQLite limpo a cada teste."""
    # Banco isolado por teste — arquivo único no diretório temporário
    db_file = tmp_path / "teste.db"

    # IMPORTANTE: setar as variáveis ANTES de importar o módulo,
    # pois o caminho do banco é resolvido na hora da conexão
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("AUROQUE_DB_PATH", str(db_file))

    # Remover qualquer versão em cache do módulo
    for mod in list(sys.modules.keys()):
        if "database" in mod:
            del sys.modules[mod]

    import database as _db
    importlib.reload(_db)

    _db.inicializar_banco()
    return _db


# ═══════════════════════════════════════════════════════════════════
# FLUXO 1: LOGIN E CADASTRO
# ═══════════════════════════════════════════════════════════════════

class TestLoginCadastro:

    def test_email_valido_aceita_validos(self, db):
        assert db.email_valido("joao@fazenda.com.br")
        assert db.email_valido("maria.silva@gmail.com")

    def test_email_valido_rejeita_invalidos(self, db):
        assert not db.email_valido("semarroba.com")
        assert not db.email_valido("@semlocal.com")
        assert not db.email_valido("sem dominio@")
        assert not db.email_valido("")

    def test_cadastro_cria_usuario_com_trial(self, db):
        ok, msg, uid = db.auto_registrar_usuario(
            "João Silva", "joao@fazenda.com", "senha123", perfil="fazendeiro"
        )
        assert ok is True
        assert uid is not None

    def test_cadastro_recusa_email_duplicado(self, db):
        db.auto_registrar_usuario("A", "dup@x.com", "senha123")
        ok, msg, uid = db.auto_registrar_usuario("B", "dup@x.com", "senha123")
        assert ok is False

    def test_login_com_senha_correta(self, db):
        db.auto_registrar_usuario("João", "login@x.com", "minhasenha", "fazendeiro")
        u = db.autenticar_usuario("login@x.com", "minhasenha")
        assert u is not None
        assert u["email"] == "login@x.com"

    def test_login_com_senha_errada_falha(self, db):
        db.auto_registrar_usuario("João", "x@x.com", "certa123")
        u = db.autenticar_usuario("x@x.com", "errada456")
        assert u is None

    def test_login_email_case_insensitive(self, db):
        db.auto_registrar_usuario("João", "Maiusculo@X.com", "senha123")
        # Deve logar mesmo com case diferente
        u = db.autenticar_usuario("maiusculo@x.com", "senha123")
        assert u is not None

    def test_hash_bcrypt_e_verificavel(self, db):
        h = db._bcrypt_hash("teste123")
        # bcrypt gera $2b$ ou fallback SHA256$
        assert h.startswith("$2b$") or h.startswith("SHA256$")

    def test_ativar_trial(self, db):
        """Regressão: ativar_trial usa _td (timedelta) — não pode quebrar."""
        ok, msg, uid = db.auto_registrar_usuario("Vet", "vet@x.com", "senha123",
                                                  perfil="veterinario")
        db.ativar_trial(uid)
        sp = db.obter_status_plano(uid)
        assert sp is not None
        assert sp.get("ativo") is True

    def test_verificar_limite_fazendas(self, db):
        """Regressão: verificar_limite_fazendas chama obter_limites_usuario."""
        ok, msg, uid = db.auto_registrar_usuario("Vet2", "vet2@x.com", "senha123",
                                                  perfil="veterinario")
        lim = db.verificar_limite_fazendas(uid)
        assert lim is not None
        assert "ok" in lim
        assert "limite" in lim

    def test_definir_plano_usuario(self, db):
        """Regressão: definir_plano_usuario usa constantes PLANOS_*."""
        ok, msg, uid = db.auto_registrar_usuario("Vet3", "vet3@x.com", "senha123",
                                                  perfil="veterinario")
        db.definir_plano_usuario(uid, "veterinario", "pro", uid)
        lim = db.obter_limites_usuario(uid)
        assert lim is not None


# ═══════════════════════════════════════════════════════════════════
# FLUXO 2: LOTE
# ═══════════════════════════════════════════════════════════════════

class TestLote:

    def test_criar_lote_retorna_id(self, db):
        lote_id = db.adicionar_lote(
            "Lote Teste", "desc", "2026-01-01", 10, 10, "", owner_id=1
        )
        assert lote_id is not None

    def test_lote_criado_aparece_na_listagem(self, db):
        db.adicionar_lote("Lote A", "", "2026-01-01", 5, 5, "", owner_id=1)
        lotes = db.listar_lotes(owner_id=1)
        nomes = [l[1] for l in lotes]
        assert "Lote A" in nomes

    def test_lote_de_outro_owner_nao_aparece(self, db):
        db.adicionar_lote("Lote Owner1", "", "2026-01-01", 5, 5, "", owner_id=1)
        db.adicionar_lote("Lote Owner2", "", "2026-01-01", 5, 5, "", owner_id=2)
        lotes_o1 = db.listar_lotes(owner_id=1)
        nomes_o1 = [l[1] for l in lotes_o1]
        assert "Lote Owner1" in nomes_o1
        assert "Lote Owner2" not in nomes_o1

    def test_lote_vendido_some_da_listagem_ativa(self, db):
        lid = db.adicionar_lote("Lote Vendido", "", "2026-01-01", 5, 5, "", owner_id=1)
        db.atualizar_status_lote(lid, "VENDIDO")
        lotes = db.listar_lotes(owner_id=1)
        ids = [l[0] for l in lotes]
        assert lid not in ids


# ═══════════════════════════════════════════════════════════════════
# FLUXO 3: ANIMAL
# ═══════════════════════════════════════════════════════════════════

class TestAnimal:

    def _lote(self, db):
        return db.adicionar_lote("L", "", "2026-01-01", 5, 5, "", owner_id=1)

    def test_criar_animal_retorna_id(self, db):
        lid = self._lote(db)
        aid = db.adicionar_animal("A01", 24, lid, sexo="M", raca="Nelore",
                                  peso_entrada=300)
        assert aid is not None

    def test_animal_aparece_no_lote(self, db):
        lid = self._lote(db)
        db.adicionar_animal("A01", 24, lid, peso_entrada=300)
        animais = db.listar_animais_por_lote(lid)
        idents = [a[1] for a in animais]
        assert "A01" in idents

    def test_animal_vendido_some_dos_ativos(self, db):
        lid = self._lote(db)
        aid = db.adicionar_animal("A01", 24, lid, peso_entrada=300)
        db.marcar_animal_vendido(aid, data_venda="2026-06-01",
                                 preco_arroba=320, peso_abate=450)
        animais = db.listar_animais_por_lote(lid)
        ids = [a[0] for a in animais]
        assert aid not in ids

    def test_contagem_exclui_vendidos(self, db):
        lid = self._lote(db)
        a1 = db.adicionar_animal("A01", 24, lid, peso_entrada=300)
        db.adicionar_animal("A02", 24, lid, peso_entrada=300)
        # Antes: 2 ativos
        antes = len(db.listar_animais_por_lote(lid))
        db.marcar_animal_vendido(a1, data_venda="2026-06-01",
                                 preco_arroba=320, peso_abate=450)
        depois = len(db.listar_animais_por_lote(lid))
        assert antes == 2
        assert depois == 1

    def test_atualizar_animal_campos_completos(self, db):
        """Regressão: atualizar_animal deve aceitar os 8 campos da tela."""
        lid = self._lote(db)
        aid = db.adicionar_animal("A01", 24, lid, peso_entrada=300)
        # Chamar como a tela de edição faz (8 argumentos posicionais)
        db.atualizar_animal(aid, "A01-NOVO", 30, "Angus", "F", 320.0, 480.0, "obs")
        a = db.obter_animal(aid)
        assert a is not None
        # Identificação deve ter mudado
        assert a[1] == "A01-NOVO"


# ═══════════════════════════════════════════════════════════════════
# FLUXO 4: PESAGEM
# ═══════════════════════════════════════════════════════════════════

class TestPesagem:

    def _lote_animal(self, db):
        lid = db.adicionar_lote("L", "", "2026-01-01", 5, 5, "", owner_id=1)
        aid = db.adicionar_animal("A01", 24, lid, peso_entrada=300)
        return lid, aid

    def test_adicionar_pesagem(self, db):
        lid, aid = self._lote_animal(db)
        db.adicionar_pesagem(aid, 320, "2026-02-01")
        pes = db.listar_pesagens(aid)
        assert len(pes) >= 1

    def test_pesagens_do_lote(self, db):
        lid, aid = self._lote_animal(db)
        db.adicionar_pesagem(aid, 320, "2026-02-01")
        db.adicionar_pesagem(aid, 350, "2026-03-01")
        pes = db.listar_pesagens_lote(lid)
        assert len(pes) == 2

    def test_pesagens_excluem_animal_vendido(self, db):
        lid = db.adicionar_lote("L", "", "2026-01-01", 5, 5, "", owner_id=1)
        a1 = db.adicionar_animal("A01", 24, lid, peso_entrada=300)
        a2 = db.adicionar_animal("A02", 24, lid, peso_entrada=300)
        db.adicionar_pesagem(a1, 320, "2026-02-01")
        db.adicionar_pesagem(a2, 330, "2026-02-01")
        # Antes: 2 pesagens
        assert len(db.listar_pesagens_lote(lid)) == 2
        # Vender a1
        db.marcar_animal_vendido(a1, data_venda="2026-06-01",
                                 preco_arroba=320, peso_abate=450)
        # Depois: 1 pesagem (só do animal ativo)
        assert len(db.listar_pesagens_lote(lid)) == 1

    def test_pesagens_incluir_vendidos_traz_todos(self, db):
        lid = db.adicionar_lote("L", "", "2026-01-01", 5, 5, "", owner_id=1)
        a1 = db.adicionar_animal("A01", 24, lid, peso_entrada=300)
        db.adicionar_pesagem(a1, 320, "2026-02-01")
        db.marcar_animal_vendido(a1, data_venda="2026-06-01",
                                 preco_arroba=320, peso_abate=450)
        # Sem incluir: 0; incluindo: 1
        assert len(db.listar_pesagens_lote(lid)) == 0
        assert len(db.listar_pesagens_lote(lid, incluir_vendidos=True)) == 1


# ═══════════════════════════════════════════════════════════════════
# FLUXO 5: VENDA (TOTAL E PARCIAL)
# ═══════════════════════════════════════════════════════════════════

class TestVenda:

    def _lote_com_animais(self, db, n=3):
        lid = db.adicionar_lote("L", "", "2026-01-01", n, n, "", owner_id=1)
        aids = []
        for i in range(1, n + 1):
            aid = db.adicionar_animal(f"A0{i}", 24, lid, peso_entrada=300)
            aids.append(aid)
        return lid, aids

    def test_venda_total_calcula_receita(self, db):
        lid, _ = self._lote_com_animais(db)
        ok, receita, arrobas = db.registrar_venda_lote(
            lid, "2026-06-01", preco_arroba=320,
            peso_venda_total=450, frigorifico="JBS"
        )
        assert ok is True
        # 450kg * 0.5 / 15 = 15 arrobas; 15 * 320 = 4800
        assert abs(arrobas - 15.0) < 0.1
        assert abs(receita - 4800.0) < 1.0

    def test_venda_total_encerra_lote(self, db):
        lid, _ = self._lote_com_animais(db)
        db.registrar_venda_lote(lid, "2026-06-01", 320, 450, "JBS")
        # Lote não aparece mais na listagem ativa
        ids = [l[0] for l in db.listar_lotes(owner_id=1)]
        assert lid not in ids

    def test_venda_total_aparece_no_historico(self, db):
        lid, _ = self._lote_com_animais(db)
        db.registrar_venda_lote(lid, "2026-06-01", 320, 450, "JBS")
        hist = db.listar_lotes_historico(1)
        ids = [h[0] for h in hist]
        assert lid in ids

    def test_venda_parcial_mantem_lote_ativo(self, db):
        lid, aids = self._lote_com_animais(db, n=3)
        db.venda_parcial_lote(lid, [aids[0]], preco_kg=10.67,
                              peso_total=450, frigorifico="X",
                              data_venda="2026-06-01")
        # Lote continua ativo
        ids = [l[0] for l in db.listar_lotes(owner_id=1)]
        assert lid in ids

    def test_venda_parcial_reduz_animais_ativos(self, db):
        lid, aids = self._lote_com_animais(db, n=3)
        assert len(db.listar_animais_por_lote(lid)) == 3
        db.venda_parcial_lote(lid, [aids[0]], preco_kg=10.67,
                              peso_total=450, data_venda="2026-06-01")
        assert len(db.listar_animais_por_lote(lid)) == 2

    def test_venda_parcial_salva_dados_no_historico(self, db):
        lid, aids = self._lote_com_animais(db, n=3)
        db.venda_parcial_lote(lid, [aids[0]], preco_kg=10.67,
                              peso_total=450, frigorifico="Minerva",
                              data_venda="2026-06-01")
        vendidos = db.listar_animais_vendidos_lote(1)
        assert len(vendidos) >= 1
        # Verificar que tem dados de receita (índice 11)
        venda = vendidos[0]
        assert venda[11] > 0  # receita maior que zero

    def test_marcar_em_venda_e_cancelar(self, db):
        lid, _ = self._lote_com_animais(db)
        db.marcar_em_venda(lid)
        # Ainda aparece (EM_VENDA continua no workspace)
        lotes = db.listar_lotes(owner_id=1)
        lote = next((l for l in lotes if l[0] == lid), None)
        assert lote is not None
        # Cancelar volta para ATIVO
        db.cancelar_venda_lote(lid)
        lotes = db.listar_lotes(owner_id=1)
        lote = next((l for l in lotes if l[0] == lid), None)
        assert lote is not None


# ═══════════════════════════════════════════════════════════════════
# FLUXO 6: DRE / CÁLCULOS FINANCEIROS
# ═══════════════════════════════════════════════════════════════════

class TestDRE:

    def test_resumo_venda_calcula_margem(self, db):
        lid = db.adicionar_lote("L", "", "2026-01-01", 2, 2, "", owner_id=1)
        db.adicionar_animal("A01", 24, lid, peso_entrada=300)
        db.adicionar_animal("A02", 24, lid, peso_entrada=300)
        db.registrar_venda_lote(lid, "2026-06-01", preco_arroba=320,
                                peso_venda_total=900, frigorifico="JBS")
        resumo = db.obter_resumo_venda_lote(lid)
        assert resumo is not None
        assert resumo["receita"] > 0
        # margem = receita - custo_total
        assert resumo["margem"] == round(
            resumo["receita"] - resumo["custo_total"], 2
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
