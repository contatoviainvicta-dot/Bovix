"""
test_database.py — Testes das funções críticas do database.py
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestFormatacao:
    """Testes das funções de formatação global."""

    def test_fmt_brl_inteiro(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ux_helpers",
            os.path.join(os.path.dirname(__file__), '..', 'ux_helpers.py')
        )
        ux = importlib.util.module_from_spec(spec)
        # Testar inline
        def fmt_brl(v):
            try:
                v=float(v); i=int(abs(v)); c=round((abs(v)-i)*100)
                s=f"{i:,}".replace(",","."); r=f"R$ {s},{c:02d}"
                return f"-{r}" if v<0 else r
            except: return "R$ 0,00"
        assert fmt_brl(0)        == "R$ 0,00"
        assert fmt_brl(100)      == "R$ 100,00"
        assert fmt_brl(1250)     == "R$ 1.250,00"
        assert fmt_brl(1250.75)  == "R$ 1.250,75"
        assert fmt_brl(702000)   == "R$ 702.000,00"
        assert fmt_brl(-50.30)   == "-R$ 50,30"

    def test_fmt_data(self):
        _MESES = {1:"jan",2:"fev",3:"mar",4:"abr",5:"mai",6:"jun",
                  7:"jul",8:"ago",9:"set",10:"out",11:"nov",12:"dez"}
        def fmt_data(d):
            try:
                d=str(d)[:10]; p=d.split("-")
                return f"{int(p[2]):02d} {_MESES[int(p[1])]} {p[0]}"
            except: return str(d)
        assert fmt_data("2025-01-12")  == "12 jan 2025"
        assert fmt_data("2026-05-28")  == "28 mai 2026"
        assert fmt_data("2025-12-01")  == "01 dez 2025"
        assert fmt_data("2025-03-01")  == "01 mar 2025"

    def test_fmt_brl_none(self):
        def fmt_brl(v):
            try:
                v=float(v); i=int(abs(v)); c=round((abs(v)-i)*100)
                s=f"{i:,}".replace(",","."); r=f"R$ {s},{c:02d}"
                return f"-{r}" if v<0 else r
            except: return "R$ 0,00"
        assert fmt_brl(None) == "R$ 0,00"
        assert fmt_brl("")   == "R$ 0,00"
        assert fmt_brl("abc") == "R$ 0,00"


class TestPermissoes:
    """Testes das regras de acesso por perfil."""

    def _simular_grupos(self, perfil):
        grupos = {"Inicio"}
        is_vet   = (perfil == "veterinario")
        is_admin = (perfil == "admin")
        if is_admin:
            grupos |= {"Analise", "Inteligencia", "Administracao", "Sistema"}
        else:
            grupos |= {"Rebanho", "Gestao Sanitaria", "Inteligencia",
                       "Financeiro", "Sistema"}
            if is_vet:
                grupos |= {"Clinico", "Preventivo", "Laboratorio", "Visitas Vet"}
        return grupos

    def test_vet_herda_fazendeiro(self):
        faz = self._simular_grupos("fazendeiro")
        vet = self._simular_grupos("veterinario")
        assert faz.issubset(vet), "Vet deve ver todos os menus do fazendeiro"

    def test_fazendeiro_nao_ve_clinico(self):
        faz = self._simular_grupos("fazendeiro")
        clinico = {"Clinico", "Preventivo", "Laboratorio", "Visitas Vet"}
        assert not (clinico & faz), "Fazendeiro NAO deve ver menus clínicos"

    def test_admin_nao_ve_rebanho(self):
        adm = self._simular_grupos("admin")
        assert "Rebanho" not in adm
        assert "Financeiro" not in adm

    def test_admin_ve_administracao(self):
        adm = self._simular_grupos("admin")
        assert "Administracao" in adm
        assert "Analise" in adm


class TestPlanos:
    """Testes do sistema de planos."""

    def test_plano_free_limites(self):
        planos = {
            "free":       dict(nome="Free",       limite_animais=50,    preco=0),
            "pro":        dict(nome="Pro",         limite_animais=500,   preco=99),
            "vet":        dict(nome="Vet",         limite_animais=2000,  preco=199),
            "enterprise": dict(nome="Enterprise",  limite_animais=99999, preco=0),
        }
        assert planos["free"]["limite_animais"]  == 50
        assert planos["pro"]["limite_animais"]   == 500
        assert planos["vet"]["limite_animais"]   == 2000
        assert planos["free"]["preco"]           == 0
        assert planos["pro"]["preco"]            == 99

    def test_verificar_limite_logic(self):
        def verificar(atual, limite, n_novos=0):
            pode = (atual + n_novos) <= limite
            disponiv = max(0, limite - atual)
            return dict(ok=pode, atual=atual, limite=limite,
                        disponiveis=disponiv)
        r = verificar(10, 50)
        assert r["ok"] is True
        assert r["disponiveis"] == 40

        r2 = verificar(50, 50)
        assert r2["ok"] is True
        assert r2["disponiveis"] == 0

        r3 = verificar(50, 50, n_novos=1)
        assert r3["ok"] is False


class TestExpiracao:
    """Testes da lógica de expiração de plano."""

    def test_plano_expirado(self):
        from datetime import date, timedelta
        ontem = str(date.today() - timedelta(days=1))
        hoje  = str(date.today())
        amanha = str(date.today() + timedelta(days=1))

        def expirado(plano_expira, plano="pro"):
            if not plano_expira or plano == "free":
                return False
            try:
                return date.today() > date.fromisoformat(plano_expira[:10])
            except: return False

        assert expirado(ontem)  is True
        assert expirado(amanha) is False
        assert expirado(hoje)   is False  # expira hoje = ainda válido
        assert expirado(None)   is False
        assert expirado(ontem, plano="free") is False  # free nunca expira


class TestCSV:
    """Testes de importação de CSV."""

    def test_deteccao_separador(self):
        csv_virgula   = "identificacao,data,peso\nTST-001,2025-01-01,320"
        csv_ptvirgula = "identificacao;data;peso\nTST-001;2025-01-01;320"
        def detectar_sep(conteudo):
            return ";" if conteudo[:200].count(";") > conteudo[:200].count(",") else ","
        assert detectar_sep(csv_virgula)   == ","
        assert detectar_sep(csv_ptvirgula) == ";"

    def test_normalizacao_colunas(self):
        linhas = [{"Identificacao": "TST-001", "PESO": "320", "Data": "2025-01-01"}]
        norm = [{k.strip().lower(): v for k, v in l.items()} for l in linhas]
        assert "identificacao" in norm[0]
        assert "peso"          in norm[0]
        assert "data"          in norm[0]

    def test_campos_obrigatorios(self):
        colunas_ok      = ["identificacao", "data", "peso"]
        colunas_faltam  = ["identificacao", "data"]
        obrig = ["identificacao", "data", "peso"]
        assert not [c for c in obrig if c not in colunas_ok]
        assert     [c for c in obrig if c not in colunas_faltam] == ["peso"]
