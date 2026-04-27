# Trabalho 1

* Grupos de no máximo 4 estudantes.
* Enunciado abaixo.
* Entrega na sala abaixo, conforme instruções na sala.

## Trabalho 1 - Parte 1 - DiMeX

Implementar o algoritmo de exclusão mútua distribuída discutido em aula.
A implementação deve ter claramente os níveis (módulos) discutidos em aula.
O módulo "PL" (*Perfect Link*), deve ser implementado sobre a interface de comunicação remota (p.ex. *sockets*).

Se você for implementar **sem IA**, pode usar o template em Go fornecido pelo professor, abaixo.

Se você for implementar **com IA**, então faça todo o conjunto de módulos.
Use como exemplo a sugestão discutida para o PL.
Use a modularidade, as propriedades e a argumentação destes algoritmos em seu favor durante o uso de IA para desenvolver o sistema. A modularidade ajuda a você ter maior certeza sobre o resultado de cada parte, para então avaliar a composição das partes.

Em ambos os casos, você deve montar uma **aplicação de testes**.
A aplicação deve exercer o uso concorrente do recurso e deve ser possível avaliar se houve violação da exclusão mútua. Para isso, você pode usar ou adaptar a aplicação fornecida no código. 
Nesta aplicação distribuída, cada processo acessa repetidas vezes o mesmo arquivo.
Cada processo, ao acessar, faz duas operacoes de escrita: `write(".")` e `write("|")`.
Ao final o arquivo comum deve conter uma sequencia de `.|.|.|.|.|.|.|.|.|.| ...`
Se houver qualquer `||` ou `..` isso terá sido uma violação da exclusão mútua no acesso ao recurso.
Não use "*sleeps*" entre as operações. O acesso deve ser intensivo.
Se o algoritmo não está correto, com alta chance o problema aparecerá.

Veja abaixo sobre as propriedades do DiMEx.

---

## Trabalho 1 - Parte 2 - Snapshot no DiMeX

Implemente o algoritmo de snapshot junto ao DiMEx, usando o **algoritmo de Chandy-Lamport** discutido em aula.

Note que na exclusão mútua, todo processo tem um canal com cada outro e que este canal preserva ordem e não perde mensagens. Assim, as suposições do algoritmo de Chandy-Lamport são satisfeitas.

Conforme o algoritmo, o módulo DiMEx, estendido para snapshot, pode receber/tratar também uma mensagem de snapshot. Cada snapshot tem um identificador único criado no processo que inicia o mesmo.
Todo processo, ao gravar seu estado, grava este identificador junto.
O estado deve incluir suas variáveis e o estado dos seus canais de entrada, conforme o algoritmo de snapshot.
Os (diversos) snapshots completos devem ser avaliados junto ao funcionamento do sistema.

Realize as seguintes etapas, e demonstre os resultados no dia da apresentação:

0. Rode o DIMEX com no mínimo 3 processos.
1. Faça um processo iniciar snapshots sucessivos, cada um com um identificador (`1`, `2`, `3` ...) concorrentemente aos seus acessos como um processo usuário do DIMEX.
2. Colha uma sequencia de snapshots (algumas centenas). Eles devem estar em arquivos separados, um para cada processo.
3. Escreva uma ferramenta que avalia para cada snapshot se os estados dos processos estão consistentes.
   Para cada snapshot `SnId` a ferramenta lê os estados gravados por cada processo, respectivo ao snapshot `SnId`, e avalia se o mesmo está correto.
   Para isso você tem que enunciar **invariantes** do sistema. Invariante é algo que deve ser verdade em qualquer estado.
   
   *Exemplos:*
   * **Inv 1:** no máximo um processo na SC.
   * **Inv 2:** se todos processos estão em "não quero a SC", então todos waitings tem que ser falsos e não deve haver mensagens.
   * **Inv 3:** se um processo `q` está marcado como waiting em `p`, então `p` está na SC ou quer a SC.
   * **Inv 4:** se um processo `q` quer a seção crítica (nao entrou ainda), então o somatório de mensagens recebidas, de mensagens em transito e de flags waiting para `p` em outros processos deve ser igual a `N-1` (onde `N` é o número total de processos).
   * **Inv ... etc.**

   Cada invariante é um teste sobre um snapshot, uma `funcao_InvX(snapshot)` retorna um booleano com o resultado. Cada snapshot é avaliado para todas invariantes. A ferramenta avisa invariantes violadas e o snapshot.

