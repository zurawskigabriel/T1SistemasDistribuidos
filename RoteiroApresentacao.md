# Roteiro de apresentacao do projeto

## 1. Contexto e objetivo (1 min)
- Trabalho 1: exclusao mutua distribuida (DiMeX) + snapshots (Chandy-Lamport).
- Objetivo: garantir a propriedade de mutex (DMX2) e progresso (DMX1), e validar consistencia via snapshots.

## 2. Arquitetura em camadas (2 a 3 min)
- Camadas implementadas:
  - Perfect Link (PL) sobre TCP.
  - DiMeX (Lock/Unlock) usando relogio de Lamport e prioridade por (timestamp, id).
  - Aplicacao de teste concorrente (processoDimex.py).
  - Ferramentas de validacao (validarSaida.py e validarSnapshots.py).

## 3. Fluxo do algoritmo DiMeX (3 a 4 min)
- Lock:
  - Incrementa relogio de Lamport e envia PEDIDO a todos.
  - Bloqueia ate receber RESPOSTA de todos.
- Resposta a pedidos:
  - Se nao quer SC, responde imediatamente.
  - Se quer ou esta na SC, decide por prioridade e pode adiar resposta.
- Unlock:
  - Libera SC e envia respostas adiadas.

## 4. Demonstracao do teste de exclusao mutua (2 min)
- Rodar 3 processos concorrentes.
- Cada processo escreve '.' e depois '|' no mesmo arquivo.
- Resultado esperado: apenas sequencias alternadas, sem '||' ou '..'.
- Mostrar validacao com validarSaida.py.

## 5. Snapshots com Chandy-Lamport (3 a 4 min)
- Um processo inicia snapshots sucessivos enquanto todos acessam a SC.
- Cada snapshot salva estado local e canais de entrada.
- Arquivos gerados por processo em .dimex_snapshots.
- Ferramenta validarSnapshots.py confere invariantes em cada snapshot.

## 6. Invariantes avaliadas (2 a 3 min)
- Inv 1: no maximo um processo na SC.
- Inv 2: se todos NAO_QUERO, nao ha mensagens em transito e nao ha pendencias.
- Inv 3: se um processo esta esperando, o outro esta na SC ou quer SC.
- Inv 4: para processo que quer SC, a soma de resposta recebida, em transito e adiada e 1 por processo remoto.

## 7. Pontos mais dificeis de implementar (destaque)
- Ordenacao e prioridade de pedidos concorrentes:
  - Comparacao de (timestamp, id) e manutencao correta do relogio de Lamport.
- Adiamento e liberacao de respostas:
  - Garantir que respostas adiadas sejam enviadas exatamente quando ocorre Unlock.
- Snapshot em cima do DiMeX:
  - Capturar estado local e canais de entrada corretamente.
  - Garantir que mensagens em transito sejam registradas apenas apos o marcador.
- Validacao de invariantes:
  - Traduzir propriedades do algoritmo em checagens consistentes.

## 8. Testes de falha (2 min)
- Inserir erro proposital (ex.: liberar resposta cedo ou nunca liberar).
- Mostrar que validarSnapshots.py acusa violacoes.

## 9. Encerramento (1 min)
- Reforcar que a implementacao atende DMX1 e DMX2.
- Mostrar que os snapshots confirmam consistencia do sistema.
- Abrir para perguntas.
