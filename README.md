# Trabalho 1 - Parte 1 (DiMeX em Python)

Implementacao da exclusao mutua distribuida com modularidade em camadas:

1. `dimex/linkPerfeito.py`: modulo PL (Perfect Link) sobre sockets TCP.
2. `dimex/dimex.py`: algoritmo de exclusao mutua distribuida (interface `Lock` e `Unlock`).
3. `processoDimex.py`: aplicacao de testes concorrente que usa o DiMeX.
4. `validarSaida.py`: verificador de violacoes (`||` e `..`) no arquivo compartilhado.

## Requisitos

- Python 3.10+
- Linux, macOS ou Windows
- Varios processos executando com acesso ao mesmo arquivo compartilhado

## Arquivos principais

- `processosExemplo.json`: configuracao de 3 processos locais (127.0.0.1:6101..6103)
- `mxOUT.txt`: arquivo compartilhado gerado no teste

## Como executar (3 processos)

### Opcao automatizada (script shell)

No Linux com interface grafica, use o script abaixo para abrir 4 terminais:

- 3 terminais executam `processoDimex.py` (um por processo)
- 1 terminal aguarda os 3 processos terminarem e executa `validarSaida.py`
- os terminais permanecem abertos ao final

```bash
./rodar_dimex.sh
```

Observacoes da opcao automatizada:

- O script limpa `mxOUT.txt` antes de iniciar.
- O script procura um terminal suportado nesta ordem: `gnome-terminal`, `xfce4-terminal`, `konsole`, `xterm`.
- A quantidade de acessos por processo esta definida no script (`QTD_ACESSOS=2000`).

### Opcao manual

### 1. Limpar arquivo de saida

```bash
rm -f mxOUT.txt
```

### 2. Abrir 3 terminais no diretorio do projeto e iniciar os processos

Terminal 1:

```bash
python3 processoDimex.py --idProcesso 1 --configProcessos processosExemplo.json --arquivoCompartilhado mxOUT.txt --quantidadeAcessos 2000
```

Terminal 2:

```bash
python3 processoDimex.py --idProcesso 2 --configProcessos processosExemplo.json --arquivoCompartilhado mxOUT.txt --quantidadeAcessos 2000
```

Terminal 3:

```bash
python3 processoDimex.py --idProcesso 3 --configProcessos processosExemplo.json --arquivoCompartilhado mxOUT.txt --quantidadeAcessos 2000
```

Observacoes:

- Cada acesso ao recurso escreve duas operacoes no arquivo: primeiro `.` e depois `|`.
- Nao ha `sleep` entre as duas escritas.
- O uso eh intensivo para aumentar chance de detectar problemas.

### 3. Validar exclusao mutua

```bash
python3 validarSaida.py --arquivo mxOUT.txt
```

Resultado esperado:

- Sem violacoes (`||` e `..` nao aparecem)
- Sequencia alternada no arquivo, por exemplo: `.|.|.|.|...`

## Como adaptar para mais processos

1. Edite `processosExemplo.json` adicionando novos `idProcesso`, `host` e `porta`.
2. Rode um terminal por processo com o `--idProcesso` correspondente.
3. Todos devem apontar para o mesmo `--arquivoCompartilhado`.

## Resumo do algoritmo (DiMeX)

- Quando um processo chama `Lock`, ele envia `PEDIDO` para todos os outros.
- Ele bloqueia ate receber `RESPOSTA` de todos.
- Se dois processos pedem ao mesmo tempo, a prioridade eh decidida por `(timestampLamport, idProcesso)`.
- Quando um processo chama `Unlock`, ele envia respostas que ficaram adiadas para manter a exclusao mutua.
