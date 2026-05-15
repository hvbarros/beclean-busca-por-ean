# Recomendações de melhoria — Instruções para Workers BeClean

Documento gerado a partir da revisão das instruções publicadas em:

<https://propostas.baselabs.com.br/beclean/instrucoes_workers/>

## Objetivo da revisão

Avaliar as instruções com o olhar do worker que vai executar a tarefa, identificando:

- dúvidas prováveis durante a operação;
- pontos que podem gerar interpretações diferentes entre workers;
- informações ausentes ou pouco claras;
- ajustes necessários para tornar o material mais autossuficiente.

## Diagnóstico geral

As instruções estão bem encaminhadas e já apresentam uma estrutura útil para execução: contexto do projeto, responsáveis, Drive, planilha, WhatsApp, evidências, fluxo da Tarefa 1 e lista de categorias.

O principal problema não parece ser falta de conteúdo, mas sim a ausência de regras operacionais para situações ambíguas. É nesses pontos que o worker tende a travar, interromper a execução para perguntar ou tomar decisões diferentes de outros workers.

A documentação atual parece suficiente para alguém acompanhado no primeiro dia, mas ainda não está totalmente autossuficiente para execução independente.

---

## Principais dúvidas prováveis dos workers

| Ponto | Dúvida provável do worker | Ajuste recomendado |
|---|---|---|
| Coleta de Rua | Existe Tarefa 2? Onde está o passo a passo? | Criar uma página específica para **Tarefa 2 — Coleta de Rua**, no mesmo nível da Tarefa 1, com fluxo completo, evidências e critérios de aprovação/revisão. |
| Numeração dos passos | Por que o fluxo começa no Passo 2? | Inserir um **Passo 1 — Preparação do dia**, explicando abertura do Hub, Drive, planilha, pasta do dia, marca/faixa atribuída e teste de login. |
| Atribuição de marcas/datas | Onde vejo minhas marcas? Quem me passa? O que faço quando acabar? | Explicitar onde a atribuição fica registrada e o que fazer quando não houver produtos para a marca ou quando o lote terminar. |
| Volume e produtividade | Quantos produtos devo fazer por dia? Existe meta mínima? Como reporto horas? | Criar uma seção de **rotina diária esperada**, com início/fim, registro de tempo, pausas, meta indicativa e regra para reportar impedimentos. |
| Screenshots | Preciso tirar print de tudo mesmo? Quantos prints por produto? | Criar um checklist objetivo de evidências por cenário: produto aprovado, produto em revisão, link quebrado, categoria corrigida e ingredientes divergentes. |
| Nome do produto | Mudança de volume, cor, fragrância ou versão reprova? | Adicionar exemplos práticos: grafia diferente, tamanho diferente, cor/fragrância diferente, kit vs unidade, embalagem antiga vs nova. |
| Imagem | Imagem com fundo colorido da própria marca pode? Kit pode? Mockup pode? | Detalhar critérios de imagem: fundo permitido, embalagem cortada, múltiplos produtos, pessoa segurando, propaganda, selo, marca d’água, kit, refil e baixa resolução. |
| EAN | Se o EAN não aparece em nenhum site, reprovo? Se aparece outro produto parecido? | Criar uma árvore de decisão para EAN encontrado, EAN divergente, EAN ausente, EAN não encontrado e EAN de variação diferente. |
| Categoria/Subcategoria | O produto cabe em duas categorias. Qual priorizar? | Adicionar regras de precedência entre categorias e exemplos de casos ambíguos. |
| Uso de IA para ingredientes | Posso colar dados do Hub no ChatGPT/Claude grátis? Há algum cuidado? | Incluir política curta de uso de IA: o que pode e não pode ser colado, cuidados com dados internos e responsabilidade da decisão final. |
| Ingredientes | Diferença de ordem sempre reprova? INCI vs português é ok? Lista truncada reprova? | Criar exemplos de conclusão: aprovado, ingredientes faltantes/extras, ordem divergente, lista truncada e possível produto diferente. |
| Motivo de revisão | Se tiver foto errada e ingredientes errados, qual motivo escolho? | Definir regra de prioridade para escolher um único motivo e orientar detalhamento dos demais problemas na observação. |
| Planilha | Atualizo a cada produto ou por bloco? O que é bloco? | Padronizar atualização, preferencialmente uma linha por produto concluído imediatamente após aprovação/revisão. |
| Problemas técnicos | E se o Hub cair, filtro não funcionar, loja bloquear acesso ou site pedir CEP/cookie? | Criar uma seção de troubleshooting com problemas comuns e ação esperada. |

