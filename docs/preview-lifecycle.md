# Preview lifecycle

O preview local implementa o mesmo contrato dos futuros providers OCI: alocar, pausar, retomar e destruir. Estados suportados: `BUILDING`, `STARTING`, `ACTIVE`, `IDLE`, `PAUSED`, `RESUMING`, `ARCHIVED`, `RESTORING`, `FAILED` e `DELETED`.

- inatividade padrão: 1.800 segundos;
- uma sessão ativa por projeto por padrão;
- URL permanece estável durante a retenção;
- reconciliação automática marca `IDLE`, pausa e remove expirados;
- artifacts permanecem registrados enquanto retidos;
- cada preview recebe nomes exclusivos de database e role no contrato;
- preview nunca vira produção.

`PREVIEW_IDLE_TIMEOUT_SECONDS`, `PREVIEW_RETENTION_DAYS` e `MAX_ACTIVE_PREVIEWS_PER_PROJECT` controlam a política. O provider local serve o artifact pelo backend; um provider de containers deve aplicar database/role reais, quota de compute e isolamento de rede mantendo a mesma interface.
