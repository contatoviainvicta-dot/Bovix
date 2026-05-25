"""Testes de autenticacao e migracao bcrypt."""
import pytest


def test_criar_usuario_e_autenticar(db_temp):
    """Usuario criado consegue autenticar com a senha correta."""
    uid = db_temp.criar_usuario(
        nome="Teste Auth", email="auth1@test.com",
        senha="MinhaSenha@123", perfil="fazendeiro"
    )
    assert uid is not None

    user = db_temp.autenticar_usuario("auth1@test.com", "MinhaSenha@123")
    assert user is not None
    assert user["email"] == "auth1@test.com"
    assert user["perfil"] == "fazendeiro"


def test_autenticar_senha_errada_retorna_none(db_temp):
    """Senha incorreta retorna None."""
    db_temp.criar_usuario(
        nome="Teste", email="auth2@test.com",
        senha="CertaSenha", perfil="fazendeiro"
    )
    user = db_temp.autenticar_usuario("auth2@test.com", "ErradaSenha")
    assert user is None


def test_autenticar_email_inexistente_retorna_none(db_temp):
    """Email nao cadastrado retorna None."""
    user = db_temp.autenticar_usuario("naoexiste@test.com", "qualquer")
    assert user is None


def test_bcrypt_hash_e_verify():
    """bcrypt_hash e bcrypt_verify funcionam corretamente."""
    from database import _bcrypt_hash, _bcrypt_verify

    h = _bcrypt_hash("senha_teste_123")
    assert h is not None
    assert _bcrypt_verify("senha_teste_123", h) is True
    assert _bcrypt_verify("senha_errada", h) is False


def test_is_bcrypt_hash():
    """Detecta hash bcrypt vs SHA256."""
    from database import _is_bcrypt_hash, _bcrypt_hash

    h_bcrypt = _bcrypt_hash("teste")
    assert _is_bcrypt_hash(h_bcrypt) is True
    assert _is_bcrypt_hash("a" * 64) is False  # SHA256
    assert _is_bcrypt_hash("") is False
    assert _is_bcrypt_hash(None) is False


def test_migracao_sha256_para_bcrypt(db_temp):
    """Senha SHA256 antiga e migrada para bcrypt no proximo login."""
    import secrets

    # Criar usuario "manualmente" com hash SHA256 (simulando usuario antigo)
    p    = db_temp._ph()
    salt = secrets.token_hex(16)
    h    = db_temp._hash_senha("senha_antiga", salt)

    with db_temp._conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO usuarios (nome,email,senha_hash,salt,perfil,ativo) "
            f"VALUES ({p},{p},{p},{p},{p},1)",
            ("Antigo", "antigo@test.com", h, salt, "fazendeiro")
        )
        conn.commit()

    # Autenticar com senha correta — deve funcionar e migrar
    user = db_temp.autenticar_usuario("antigo@test.com", "senha_antiga")
    assert user is not None

    # Verificar que o hash foi migrado
    with db_temp._conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT senha_hash FROM usuarios WHERE email={p}",
            ("antigo@test.com",)
        )
        novo_hash = cur.fetchone()[0]

    from database import _is_bcrypt_hash
    assert _is_bcrypt_hash(novo_hash), "Hash deveria ter sido migrado para bcrypt"

    # Login continua funcionando com a mesma senha
    user2 = db_temp.autenticar_usuario("antigo@test.com", "senha_antiga")
    assert user2 is not None