---

## Recomendações de melhoria

### 1. Criar uma página específica para a Tarefa 2 — Coleta de Rua

A introdução menciona duas frentes de trabalho:

1. Validação de Scraping;
2. Validação de Coleta de Rua.

Porém, o detalhamento disponível está concentrado na Tarefa 1. Para evitar dúvidas, é importante criar uma página separada para a Coleta de Rua, contendo:

- objetivo da tarefa;
- quando ela deve ser executada;
- passo a passo completo;
- evidências obrigatórias;
- padrão de fotos;
- como registrar na planilha;
- como nomear arquivos;
- critérios de aprovação/revisão;
- exemplos de casos corretos e incorretos;
- canal para dúvidas.

### 2. Incluir um checklist de início do dia

Sugestão de texto:

```md
## Antes de começar

1. Abrir o Hub e confirmar que o login está funcionando.
2. Abrir a pasta do Drive correspondente ao seu worker.
3. Criar ou acessar a pasta do dia.
4. Criar ou acessar a subpasta `screenshots`.
5. Abrir a planilha de controle.
6. Confirmar a marca/faixa atribuída para o dia.
7. Aplicar os filtros necessários no Hub.
8. Tirar o print inicial dos filtros aplicados.
9. Iniciar a validação do primeiro produto.
```

Esse checklist reduz erro de organização e ajuda o worker novo a começar sem depender de orientação verbal.

### 3. Criar um checklist por produto

Sugestão de checklist operacional:

```md
## Checklist por produto — Validação de Scraping

Para cada produto:

1. O link da loja abre corretamente?
2. O produto exibido na loja corresponde ao produto do Hub?
3. O nome está equivalente?
4. A imagem está no padrão esperado?
5. O EAN existe e confere?
6. A categoria e subcategoria estão corretas?
7. As listas de ingredientes são equivalentes?
8. A decisão final é aprovar ou enviar para revisão?
9. O screenshot obrigatório foi salvo?
10. A planilha foi atualizada?
```

Esse formato funciona como uma “cola operacional” para o worker seguir durante a execução.

### 4. Separar evidência mínima de evidência complementar

A regra de tirar screenshots de todas as telas conferidas pode gerar interpretações diferentes: alguns workers podem tirar prints demais, outros de menos.

Sugestão de padronização:

```md
## Evidência mínima — Produto aprovado

Salvar screenshots de:

1. filtros aplicados no lote;
2. ficha do produto no Hub;
3. página da loja mostrando o produto correto;
4. validação do EAN;
5. categoria/subcategoria;
6. quadrantes ou campos de ingredientes;
7. conclusão da IA, quando usada;
8. toast ou mensagem de aprovação.
```

```md
## Evidência mínima — Produto enviado para revisão

Salvar screenshots de:

1. tela que mostra o problema encontrado;
2. motivo de revisão selecionado;
3. observação preenchida;
4. toast ou mensagem de envio para revisão.
```

```md
## Evidência complementar

Salvar evidências adicionais quando houver:

- link quebrado;
- produto diferente;
- imagem inadequada;
- EAN divergente;
- categoria ambígua;
- ingredientes incompletos;
- divergência entre INCI e português;
- erro técnico no Hub ou na loja.
```

### 5. Criar regras mais objetivas para nome do produto

