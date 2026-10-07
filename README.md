# DropFlow Platform — protótipo com backend

## O que está implementado
- Site responsivo com catálogo
- Cadastro e login com hash de senha
- Sessão individual por usuário
- SQLite para usuários, produtos e pedidos
- Painel do usuário com histórico
- Criar pedidos de demonstração e reduzir estoque
- Busca de produtos
- Produtos iniciais inseridos automaticamente

## Rodar localmente
Requer Python 3.10+.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Abra http://127.0.0.1:5000

## Importante
Este projeto ainda é um protótipo. Pedidos não são pagos nem enviados. Não há integração real com fornecedores, gateways de pagamento, transportadoras ou marketplaces. Antes de publicar, configure `DROPFlow_SECRET` com uma chave aleatória forte, desative `debug`, use HTTPS, adicione proteção CSRF e limites de tentativas, política de privacidade/termos, backups e revisão de segurança. O painel `/admin` fica bloqueado por padrão; a autorização de administrador precisa ser implementada explicitamente antes de uso real.


## Multi-lojas — nova funcionalidade
Cada conta possui uma loja própria:
- Nome, descrição, emoji/logo e cor da marca.
- Slug único, por exemplo `/loja/minha-marca`.
- Seleção dos produtos publicados.
- Nome e preço personalizados por loja.
- Página pública responsiva.
- Link "Ver loja" no painel.

### Próxima infraestrutura para produção real
1. Publicar o backend em um servidor com HTTPS.
2. Migrar SQLite para PostgreSQL.
3. Usar variáveis de ambiente para segredos.
4. Implementar domínio/subdomínio por loja.
5. Implementar checkout real com um provedor de pagamentos.
6. Criar carrinho, cálculo de frete e confirmação de pedido.
7. Implementar webhooks idempotentes para pagamentos.
8. Implementar integração real com fornecedor/fulfillment.
9. Adicionar CSRF, rate limiting, logs, backups e monitoramento.
10. Revisar LGPD, Termos de Uso, Política de Privacidade e regras de chargeback.

O botão "Comprar" das lojas públicas ainda é propositalmente bloqueado: ele não coleta pagamento e não cria uma venda real até que o checkout seja configurado.


# Plano das 7 frentes

1. **Servidor online:** Gunicorn + Docker/Compose preparados. Falta escolher um provedor e configurar DNS/HTTPS.
2. **Checkout/pagamento:** carrinho + checkout + ponto de integração. O Mercado Pago recomenda Orders API para novas integrações; a criação exige `X-Idempotency-Key`. Credenciais ficam somente em variáveis de ambiente. O adaptador real deve verificar o webhook e consultar o status antes de marcar o pedido como pago.
3. **Carrinho:** implementado em sessão, com quantidade e remoção.
4. **Pedidos reais:** a base atual pode ser expandida para estados `pending/paid/processing/shipped/delivered/cancelled/refunded`. A confirmação de pagamento deve vir do webhook do provedor, não do retorno do navegador.
5. **Fornecedor/fulfillment:** arquitetura deve usar um adapter por fornecedor; não foram inventadas APIs ou credenciais. O próximo passo é conectar um fornecedor escolhido e mapear SKU, estoque, custo, pedido e rastreio.
6. **Domínio por loja:** campo de domínio + tela de configuração. A etapa de DNS/TLS depende do servidor e do domínio. Um reverse proxy deve rotear o Host para a loja correspondente.
7. **Segurança/LGPD:** cookies HTTPOnly/SameSite, headers de segurança, CSRF, senhas com hash, `.env` fora do Git, limite de upload e páginas iniciais de privacidade/termos. A LGPD considera dados pessoais informações relacionadas a pessoa identificada ou identificável; antes de operar, defina controlador, retenção, direitos dos titulares e canal de contato. Consulte a ANPD. 

## Antes do lançamento comercial
- Trocar SQLite por PostgreSQL em produção (o `docker-compose` já inclui PostgreSQL, mas a camada de acesso precisa ser migrada/validada antes de produção).
- Configurar domínio e HTTPS.
- Criar conta comercial do provedor de pagamentos e credenciais de produção.
- Fazer testes em sandbox antes de produção.
- Implementar verificação de assinatura/segurança de webhooks e idempotência.
- Implementar autenticação de administrador e RBAC.
- Implementar rate limiting, logs estruturados, monitoramento, backups e restauração testada.
- Definir política de reembolso, chargeback, atendimento e conformidade fiscal.
- Se o operador da plataforma for menor de idade, a abertura/uso de contas comerciais, contratos e serviços financeiros deve ser feita com um responsável adulto e conforme os requisitos do provedor.

## Deploy no Render

1. Suba este projeto para um repositório GitHub.
2. No Render, crie um Web Service apontando para o repositório.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
5. Configure `DATABASE_URL` com a URL de um PostgreSQL.
6. Configure `DROPFlow_SECRET` como segredo forte e `COOKIE_SECURE=1`.
7. Faça o deploy e abra a URL `.onrender.com` fornecida pelo Render.

O arquivo `render.yaml` também pode ser usado como referência para a configuração.
