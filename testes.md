# Testes do Auroque

Suíte de testes automatizados dos fluxos críticos.

## Rodar os testes

```bash
# Instalar dependências (uma vez)
pip install pytest bcrypt

# Rodar todos os testes
pytest test_fluxos_criticos.py

# Rodar só um fluxo
pytest test_fluxos_criticos.py -k login
pytest test_fluxos_criticos.py -k venda

# Parar no primeiro erro
pytest test_fluxos_criticos.py -x
```

## O que é testado

**Login e cadastro** (8 testes)
- Validação de email
- Cadastro com trial
- Recusa de email duplicado
- Login com senha correta/errada
- Login case-insensitive
- Hash bcrypt verificável

**Lote** (4 testes)
- Criação e listagem
- Isolamento por owner (RLS)
- Lote vendido some da listagem ativa

**Animal** (4 testes)
- Criação e vínculo ao lote
- Animal vendido some dos ativos
- Contagem exclui vendidos

**Pesagem** (5 testes)
- Adicionar e listar
- Pesagens excluem animais vendidos
- Flag incluir_vendidos para histórico

**Venda** (7 testes)
- Venda total calcula receita correta
- Venda total encerra o lote
- Venda total aparece no histórico
- Venda parcial mantém lote ativo
- Venda parcial reduz animais ativos
- Venda parcial salva dados no histórico
- Em negociação e cancelamento

**DRE** (1 teste)
- Cálculo de margem (receita - custo)

## Quando rodar

**Sempre antes de cada deploy.** Se algum teste falhar, NÃO suba para o GitHub
até corrigir. Isso evita que uma correção quebre outro fluxo (regressão).

## Adicionar novos testes

Ao criar uma nova função crítica no `database.py`, adicione um teste aqui.
A regra: se quebrar em produção dói, tem que ter teste.