A validação do nome precisa de exemplos. Sugestão:

```md
## Nome do produto — Critérios

Aprovar quando:

- houver apenas diferença de grafia;
- a ordem das palavras for diferente, mas o produto for claramente o mesmo;
- houver abreviação ou expansão do nome sem alterar a versão do produto.

Enviar para revisão quando:

- o volume/tamanho for diferente;
- a fragrância for diferente;
- a cor/tonalidade for diferente;
- a versão for diferente;
- o link mostrar um kit, mas o Hub indicar unidade;
- o link mostrar unidade, mas o Hub indicar kit;
- houver dúvida se a embalagem antiga e a nova são o mesmo produto.
```

### 6. Detalhar critérios de imagem

Sugestão de critérios:

```md
## Imagem — Critérios

Aprovar quando:

- a embalagem estiver visível;
- o produto corresponder ao nome/link;
- a imagem tiver boa resolução;
- o fundo for branco ou claro;
- não houver elementos que prejudiquem a identificação do produto.

Enviar para revisão quando:

- a imagem mostrar produto diferente;
- a imagem mostrar kit em vez de unidade, ou unidade em vez de kit;
- houver pessoa, rosto, corpo ou mão como elemento principal;
- a imagem estiver cortada;
- a imagem estiver muito baixa resolução;
- houver propaganda, banner ou composição publicitária;
- houver marca d’água relevante;
- a embalagem não permitir identificar claramente o produto;
- a imagem for mockup ou ilustração e não representar bem o produto real.
```

### 7. Criar árvore de decisão para EAN

Sugestão:

```md
## EAN — Árvore de decisão

1. O EAN está presente no Hub?
   - Sim: seguir para validação.
   - Não: enviar para revisão com observação.

2. O EAN foi encontrado em fonte externa?
   - Sim: verificar se marca, nome, versão e volume correspondem.
   - Não: enviar para revisão com observação informando que o EAN não foi localizado.

3. O EAN encontrado corresponde exatamente ao produto?
   - Sim: aprovar esse critério.
   - Não: enviar para revisão.

4. O EAN corresponde a produto parecido, mas com tamanho, fragrância, versão ou kit diferente?
   - Enviar para revisão.

5. O EAN aparece em mais de uma fonte com informações divergentes?
   - Enviar para revisão e registrar as fontes divergentes na observação.
```

### 8. Criar regras de precedência para categoria/subcategoria

A lista de categorias é útil, mas não resolve casos em que um produto cabe em mais de uma classificação.

Sugestão de orientação:

```md
## Categoria/Subcategoria — Regra geral

Quando um produto puder se encaixar em mais de uma categoria, priorizar a finalidade principal do produto conforme nome, embalagem e descrição da loja.
```

Exemplos de casos que devem ter regra explícita:

| Caso | Dúvida | Regra sugerida |
|---|---|---|
| Protetor solar infantil | Baby Care ou Proteção Solar? | Definir precedência oficial. |
| Lip balm com FPS | Lábios, Maquiagem/Boca ou Proteção Solar? | Definir pela finalidade principal ou regra específica. |
| Shampoo masculino | Cabelos ou Produtos Masculinos? | Definir se “masculino” é categoria prioritária ou apenas atributo. |
| Produto multifuncional cabelo/corpo | Cabelos, Corpo ou Banho? | Priorizar aplicação principal descrita na embalagem. |
| Produto infantil para cabelo | Baby Care ou Cabelos? | Definir precedência oficial. |

### 9. Padronizar o uso de IA para ingredientes

Sugestão de texto:

```md
## Uso de IA para comparação de ingredientes

A IA pode ser usada apenas como apoio para comparar listas de ingredientes.

Não cole na IA:

- login;
- senha;
- dados pessoais;
- prints com informações sensíveis;
- informações internas que não sejam necessárias para a comparação;
- dados de clientes ou fornecedores que não façam parte da tarefa.

A IA não toma a decisão final. A decisão final deve seguir os critérios deste documento.

Em caso de dúvida, envie para revisão e registre a justificativa.
```

