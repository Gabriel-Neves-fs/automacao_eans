# Automação de EANs na VTEX

Este projeto nasceu de uma necessidade bem prática: atualizar os EANs de mais de 200 produtos na VTEX sem precisar fazer tudo manualmente pelo painel. Como o volume era grande e o processo repetitivo, a solução foi automatizar a alteração usando a API de catálogo da VTEX.

A automação lê uma planilha com os SKUs e seus novos EANs, consulta o EAN atual de cada SKU, remove os EANs antigos quando necessário e cadastra o novo código de barras. O script também tem modo de simulação para validar a planilha antes de executar alterações reais.

## O que o projeto faz

- Lê uma planilha Excel com as colunas `SKU` e `ean`.
- Consulta os EANs já cadastrados no SKU via API da VTEX.
- Mantém o SKU intacto quando o EAN informado já está correto.
- Simula as alterações com `--dry-run` antes de gravar dados.
- Remove EANs antigos e cadastra o novo EAN quando executado com `--no-dry-run`.
- Gera um relatório final em `execution_report.xlsx` com o resultado de cada linha.

## Arquivos principais

- `vtex_ean_automation.py`: script principal da automação.
- `debug.py`: script auxiliar para testar a conexão e consultar dados de um SKU específico.
- `requirements.txt`: dependências Python necessárias para rodar o projeto.
- `.gitignore`: impede o versionamento de credenciais, ambiente virtual, planilhas e relatórios.

## Instalação

Requisitos:

- Python 3.8 ou superior
- Credenciais de API da VTEX com permissão de catálogo

Instale as dependências:

```powershell
pip install -r requirements.txt
```

Crie um arquivo `.env` na raiz do projeto com as credenciais:

```env
VTEX_ACCOUNT_NAME=sua_loja
VTEX_ENVIRONMENT=vtexcommercestable
VTEX_APP_KEY=sua_app_key
VTEX_APP_TOKEN=seu_app_token
```

O arquivo `.env` não deve ser enviado ao GitHub.

## Formato da planilha

A planilha precisa ter estas colunas:

| Coluna | Descrição |
| --- | --- |
| `SKU` | ID do SKU na VTEX |
| `ean` | Novo código de barras que será cadastrado |

Exemplo:

| SKU | ean |
| --- | --- |
| 1001 | 7890000000001 |
| 1002 | 7890000000002 |

Dica: formate as colunas como texto no Excel para evitar que os códigos sejam convertidos para notação científica ou recebam `.0` no final.

## Como usar

Rode primeiro em modo de simulação:

```powershell
python vtex_ean_automation.py --file sua_planilha.xlsx --dry-run
```

Quando o resultado estiver correto, execute a alteração real:

```powershell
python vtex_ean_automation.py --file sua_planilha.xlsx --no-dry-run
```

Para controlar a quantidade de requisições simultâneas:

```powershell
python vtex_ean_automation.py --file sua_planilha.xlsx --no-dry-run --concurrency 5
```

## Relatório

Ao final, o script gera `execution_report.xlsx` com os dados processados e as colunas de status.

Status possíveis:

- `Already Up-to-date`: o SKU já estava com o EAN correto.
- `Dry-Run`: simulação executada, sem alteração na VTEX.
- `Created`: EAN criado em um SKU que não tinha EAN cadastrado.
- `Replaced`: EAN antigo removido e novo EAN cadastrado.
- `Skipped`: linha ignorada por falta de SKU ou EAN.
- `Error`: erro ao consultar, remover ou cadastrar o EAN.

## Observações

- Sempre rode a simulação antes da execução real.
- Confira se as credenciais da VTEX estão corretas no `.env`.
- Planilhas, relatórios, `.env` e `.venv` ficam fora do versionamento por segurança e organização.
