# ADR 0002 — Monólito modular e Temporal

Status: aceito.

O control plane é um monólito modular FastAPI. Temporal executa workflows duráveis em processo worker separado. Um backend local implementa o mesmo contrato para testes e desenvolvimento sem mascarar o backend escolhido.