Sugestão de conclusão esperada da IA:

```md
A conclusão deve terminar com uma das opções:

- APROVADO — listas equivalentes;
- REVISÃO — ingredientes faltantes/extras;
- REVISÃO — ordem divergente;
- REVISÃO — lista truncada/incompleta;
- REVISÃO — possível produto diferente.
```

### 10. Criar exemplos de decisão para ingredientes

Sugestão:

```md
## Ingredientes — Critérios de decisão

Aprovar quando:

- as listas forem equivalentes;
- houver diferença apenas entre nomes em português e INCI, desde que sejam equivalentes;
- houver diferença de caixa, acentuação ou pontuação sem alteração do ingrediente;
- a ordem estiver correta e os ingredientes forem os mesmos.

Enviar para revisão quando:

- houver ingrediente faltante;
- houver ingrediente extra;
- a ordem dos ingredientes estiver divergente;
- a lista parecer truncada;
- a composição parecer ser de outro produto;
- a lista da loja e a lista do Hub forem incompatíveis;
- houver dúvida relevante sobre equivalência.
```

### 11. Definir prioridade para motivo de revisão

Como o Hub permite selecionar apenas um motivo, é importante definir uma ordem de prioridade.

Sugestão:

```md
## Motivo de revisão — Regra de prioridade

Quando houver mais de um problema no mesmo produto, selecionar apenas um motivo principal e detalhar todos os problemas na observação.

Prioridade sugerida:

1. Link inexistente, quebrado ou página sem produto.
2. Produto diferente no link da loja.
3. Imagem fora do padrão.
4. Categoria ou subcategoria incorreta.
5. Ingredientes divergentes.
6. Ordem de ingredientes divergente.
7. Problema de apresentação que não afeta composição, categoria ou identidade do produto.
```

Exemplo de observação:

```md
Produto enviado para revisão por imagem fora do padrão. Também foi identificada divergência nos ingredientes: a lista da loja contém ingrediente extra não presente no Hub.
```

### 12. Padronizar atualização da planilha

Sugestão:

```md
## Atualização da planilha

A planilha deve ser atualizada imediatamente após cada produto aprovado ou enviado para revisão.

Cada linha deve representar um produto concluído.

Não deixar para atualizar apenas no final do dia, para evitar perda de rastreabilidade.
```

Caso seja mantido o conceito de “bloco”, definir:

```md
Um bloco corresponde a uma sequência contínua de até X produtos ou até X minutos de trabalho, o que ocorrer primeiro.
```

### 13. Criar seção de problemas comuns

Sugestão:

```md
## Problemas comuns e o que fazer

| Problema | O que fazer |
|---|---|
| Hub fora do ar | Registrar horário, tirar print do erro e avisar no grupo. |
| Login expirado | Tentar login novamente. Se persistir, avisar o responsável. |
| Filtro não funciona | Tirar print, atualizar a página e tentar novamente. Se persistir, avisar. |
| Link da loja quebrado | Registrar evidência e enviar produto para revisão. |
| Site da loja pede CEP | Informar CEP padrão, se houver. Caso não exista CEP padrão definido, perguntar no grupo. |
| Pop-up de cookie atrapalha | Fechar ou aceitar cookies, se necessário, e seguir a validação. |
| Produto indisponível na loja | Validar se a página ainda mostra nome, imagem, EAN e ingredientes. Se não mostrar, enviar para revisão. |
| Página sem ingredientes | Registrar evidência e enviar para revisão. |
| EAN não encontrado | Registrar busca e enviar para revisão. |
| Botão de copiar não funciona | Copiar manualmente, se possível. Se não for possível, registrar evidência. |
```

---

## Recomendações por prioridade

### Prioridade alta

Esses ajustes devem ser feitos antes de escalar a operação para mais workers.

