# Certificação QAS — 2026-08-04

## Escopo

Esta evidência cobre a estabilização `16.0.1.1.14` (incluindo a restauração da
Categoria Padre) e a release `16.0.1.2.0` de controle de Packs OCA e variantes.
PROD não foi alterado e continua condicionado à aprovação funcional do usuário.

## Baseline certificado

- Branch: `feature/bpi-pack-variant-control`
- Código inicialmente implantado: `21e2f98ba53aec0e0a98171bbcb476da7ac9be08`
- Versão instalada: `16.0.1.2.0`
- Backup completo: `/opt/odoo/backups/qas_remediation_stock_tz_ports_20260804T132627Z`
- Backup validado por SHA-256: banco, filestore, addons e configurações

## Remediações do ambiente QAS

1. **Configurações de Inventário**
   - A view ativa era `16.0.3.0.0`, mas o código carregado era `16.0.2.6.1`.
   - Foi sobreposto somente o addon oficial OCA `stock_inventory` `16.0.3.0.0`,
     proveniente do commit `0763434d2d866cc4daab3b0838f39cf4953040e8`.
   - Os 30 arquivos foram validados por SHA-256.
   - `stock_inventory_batch_size` existe novamente em `res.config.settings` e
     `res.company`; a view 2835 está ativa e seu XML é válido.

2. **Timezones da Argentina**
   - Foram corrigidos 179 parceiros e 1 recurso com aliases obsoletos.
   - Depois da correção: zero aliases inválidos.
   - Foram lidos com sucesso 120 usuários, 920 atividades e os registros exatos
     do traceback (`sale.order` 5967 e `mail.activity` 56790).

3. **HTTP e websocket**
   - Odoo 8069 e gevent 8072 escutam somente em `127.0.0.1`.
   - Nginx permanece como única entrada pública; `/web/login` retorna HTTP 200.
   - O websocket público respondeu `101 SWITCHING PROTOCOLS`.
   - As portas 8069/8072 não são acessíveis diretamente pela Internet.

## Testes do Producto Intelligence

- Validação estática: **PASS** (manifesto, Python, XML, JavaScript, 28 caminhos
  frontend/30 rotas, higiene Git).
- `git diff --check`: **PASS**.
- Busca por segredos no conteúdo rastreado: **limpa**.
- Backend Odoo: **18 testes**, 0 falhas, 0 erros.
- OWL QUnit: **10 testes**, **28/28 assertions**, 0 falhas.
- Runtime QAS: 29/29 arquivos do commit original validados por SHA-256 antes
  desta atualização exclusivamente documental.

## Evidência funcional

- Categoria nativa continua sendo a view padrão.
- As views BPI são derivadas primárias com bindings explícitos tree/form.
- `parent_id`, imagem, website e sequência estão presentes na view BPI.
- Produto QAS 2096, **QAS BPI CERT - Producto con 2 variantes**:
  `productKind=variants`, 2 variantes, intervalo efetivo USD 100–115.
- Produto QAS 2099, **QAS BPI CERT - Pack 2 componentes**:
  `productKind=pack`, 2 componentes e revisão concorrente válida.
- O mesmo payload foi validado via JSON-RPC público através do Nginx.
- Cron de jobs do Producto Intelligence permanece ativo.
- “Total Productos” corresponde somente a templates ativos.

## Estado final dos logs

A partir do checkpoint UTC `2026-08-04 13:57:12`, após reinício, chamadas RPC e
handshake websocket:

- 0 ERROR;
- 0 CRITICAL;
- 0 WARNING;
- 0 ocorrências de `stock_inventory_batch_size` ausente;
- 0 timezones inválidos;
- 0 erros de binding websocket;
- 0 tráfego malformado chegando diretamente ao Odoo.

## Decisão de entrega

QAS está tecnicamente certificado. A implantação em PROD permanece bloqueada até
aprovação funcional explícita dos dois ajustes pelo usuário.

## Hotfix OWL 16.0.1.2.1

Após a certificação inicial, a abertura da ação revelou que o compilador OWL do
Odoo 16 não aceita `t-on-keydown.enter.prevent`. A release `16.0.1.2.1` substitui
esse modificador por um handler JavaScript que valida `event.key === "Enter"`,
respeita composição IME e chama `preventDefault()` somente para Enter. A evidência
de backend, QUnit, abertura real da ação e logs será atualizada após o deploy QAS.
