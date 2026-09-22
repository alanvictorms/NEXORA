# ProjectSpec, DesignSpec e TaskGraph

`ProjectSpecVersion` é a intenção compilada. Cada mensagem gera uma nova versão com patch, checksum e origem. A análise de lacunas cria no máximo cinco perguntas úteis; somente severidade `BLOCKING` interrompe o pipeline.

`DesignSpecVersion` extrai referências, tokens, direção visual e requisitos de acessibilidade sem colocar arquivos binários no prompt. `ArchitectureSpecVersion` aplica a Stack Policy e registra decisões com justificativa.

`TaskGraph` é uma DAG versionada. Cada `TaskSpec` inclui dependências, objetivo, caminhos permitidos/proibidos, contexto mínimo, critérios de aceite, comandos, artifacts esperados, provider policy, timeout e retry policy. O `ContextCompiler` entrega ao executor apenas o recorte necessário e artifacts das dependências.

Os schemas interoperáveis ficam em `packages/contracts`. Os modelos Pydantic do backend são a implementação executável e os JSON Schemas são o contrato externo estável v1.
