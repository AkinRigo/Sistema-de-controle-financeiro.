# Painel Financeiro — backend

FastAPI + SQLAlchemy + Alembic. Regras de negócio puras em `src/painel/domain`.

## Rodar

```powershell
cd backend
py -3.12 -m venv .venv            # ou o python 3.12 do pyenv
.venv\Scripts\pip install -e ".[dev]"
copy .env.example .env            # e preencha (chave: python -c "import secrets;print(secrets.token_hex(32))")
.venv\Scripts\alembic upgrade head
.venv\Scripts\uvicorn painel.main:app --reload --env-file .env
```

Documentação interativa: http://localhost:8000/docs

| Variável | Padrão |
|---|---|
| `PAINEL_DATABASE_URL` | **obrigatória**: connection string do Neon (Postgres). Sem ela o backend não sobe. |
| `PAINEL_CHAVE_TOKEN` | aleatória (logins caem ao reiniciar) |
| `PAINEL_VALIDADE_TOKEN` | `604800` (7 dias, em segundos) |
| `PAINEL_CORS_ORIGENS` | `http://localhost:5173` (separe por vírgula) |
| `PAINEL_URL_FRONTEND` | `http://localhost:5173` (base do link no e-mail) |
| `ADMIN_API_KEY` | vazia: `POST /admin/users` fica desligada |
| `PAINEL_SMTP_USUARIO` / `PAINEL_SMTP_SENHA` | vazio: o link de troca de senha sai só no terminal |

### E-mail (Gmail)

1. Ative a verificação em duas etapas na conta Google.
2. Crie uma senha de app em https://myaccount.google.com/apppasswords.
3. No `.env`: `PAINEL_SMTP_USUARIO=seu@gmail.com` e `PAINEL_SMTP_SENHA=<as 16 letras>`.

## Testes

```powershell
.venv\Scripts\python -m coverage run -m pytest; .venv\Scripts\python -m coverage report
.venv\Scripts\ruff check .
```

## Camadas

- `domain/` — entidades, valores (`Dinheiro` em Decimal, `Mes` AAAA-MM) e regras.
- `infra/` — modelos ORM, mapeamento ORM↔domínio, argon2 e tokens PASETO v4.local.
- `api/` — schemas, dependências e rotas. Dinheiro sai sempre como texto (`"150.50"`).

## Rotas

- `POST /auth/cadastro`, `POST /auth/login`, `GET /auth/eu`
- `POST /auth/esqueci-senha` (manda o link), `POST /auth/redefinir-senha` (vale 30 min, uso único)
- `GET|PUT /configuracoes/corridas`
- `GET|POST /bancos`, `PUT|DELETE /bancos/{id}`
- `GET|POST /contas`, `PUT|DELETE /contas/{id}`
- `GET /pagamentos?mes=AAAA-MM`, `POST /pagamentos`, `DELETE /pagamentos/{id}`
- `GET|POST /ganhos`, `PUT|DELETE /ganhos/{id}`
- `GET /resumo/{mes}`, `GET /categorias`, `GET /categorias/{mes}`, `GET /divida`
- `GET /backup` (exporta), `POST /backup` (importa e substitui tudo; aceita o JSON do protótipo)

Saldos de banco são ajustados automaticamente: pagamento com `banco_id` debita;
ganho `recebido` com `banco_id` credita; desfazer pagamento ou editar ganho desfaz o efeito.
Excluir uma conta apaga o histórico dela, mas não mexe nos saldos.

## Cadastrar amigos (admin)

`POST /admin/users` cria uma conta já ativada. Exige o header `X-Admin-Key` com o valor da
`ADMIN_API_KEY` (no Render: serviço → Environment). Exemplo no PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri https://controle-financeiro-api-thgy.onrender.com/admin/users `
  -Headers @{ "X-Admin-Key" = "<sua ADMIN_API_KEY>" } -ContentType "application/json" `
  -Body '{"nome":"Bia","email":"bia@exemplo.com","senha":"senha-com-8+"}'
```

Também dá para usar a página `/docs` (botão "Try it out" em `POST /admin/users`).