4. Rode o sistema e avalie com a ferramenta. Se ela gerou avisos de violação de invariantes, avalie seu algoritmo (ou o algoritmo de snapshot). Para o DIMEX supostamente correto, as invariantes devem todas passar.
5. Insira falhas no DIMEX. Por exemplo, altere a condição de resposta para violar a SC, altere a mesma condição para bloquear.
6. Detecte estes casos com a análise de snapshots.

---

### Propriedades do Algoritmo de Exclusão Mútua Distribuída

Considerando a interface vista em aula com `Entry`, `Resp` e `Exit`:

* **DMX1** (não-postergação e não bloqueio): se um processo solicita `Entry`, decorrido algum tempo, o acesso será permitido, ou seja ele entrega `resp*`. *(Na implementação, significa que se em um processo distribuído, a aplicação escreve `dmxReq[Entry]` para o módulo DIMEX, então decorrido um tempo ele vai garantidamente escrever um `dmxResp` no canal de indicação do módulo DIMEX para a aplicação).*
* **DMX2** (mutex): Se um processo `p` entregou `dmxResp`, nenhum outro processo entregará `dmxResp` antes que `p` sinalize `Exit`. *(Na implementação, significa que se em um processo `p` o módulo DIMEX entregou `dmxResp` no canal de indicação para a aplicação, então em nenhum outro processo `q` o módulo DIMEX de `q` entregará `dmxResp` para sua aplicação antes que em `p` a aplicação escreva `dmxReq[EXIT]` no canal de requisição para DIMEX em `p`).*

*\* Assumimos que todo processo sinaliza Exit ao final do seu uso, e que seu uso termina. De outra forma, este algoritmo não garante progresso.*

#### ATENÇÃO:

Você pode simplificar a interface do DiMEx para ter somente as operações:
* **Lock** - aplicação chama Lock e fica bloqueada nesta operacao até que o acesso ao recurso tenha sido garantido.
* **Unlock** - chama para liberar o recurso.

Neste caso as propriedades ficariam:
* **DMX1** (não-postergação e não bloqueio): a operação `Lock`, quando invocada, termina decorrido um tempo.
* **DMX2** (mutex): Se um processo `p` terminou `Lock`, nenhum outro processo terminará `Lock` antes que `p` faça `Unlock`.

*Se você usar IA, pode usar também esta forma de especificar. Parece mais simples que a anterior.*

---

## Template para DiMEx

Abra o `.ZIP`. Ele vai criar a seguinte estrutura:

```
pasta SD/
    pasta PP2PLink/
        PP2PLink.go
    pasta DIMEX/
        DIMEX-Template.go
    chatComPPLink.go
    useDIMEX.go
    useDIMEX-f.go
    go.mod
```

O arquivo adicionado `useDIMEX-f.go` gera o arquivo `mxOUT.txt` que faz append de:
* `|` quando entra no MX e
* `.` quando sai de MX.

Todos processos acessam o mesmo arquivo. Este sistema funciona na mesma máquina ou em máquinas que compartilham o sistema de arquivos (enxergam os mesmos arquivos).

Se você deixar rodar por algum tempo, obterá um registro de milhares de entradas e saídas do MX. No arquivo nunca poderá ser encontrada a sub-string `||` significando duas entradas consecutivas no MX sem uma saída entre elas. Analogamente, a sub-string `..` também não deve ser encontrada. Ou seja, o arquivo é composto somente por sequencias de `|.|.|.`.

Após a execução você pode abrir o arquivo `mxOUT.txt` em um editor txt comum e procurar por `||`, devendo dar zero ocorrências.
