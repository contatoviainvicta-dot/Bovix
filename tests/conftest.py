"""
conftest.py — Fixtures compartilhadas para os testes do Auroque
"""
import pytest
import sys, os

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

@pytest.fixture(scope="session")
def db_test():
    """Banco SQLite em memória para testes sem afetar o Supabase."""
    import database as db
    os.environ.pop("DATABASE_URL", None)
    db._pg_pool = None
    yield db

@pytest.fixture
def usuario_fazendeiro():
    return dict(
        id=1, nome="Teste Fazendeiro",
        email="test@auroque.com", perfil="fazendeiro",
        owner_id=1, plano="pro", status_conta="ativo",
        plano_expirado=False
    )

@pytest.fixture
def usuario_vet():
    return dict(
        id=2, nome="Dr. Teste Vet",
        email="vet@auroque.com", perfil="veterinario",
        owner_id=2, plano="vet", status_conta="ativo",
        plano_expirado=False
    )

@pytest.fixture
def usuario_admin():
    return dict(
        id=3, nome="Admin Teste",
        email="admin@auroque.com", perfil="admin",
        owner_id=3, plano="enterprise", status_conta="ativo",
        plano_expirado=False
    )
