# Auditoria integral do legado

## Escopo examinado

Foram examinados o código Flask, templates, CSS/JavaScript, banco SQLite, cinco prompts históricos, oito referências cadastradas, seis imagens e dois HTMLs completos. Arquivos compilados `pyc` foram tratados como derivados dos fontes presentes. O `.env` foi inventariado somente por nome de variável; nenhum valor foi copiado.

## Decisão

A V2 será uma reconstrução em base nova, com reaproveitamento seletivo de conhecimento. O Flask não entra no runtime novo. O legado permanece como fonte para importação e regressão.

## Conhecimento preservado

- briefing: descrição, mensagem original, notas internas e direção visual;
- taxonomias de autenticação, permissões, hospedagem, gateway, API externa e realtime;
- integrações específicas, incluindo Evolution API/WhatsApp;
- anexos visuais e HTML/CSS como artefatos de design;
- campos extras extensíveis;
- prompts históricos como `EvaluationFixture`, nunca como cérebro do produto;
- prioridade mobile, fidelidade visual, estados vazios, feedback e critérios de aceite;
- projetos históricos reais: PlayMenu, Endereço Fiscal, ConnectaCapital e Fazenda Boaventura.

## Problemas que não serão transportados

- tabela `Project` achatada e com responsabilidades demais;
- segredo plaintext no SQLite e segredo inserido em `data-secret` no HTML;
- ausência de autenticação, tenant isolation, CSRF e testes;
- uploads validados apenas por extensão;
- migração SQLite por `PRAGMA` e `ALTER TABLE` manual;
- request HTTP síncrona chamando um único modelo;
- prompt monolítico como estado do sistema;
- seleção manual de stack/plataforma pelo usuário comum;
- credenciais operacionais misturadas com briefing.

## Segurança

O pacote contém uma `OPENAI_API_KEY` e credenciais de teste/administrativas em campos legados. Elas não são importadas. Devem ser rotacionadas ou invalidadas. O importador V2 registra apenas que havia material sensível e exige recadastro.

## Mapeamento para a V2

| Legado | V2 |
| --- | --- |
| `projects` | `projects` + `project_spec_versions` |
| briefing/notas/layout | seções estruturadas de `ProjectSpec` |
| credenciais em colunas | `secret_metadata` + secret store |
| `project_references` | `artifacts` + futura `design_spec_versions` |
| `prompt_generations` | `evaluation_fixtures` |
| plataforma/stack escolhida | `ArchitectureDecision` dentro da Stack Policy |
| geração síncrona | workflow durável e DAG persistida |

