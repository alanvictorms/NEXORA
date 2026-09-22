# Provider Registry, OpenHands e ACP

O `ProviderRegistry` seleciona executores por capability, prioridade, habilitação e preferência da tarefa. O `ExecutionService` mantém a política de fallback e registra uma `Execution` por tentativa. Nenhuma regra de produto conhece modelos específicos.

Providers iniciais:

| Adapter | Papel | Autenticação |
|---|---|---|
| `local_mock` | CI, desenvolvimento e regressão determinística | nenhuma |
| `openhands_native` | agente OpenHands nativo | Session API Key |
| `claude_code_acp` | Claude Code por ACP no Agent Server | secret ref |
| `codex_acp` | Codex por ACP no Agent Server | secret ref |

O cliente cria uma conversa diretamente em `/api/conversations`, envia `agent`, `initial_message`, `workspace`, limites e tags; depois consulta o estado até conclusão e pode interromper. O payload do agente fica em `provider_metadata`, permitindo acompanhar o contrato da versão fixada do Agent Server sem contaminar o domínio.

Configuração mínima:

```dotenv
OPENHANDS_BASE_URL=http://openhands-agent-server:8000
OPENHANDS_API_KEY=uma-chave-de-sessao
```

Em produção, fixe imagem/digest, teste o OpenAPI correspondente, mantenha a rede privada e injete secrets somente no runtime autorizado. O Agent Canvas não é usado.