1. Publicar o passo a passo da **Tarefa 2 — Coleta de Rua**.
2. Criar checklist de início do dia.
3. Criar checklist por produto.
4. Definir evidência mínima por cenário.
5. Criar árvore de decisão para motivo de revisão.
6. Incluir regras para EAN ausente, não encontrado ou divergente.
7. Criar política curta para uso de IA.

### Prioridade média

Esses ajustes reduzem retrabalho e aumentam consistência.

1. Melhorar regras de categoria com precedência.
2. Adicionar exemplos de casos ambíguos.
3. Padronizar atualização da planilha.
4. Criar seção de troubleshooting.
5. Adicionar exemplos de decisão para ingredientes.

### Prioridade baixa

Esses ajustes melhoram a experiência do worker e facilitam treinamento.

1. Criar FAQ no final.
2. Incluir um exemplo completo de produto aprovado.
3. Incluir um exemplo completo de produto enviado para revisão.
4. Transformar a lista de categorias em tabela pesquisável.
5. Criar versão resumida para consulta rápida durante a execução.

---

## Estrutura sugerida para a documentação final

```md
# Instruções para Workers — BeClean

## 1. Visão geral do projeto

## 2. Responsáveis e canais de comunicação

## 3. Ferramentas necessárias

## 4. Organização do Drive

## 5. Planilha de controle

## 6. Rotina diária do worker

## 7. Checklist de início do dia

## 8. Tarefa 1 — Validação de Scraping

### 8.1 Objetivo
### 8.2 Filtros
### 8.3 Checklist por produto
### 8.4 Nome do produto
### 8.5 Imagem
### 8.6 EAN
### 8.7 Categoria e subcategoria
### 8.8 Ingredientes
### 8.9 Uso de IA
### 8.10 Aprovação
### 8.11 Envio para revisão
### 8.12 Evidências obrigatórias

## 9. Tarefa 2 — Coleta de Rua

### 9.1 Objetivo
### 9.2 Quando executar
### 9.3 Checklist de coleta
### 9.4 Evidências obrigatórias
### 9.5 Critérios de aprovação/revisão

## 10. Categorias e subcategorias

## 11. Problemas comuns e o que fazer

## 12. FAQ

## 13. Exemplos completos
```

---

## Exemplo de FAQ para incluir

```md
## FAQ

### O que faço se o produto não tiver EAN?

Envie para revisão e registre na observação que o EAN está ausente no Hub.

### O que faço se o EAN não for encontrado em nenhuma fonte?

Envie para revisão e registre que o EAN não foi localizado nas fontes consultadas.

### O que faço se a loja mostrar o produto certo, mas com outra imagem?

Avalie se a imagem representa o mesmo produto. Se houver dúvida ou se a imagem estiver fora do padrão, envie para revisão.

### O que faço se a lista de ingredientes estiver em português em uma fonte e em INCI em outra?

Compare a equivalência dos ingredientes. Se forem equivalentes, pode aprovar. Se houver dúvida, envie para revisão.

### O que faço se o produto tiver mais de um problema?

Escolha o motivo principal seguindo a prioridade definida e detalhe todos os problemas na observação.

### Posso usar IA para decidir?

A IA pode apoiar a comparação de ingredientes, mas a decisão final deve seguir as regras da documentação.

### Quando devo atualizar a planilha?

Imediatamente após concluir cada produto.
```

---

## Avaliação final

As instruções atuais são adequadas para iniciar a operação com acompanhamento, mas ainda precisam de melhorias para execução independente.

Os principais ajustes necessários são:

- transformar o fluxo em checklists operacionais;
- explicitar regras para casos ambíguos;
- definir evidência mínima;
- padronizar motivo de revisão;
- documentar a Tarefa 2;
- orientar melhor o uso de IA;
- criar exemplos completos.

Com esses ajustes, a documentação tende a reduzir dúvidas no grupo, retrabalho dos gestores e variação de critérios entre workers.
