"""
conftest.py — Fixtures pytest para BOVIX.

Usa SQLite em arquivo temporario (em memoria seria mais rapido
mas o codigo usa contextmanager de conexao - arquivo e mais seguro).
"""
import os
import sys
import tempfile
import pytest

# Adicionar raiz do projeto ao path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture
def db_temp(monkeypatch):
    """Cria banco SQLite temporario isolado para cada teste."""
    # Forcar uso de SQLite via env var
    monkeypatch.setenv("BOVIX_FORCE_SQLITE", "1")

    # Criar arquivo temporario
    fd, db_path = tempfile.mkstemp(suffix=".db", prefix="bovix_test_")
    os.close(fd)

    # Apontar para o arquivo temporario via env var
    monkeypatch.setenv("BOVIX_SQLITE_PATH", db_path)

    # Importar e inicializar banco apos env vars setadas
    import database

    # Forcar reuso do path temporario
    original_db = getattr(database, "DB_PATH", None)
    if hasattr(database, "DB_PATH"):
        database.DB_PATH = db_path

    # Inicializar banco
    database.inicializar_banco()

    yield database

    # Cleanup
    try:
        os.unlink(db_path)
    except Exception:
        pass


@pytest.fixture
def usuario_fazendeiro(db_temp):
    """Cria um usuario fazendeiro para os testes."""
    uid = db_temp.criar_usuario(
        nome="Joao Teste",
        email="joao.teste@bovix.test",
        senha="Teste@123",
        perfil="fazendeiro"
    )
    return uid


@pytest.fixture
def usuario_vet(db_temp):
    """Cria um usuario veterinario para os testes."""
    uid = db_temp.criar_usuario(
        nome="Dra Ana Teste",
        email="ana.teste@bovix.test",
        senha="Teste@123",
        perfil="veterinario"
    )
    return uid
