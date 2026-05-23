# Tarefas para Workers — BeClean

**Responsável (Gestor de Contrato):** Hugo Barros — hbarros@baselabs.com.br
**Pontos focais BeClean:** Marina da Costa Miranda, Elaine da Silva
**Versão:** 1.5 — 11/05/2026

---

## Público deste documento {#publico}

Este documento é a **referência oficial dos workers BASE/labs alocados ao projeto BeClean** — profissionais contratados pela BASE/labs para executar a validação dos produtos no Hub da BeClean.

**Quem deve ler:** todos os workers, antes e durante a execução das tarefas. Antes do primeiro dia, leia o documento por completo. Durante a operação, mantenha-o aberto como apoio — aqui estão os passos detalhados, as evidências esperadas, as regras de execução e o canal de dúvidas.

O **gestor de contratos da BASE/labs** é o ponto de contato principal e responde dúvidas via WhatsApp (ver "Canal de dúvidas").

---

## 1. Introdução {#sec-introducao}

A BeClean é uma empresa que mantém uma base curada de produtos cosméticos e de higiene pessoal, com foco em análise de ingredientes e classificação por categoria. Para alimentar e manter essa base, a BeClean opera o **Hub** — uma plataforma interna onde produtos chegam por três caminhos principais: scraping de sites de lojas, enriquecimento por bases de cosméticos públicas e privadas e coleta de campo em farmácias.

A BASE/labs foi contratada para executar a **validação de scraping (Pré-Aprovados)** — conferência de produtos importados via web scraping, garantindo que imagem, nome, EAN, categoria e lista de ingredientes estejam corretos antes da aprovação para produção.

Este documento detalha o passo a passo dessa tarefa, a estrutura de entrega das evidências no Google Drive, a planilha de controle, o canal de dúvidas e as regras gerais de execução.

---

## 2. Sumário {#sec-sumario}

- [Público deste documento](#publico)
1. [Introdução](#sec-introducao)
2. [Sumário](#sec-sumario)
3. [Regras gerais de execução](#sec-regras)
4. [Organização no Google Drive (pasta por worker)](#sec-drive)
5. [Canal de dúvidas — Grupo de WhatsApp](#sec-duvidas)
6. [Planilha de controle de produtividade](#sec-planilha)
7. [Tarefa 1 — Validação de Scraping (Pré-Aprovados)](#sec-tarefa-1)
8. [Pendências do Hub que afetam a execução](#sec-pendencias)
9. [Anexos a serem incluídos](#sec-anexos)

---

## 3. Regras gerais de execução {#sec-regras}

- **Acesso ao Hub:** `https://hub.beclean.com.br/` — login com e-mail e senha individual fornecidos pela BeClean
- **Trabalho por marca:** nunca há dois workers na mesma marca. As marcas atribuídas são enviadas pelo gestor de contratos via WhatsApp ou e-mail — podendo receber uma ou mais marcas de uma vez. Ao concluir, avisar o gestor para receber o próximo lote
- **Evidências obrigatórias:** screenshots de todas as telas conferidas, salvos na pasta do EAN correspondente, no Drive. Como alternativa, é aceito um único arquivo de gravação de tela (vídeo) por EAN, salvo na pasta do EAN correspondente
- **Comunicação:** dúvidas pontuais vão para o grupo de WhatsApp (ver "Canal de dúvidas"); dúvidas conceituais sobre produtos/categorias podem ser anotadas na coluna "Observações" da planilha
- **Não criar motivos novos de revisão:** usar apenas os motivos já existentes no Hub. Texto livre adicional vai no campo de observação do produto
- **Padrão de qualidade:** melhor enviar para revisão em caso de dúvida do que aprovar incorretamente
- **Screenshots:** no Windows, use a ferramenta de Recorte (`Win + Shift + S`), o Snipping Tool, o atalho `Print Screen` ou o [Greenshot](https://getgreenshot.org/) (gratuito, recomendado). Salve sempre no formato `.png`.
- **Gravação de tela (alternativa aos screenshots):** se preferir gravar a tela em vez de tirar screenshots, use o Xbox Game Bar (`Win + G`) ou o OBS Studio (gratuito). Salve um arquivo de vídeo por EAN (`[EAN].mp4`) diretamente na pasta do EAN — **não** dentro de `screenshots`. Use screenshots **ou** vídeo para cada EAN, não os dois.

> **Atenção:** O trabalho deve ser feito em um **notebook ou desktop**. Não é possível executar as tarefas via celular — o Hub e o Google Drive precisam ser acessados em um navegador de computador.

### 3.1. Checklist de início do dia {#sec-checklist-dia}

Antes de iniciar a validação dos produtos, confirmar cada item abaixo:

1. Fazer login no Hub (`https://hub.beclean.com.br/`) e confirmar que está funcionando
2. Abrir a pasta do worker no Drive compartilhado
3. Confirmar a marca atribuída (enviada pelo gestor via WhatsApp ou e-mail)
4. Dentro de `evidencias`, criar a pasta da marca (se ainda não existir)
5. Abrir a planilha de controle e registrar o horário de início
6. Aplicar os filtros no Hub conforme o Passo 2
7. Registrar a evidência inicial dos filtros aplicados (screenshot ou início da gravação de tela)
8. Iniciar a validação do primeiro produto

> **Evidências por EAN:** para cada produto, a evidência pode ser feita em **screenshots** (salvo na subpasta `screenshots` do EAN) **ou** em **vídeo** (arquivo `[EAN].mp4` na pasta do EAN) — escolha um formato por EAN, não os dois.

---

## 4. Organização no Google Drive (pasta por worker) {#sec-drive}

### 4.1. Estrutura

Cada worker terá uma pasta exclusiva dentro do Drive compartilhado da BASE/labs, criada e compartilhada pelo gestor de contratos da BASE/labs antes do início dos trabalhos. A estrutura padrão é:

```
📁 BASE-labs (Drive compartilhado)
└── 📁 Projetos
    └── 📁 BeClean — Workers
        └── 📁 [Nome do Worker] — [Ano-Mês de início]
            ├── 📄 Planilha de Controle — [Nome do Worker]   (Google Sheets)
            └── 📁 evidencias
                └── 📁 [Marca]
                    └── 📁 [EAN]
                        ├── 📁 screenshots          ← opção A: pasta com screenshots
                        │   └── 📄 passo3-01.png    (ou outros nomes ordenáveis)
                        ├── 📄 observações.txt (opcional)
                        └── 🎥 [EAN].mp4            ← opção B: vídeo direto na pasta do EAN
```

> **Screenshots ou vídeo — escolha um por EAN.** Não é necessário (nem esperado) ter os dois para o mesmo produto.

### 4.2. Regras de nomenclatura

- **Pasta do worker:** `[Nome Completo] — [AAAA-MM]`. Ex.: `Maria Silva — 2026-05`
- **Pasta de marca:** nome da marca conforme aparece no Hub. Ex.: `Natura`
- **Pasta de EAN:** o código EAN do produto. Ex.: `7891234567890`
- **Screenshot:** qualquer nome que permita ordenação é aceito. Formatos válidos:
  - `[Passo]-[NN].png` — Ex.: `passo3-01.png` *(padrão recomendado)*
  - `[NN].png` — Ex.: `01.png`, `02.png`
  - Qualquer nome com prefixo numérico ou de data que garanta ordem alfabética correta — Ex.: `2026-05-22_01.png`
  - Também é aceito confiar na **data de modificação do arquivo** para ordenação, desde que ela reflita a ordem real de captura (o que ocorre naturalmente ao tirar screenshots em sequência)
  - Não usar acentos, espaços no início/fim do nome, nem caracteres especiais (`/ \ : * ? " < > |`) em nenhum nome de arquivo ou pasta
- **Gravação de tela (alternativa exclusiva aos screenshots):** `[EAN].mp4` — o nome do arquivo deve ser o código EAN do produto. Ex.: `7891234567890.mp4`. Salvo **diretamente na pasta `[EAN]`**, não dentro de `screenshots`. Use screenshots **ou** vídeo para cada EAN — não os dois.

### 4.3. O que o worker deve fazer

1. Acessar a pasta compartilhada que recebeu por e-mail/Drive
2. Confirmar que enxerga sua planilha de controle e a subpasta `evidencias`
3. Para cada produto, criar a pasta da marca (se ainda não existir) e dentro dela a pasta com o EAN do produto
4. Para cada EAN, salvar a evidência de **uma** das duas formas (não as duas):
   - **Screenshots:** dentro da subpasta `screenshots` da pasta do EAN
   - **Vídeo:** arquivo `[EAN].mp4` diretamente na pasta do EAN (ex.: `7891234567890.mp4`)
5. Atualizar a planilha de controle ao final de cada produto conferido (ver seção 6)

### 4.4. O que o worker NÃO deve fazer

- Compartilhar a pasta com terceiros
- Baixar fotos/dados de produtos para fora do Drive compartilhado
- Renomear subpastas já criadas (criar uma nova se houver erro)
- Trabalhar fora do Hub (capturas devem ser feitas a partir do Hub oficial)

---

## 5. Canal de dúvidas — Grupo de WhatsApp {#sec-duvidas}

Para suporte em tempo real durante a execução das tarefas, todos os workers alocados ao projeto serão incluídos em um **grupo de WhatsApp** dedicado.

### 5.1. Moderadores e pontos focais

- **Gestor de contratos (BASE/labs)** — ponto de contato principal para o worker, intermediário com a BeClean e responsável administrativo do projeto
- **Ponto focal técnico (BeClean)** — dúvidas sobre produtos, categorias e regras de negócio
- **Ponto focal operacional (BeClean)** — dúvidas sobre o Hub e o fluxo de validação

### 5.2. Horário de atendimento

O grupo cobre **toda a jornada de trabalho do worker**. Como os workers podem ter rotinas diferentes, dúvidas podem ser enviadas a qualquer momento — a equipe de moderação responderá assim que possível dentro do horário de cada moderador. Para máxima agilidade, evitar acumular dúvidas: enviar à medida que aparecerem.

### 5.3. Boas práticas no grupo

- **Identifique a tarefa** ao enviar uma dúvida: começar com "[Scraping]"
- **Anexe screenshot** sempre que possível — facilita o diagnóstico
- **Informe o produto/EAN/marca** em questão
- **Antes de perguntar, consulte este documento** — muitas dúvidas estão respondidas aqui
- **Não compartilhe** informações do grupo, prints do Hub ou dados de produtos fora dele
- **Dúvidas conceituais recorrentes** (categoria de um produto, padrão de nomenclatura, etc.) podem virar atualizações deste documento — vale a pena registrar

### 5.4. Quando NÃO usar o grupo

- Anomalias que não bloqueiam o trabalho do dia → anotar na coluna "Observações" da planilha de controle
- Comentários gerais ou sociais → o grupo é estritamente operacional
- Assuntos contratuais ou administrativos → tratar diretamente com o gestor de contratos da BASE/labs, fora do grupo

---

## 6. Planilha de controle de produtividade {#sec-planilha}

Cada worker recebe um **Google Sheets** próprio, copiado a partir de um template único. A planilha vive dentro da pasta do worker e é atualizada ao final de cada produto conferido.

### 6.1. Colunas da planilha (template)

- **Data** — formato AAAA-MM-DD
- **Tarefa** — "Scraping"
- **Marca** — marca atribuída pelo gestor
- **Produto** — nome do produto conforme aparece no Hub
- **EAN** — código (quando aplicável)
- **Resultado** — "Aprovado", "Enviado para revisão", "Aprovado em lote" ou "Já estava revisado"
- **Motivo de revisão** — preenchido apenas quando enviado para revisão
- **Tempo gasto (min)** — estimativa
- **Pasta de screenshots** — link da subpasta correspondente no Drive
- **Observações** — texto livre (dúvidas, anomalias do Hub, etc.)

### 6.2. Frequência de atualização

- A planilha deve ser atualizada **a cada produto** ou, no mínimo, ao final de cada bloco de trabalho contínuo
- Não deixar acumular para o fim do dia — o objetivo é ter rastreabilidade em tempo real

> *[ESPAÇO PARA SCREENSHOT: imagem do template da planilha com colunas preenchidas como exemplo]*

---

## 7. Tarefa 1 — Validação de Scraping (Pré-Aprovados) {#sec-tarefa-1}

### 7.1. Descrição

Conferir produtos cosméticos importados via scraping (e eventualmente enriquecidos por bases de cosméticos públicas e privadas) no Hub da BeClean, validando imagem, nome, EAN, categoria/subcategoria e — principalmente — a consistência entre três listas de ingredientes (site da loja, scraping original e ingredientes vinculados no Hub). O objetivo é aprovar lotes corretos e enviar à revisão tudo que apresentar discrepância.

**Perfil:** não exige formação técnica específica, mas exige senso crítico para identificar inconsistências (ex.: um delineador com apenas 2 ingredientes provavelmente está errado).

**Organização:** por marca. Cada worker recebe uma lista de marcas exclusivas.

### 7.2. Checklist por produto {#sec-checklist-produto}

Use esta lista como referência rápida durante a execução. Cada item corresponde a um passo detalhado nas seções seguintes.

1. O link da loja abre e exibe o produto correto? → se não, **pular direto para o Passo 6** (não é necessário conferir os demais itens)
2. Conferir **todos** os itens abaixo, mesmo que algum falhe — anotar cada problema encontrado:
   - O nome corresponde ao mesmo produto?
   - A imagem está no padrão BeClean?
   - O EAN foi validado em fonte externa?
   - A categoria e subcategoria estão corretas? → corrigir no Hub se necessário
   - As três listas de ingredientes são equivalentes?
3. Todos os itens aprovados? → clicar em "Aprovar Produto" e aguardar toast → **pular para o Passo 7**
4. Algum item reprovado? → registrar todos os problemas na Observação e ir para o **Passo 6**
5. Evidências salvas? Escolha uma das duas formas:
   - **Screenshots por produto** (padrão) — salvar na subpasta `screenshots` do EAN:
     - **Passo 2** — filtros aplicados + contagem do lote *(uma vez por sessão)*
     - **Passo 3** — link da loja aberto + ficha do produto no Hub
     - **Passo 4** — um ou mais screenshots com: nome no Hub e no site; imagem do produto; resultado do EAN; categoria e subcategoria; três quadrantes de ingredientes + conclusão da IA
     - **Passo 5** *(se aprovado)* — botão "Aprovar Produto" + toast "Produto pronto para produção"
     - **Passo 6** *(se revisão)* — observação preenchida + motivo selecionado + toast "Produto marcado para revisão"
   - **Gravação de tela** (alternativa exclusiva) — um único arquivo de vídeo por EAN (`[EAN].mp4`, ex.: `7891234567890.mp4`), salvo **diretamente na pasta `[EAN]`** (não em `screenshots`). Usar screenshots **ou** vídeo — não os dois.
6. Planilha de controle atualizada?

### 7.3. Passo 2 — Filtrar pré-aprovados de scraping

> **Evidência:** um único screenshot que mostre simultaneamente os filtros aplicados e o rodapé com a contagem total do lote — ou dois screenshots separados caso não seja possível capturar tudo em uma tela. Esta evidência é tirada **uma vez por sessão**, não por produto.

- Ir para a aba **"Pré-Aprovados"**
- Aplicar os filtros:
  - **Marca Original (Scraping):** marca de trabalho atribuída
  - **Fonte (Origem):** Scrapping *(grafia do Hub — equivale a "scraping")*
  - **Enriquecimento por:** sem filtro de enriquecimento
  - **Categorizado por IA:** Todos
  - **Ordenar por Matching:** Maior Matching
- A lista aparece em ordem decrescente de Matching (começando em 100%)
- A **quantidade total** de produtos do lote é exibida ao final da página — anotar esse número
- Para iniciar a análise de um produto, clicar no botão **"Analisar"** na linha do produto

> *[ESPAÇO PARA SCREENSHOT 2.1: aba "Pré-Aprovados" com todos os filtros aplicados]*

> *[ESPAÇO PARA SCREENSHOT 2.2: rodapé da listagem mostrando a quantidade total do lote]*

### 7.4. Passo 3 — Abrir o link da loja {#sec-tarefa-1-link}

> **Evidência:** um ou dois screenshots mostrando o link da loja aberto e a ficha do produto no Hub (podem ser capturas separadas ou lado a lado, desde que ambos estejam visíveis).

Abrir o link da loja e usá-lo como referência principal para toda a conferência dos passos seguintes.

Caso o link **não exista, não abra ou abra em uma página sem produto**, ainda assim **valide o EAN** (item c do Passo 4) antes de encerrar a conferência do produto. Após validar o EAN, pular para o **Passo 6 — Envio para Revisão** e usar o motivo **"SITE"**.

> *[ESPAÇO PARA SCREENSHOT 3.a: link da loja aberto]*

> *[ESPAÇO PARA SCREENSHOT 3.b: ficha do produto no Hub]*

### 7.5. Passo 4 — Conferência item a item de cada produto

> **Evidência:** um ou mais screenshots por item, contendo as informações validadas. As capturas podem estar combinadas (vários itens na mesma tela) desde que todas as informações abaixo estejam visíveis em pelo menos uma captura:
> nome do produto no Hub e no site da loja; imagem do produto na ficha do Hub; resultado da consulta do EAN; categoria e subcategoria preenchidas; os três quadrantes de ingredientes (Lista A, B e C) e a conclusão da IA.

A ficha do produto traz os campos numerados na ordem de verificação. Seguir os itens em sequência, usando o link da loja aberto no passo anterior como referência.

#### a) Nome do produto {#item-4a}

Comparar o nome do Hub com o nome no site da loja. O nome não precisa ser idêntico — variações de grafia, abreviações e diferenças de formatação são aceitáveis, desde que os dois nomes façam referência claramente ao mesmo produto. O que não pode ocorrer é o nome apontar para um produto diferente (ex.: versão errada, tamanho diferente, linha diferente).

Contamos com o seu senso crítico para distinguir variações de escrita do mesmo produto de capturas incorretas.

> *[ESPAÇO PARA SCREENSHOT 4.a: comparação nome do Hub vs. nome no site da loja]*

#### b) Imagem {#item-4b}

**Padrão BeClean:** produto com fundo branco ou cores claras. Enviar para Revisão fotos com pessoas de fundo, partes do corpo, propaganda ou qualquer elemento fora do padrão.

> *[ESPAÇO PARA SCREENSHOT 4.b: área da imagem na ficha do produto]*

#### c) EAN {#item-4c}

Consultar o EAN em **um** dos três sites de validação abaixo (uma validação positiva basta para aprovação):

1. **[Cosmos](https://cosmos.bluesoft.com.br/)** — Catálogo de Produtos, GTIN, NCM, Tributação e Marca
2. **[Pesquisa de produto](https://pt.product-search.net/)** — busca por EAN, UPC, ISBN, GTIN ou nome do produto
3. **[Verified by GS1 / GS1 Brasil](https://verifiedbygs1.gs1br.org/)** — no site, clicar em **"Testar agora"**

**Árvore de decisão:**

- **EAN encontrado e produto corresponde** → aprovar este critério
- **EAN encontrado mas produto diverge** (tamanho, fragrância, versão ou kit diferente) → enviar para revisão; registrar na observação qual divergência foi encontrada
- **EAN não encontrado em nenhuma fonte** → enviar para revisão; registrar na observação que o EAN não foi localizado nas fontes consultadas
- **EAN aparece em mais de uma fonte com informações divergentes** → enviar para revisão; registrar as fontes e as divergências na observação

#### d) Categoria e Subcategoria {#item-4d}

Analisar a classificação atual usando o **[quadro padrão BeClean](/beclean/instrucoes_workers/categorias/)** (em caso de dúvida).

- **Havendo divergência e certeza da classificação correta:** clicar em **"Editar categoria"**, selecionar a Categoria e a Subcategoria corretas e clicar em **"Salvar classificação"**
- **Em caso de dúvida sobre a classificação correta:** não alterar — enviar para revisão com motivo **"Ajuste de Cate&Sub"** e registrar a dúvida na Observação
- A lista de subcategorias é filtrada conforme a categoria selecionada

> *[ESPAÇO PARA SCREENSHOT 4.d.1: campo de categoria/subcategoria]*

> *[ESPAÇO PARA SCREENSHOT 4.d.2: filtro "Editar categoria" com nova classificação + botão "Salvar classificação"]*

#### e) Avaliação de Ingredientes {#item-4e}

Comparar três listas usando IA:

- Ainda no link da loja, localizar o campo de ingredientes/composição
- Fazer uma **avaliação visual de 100% da página** — atenção a listas simplificadas com botão **"ver mais"**: clicar para liberar a composição completa antes de copiar

Coletar as três listas no Hub. **Cada quadrante tem o seu próprio botão de copiar** — não é necessário selecionar o texto manualmente:

- **Lista A** — Ingredientes do **link da loja**
- **Lista B** — Quadrante **Original (Scraping)** no Hub
- **Lista C** — Quadrante **Vinculados (DB)** no Hub

> **Atenção:** usar apenas contas gratuitas do **ChatGPT** ou **Claude** para esta etapa — não é necessário assinar nenhum plano pago.

**O que pode ser colado na IA:** apenas as listas de ingredientes copiadas dos quadrantes do Hub e do site da loja. **Não colar** login, senha, dados pessoais, prints com informações internas ou qualquer dado que não seja necessário para a comparação de ingredientes. A IA apoia a análise, mas a **decisão final é sempre sua**, com base nos critérios deste documento. Em caso de dúvida, envie para revisão.

Colar as três listas no chat usando o prompt abaixo. Substituir os blocos `[COLAR LISTA ...]` pelo conteúdo copiado de cada quadrante:

```
Compare 3 listas de ingredientes cosméticos (Lista A, Lista B e Lista C),
verificando se os ingredientes são os mesmos, se existe diferença na
quantidade de componentes, ingredientes faltando, extras ou duplicados,
e se as listas representam o mesmo produto cosmético. Considere
equivalentes ingredientes escritos em português & INCI.

Analise também a ordem dos ingredientes, informando se ela é igual ou
diferente entre as listas. Identifique pontos de atenção relevantes,
como nomes truncados ou alterações reais de composição.

Entregue uma conclusão objetiva e sucinta, deixando claro se as listas
estão aprovadas (sendo as três equivalentes entre si), se representam o
mesmo produto cosmético e se as formulações podem ser consideradas
equivalentes ou reprovadas.
Enviar CONCLUSÃO OBJETIVA.

Lista A (site da loja):
[COLAR LISTA A AQUI]

Lista B (Original / Scraping — Hub):
[COLAR LISTA B AQUI]

Lista C (Vinculados / DB — Hub):
[COLAR LISTA C AQUI]
```

> *[ESPAÇO PARA SCREENSHOT 4.e.1: três quadrantes (Lista A, B e C) destacando o botão "copiar" de cada um]*

> ⚠️ **Atenção — Perfume com fórmula aberta:** se o ingrediente "perfume" aparecer com sua composição detalhada (indicada por asteriscos, parênteses ou subitens com os componentes), **retire o "perfume" da lista** e considere apenas os componentes abertos individualmente. Envie o produto para revisão para que o ajuste seja feito no Hub.

> ⚠️ **Atenção — "Pode conter" e "Não contém":** ignore menções de "pode conter" (referentes a alérgenos) e "não contém" (marketing de ingrediente livre) ao comparar as listas. Se qualquer uma das listas do Hub incluir esses termos como ingredientes, envie o produto para revisão para que sejam removidos da composição.

> ℹ️ **Diferenças de idioma (português vs. INCI):** diferenças entre nomes em português e o padrão internacional INCI são tratadas automaticamente pelo sistema e **não devem ser consideradas divergência**. Ao usar a IA, oriente-a a focar na **equivalência química das substâncias**, não na grafia dos nomes.

> **Aviso:** conferir **todos** os itens a–e antes de qualquer ação. Se um ou mais critérios falharem, registrar todos os problemas encontrados na Observação e ir para o **Passo 6 — Envio para Revisão**. Nunca interromper a conferência no meio porque um item falhou.

### 7.6. Passo 5 — Aprovar o produto {#sec-tarefa-1-aprovar}

> **Evidência:** screenshot do botão "Aprovar Produto" e do toast de confirmação.

Se todos os itens do Passo 4 forem aprovados, concluir a validação:

- Clicar em **"Aprovar Produto"** (botão verde)
- Aguardar a mensagem no canto da tela: **"Produto pronto para produção"**

> *[ESPAÇO PARA SCREENSHOT 5.1: botão "Aprovar Produto"]*

> *[ESPAÇO PARA SCREENSHOT 5.2: toast de confirmação "Produto pronto para produção"]*

> **Aviso:** após a aprovação, pular direto para o **Passo 7 — Encerramento da jornada**.

### 7.7. Passo 6 — Envio para Revisão

> **Evidência:** screenshots mostrando a observação preenchida com a conclusão da IA ou descrição do problema, o motivo da revisão selecionado e o toast "Produto marcado para revisão". Podem estar em capturas separadas ou combinadas.

Usar este fluxo em dois casos: quando qualquer item do Passo 4 estiver fora de conformidade, **ou** quando o link da loja (Passo 3) não existir, não abrir ou abrir em uma página sem produto.

**1) Registrar a Observação**

- Na ficha do produto, localizar a aba **"Observação"** e clicar no **ícone do lápis**
- Colar a **conclusão da IA** (ou descrição textual do problema — ex.: "link da loja não abre")
- Clicar em **"Salvar"**
- Mesmo que existam **múltiplos motivos** de revisão, todos devem ser detalhados aqui em Observação (só um motivo será selecionado no próximo passo)

**2) Selecionar o Motivo da Revisão**

- Em **"Motivo da Revisão"**, escolher **apenas um** motivo entre os existentes na base. Quando houver mais de um problema, usar a prioridade abaixo para escolher o motivo principal e detalhar todos os demais na Observação:

  1. **SITE** — link inexistente, quebrado ou página sem produto
  2. **Ajuste de Foto** — imagem fora do padrão BeClean
  3. **Ajuste de Cate&Sub** — categoria ou subcategoria incorreta
  4. **Padronizar Ingredientes** — ingredientes faltantes, extras ou lista de outro produto
  5. **Ajustar - Ordem de Ingredientes** — ingredientes corretos mas em ordem divergente
  6. **Ajuste de Apresentação** — problema de apresentação que não afeta composição, categoria ou identidade do produto

> **Atenção:** nunca criar motivo novo. A opção "+ Criar novo motivo" existe na interface, mas deve ser ignorada — usar sempre um dos motivos existentes na lista acima.

**3) Confirmar a Revisão**

- Clicar em **"Confirmar Revisão"**
- Aguardar a mensagem no canto da tela: **"Produto marcado para revisão"**

> *[ESPAÇO PARA SCREENSHOT 6.1: aba Observação com o ícone do lápis em destaque]*

> *[ESPAÇO PARA SCREENSHOT 6.2: campo de Observação preenchido com a conclusão da IA + botão "Salvar"]*

> *[ESPAÇO PARA SCREENSHOT 6.3: motivo da revisão selecionado]*

> *[ESPAÇO PARA SCREENSHOT 6.4: botão "Confirmar Revisão" + toast "Produto marcado para revisão"]*

### 7.8. Passo 7 — Encerramento da jornada

> **Evidência:** planilha de controle atualizada com todos os produtos do dia e pasta de screenshots organizada no Drive.

- Salvar todos os screenshots na pasta do EAN no Drive (ver "Organização no Google Drive")
- Atualizar a planilha de controle com cada produto conferido
- Anotar dúvidas, anomalias do Hub e marcas com problemas estruturais na coluna "Observações"

---

## 8. FAQ — Perguntas e Problemas Frequentes {#sec-troubleshooting}

> **Atenção:** O trabalho deve ser feito em um **notebook ou desktop**. Não é possível executar as tarefas via celular — o Hub e o Google Drive precisam ser acessados em um navegador de computador.

| Problema / Dúvida | O que fazer |
|---|---|
| Hub fora do ar | Registrar horário, tirar screenshot do erro e avisar no grupo de WhatsApp |
| Login expirado ou não funciona | Tentar novamente. Se persistir, avisar o gestor de contratos |
| Filtro do Hub não funciona | Tirar screenshot, atualizar a página e tentar novamente. Se persistir, avisar no grupo |
| Link da loja quebrado ou sem produto | Tirar screenshot, registrar na observação e enviar o produto para revisão com motivo SITE |
| Site da loja pede CEP | Informar qualquer CEP válido (ex.: 01310-100) para prosseguir com a validação |
| Pop-up de cookie bloqueia a página | Fechar ou aceitar os cookies e continuar normalmente |
| Produto indisponível na loja | Se a página ainda mostrar nome, imagem e ingredientes, validar normalmente. Se não mostrar, enviar para revisão com motivo SITE |
| Página sem campo de ingredientes | Registrar na observação e enviar para revisão com motivo Padronizar Ingredientes |
| EAN não encontrado em nenhuma fonte | Registrar na observação que o EAN não foi localizado e enviar para revisão |
| Botão de copiar ingredientes não funciona | Selecionar e copiar o texto manualmente. Se não for possível, registrar na observação |
| IA retorna resposta vaga ou inconclusiva | Reenviar o prompt. Se persistir, usar outra ferramenta (ChatGPT → Claude ou vice-versa). Em caso de dúvida, enviar para revisão |

---

## 9. Tarefa 2 — Validação de Coleta de Rua (Sugestões de Usuário) {#sec-tarefa-2}

### 8.1. Descrição

Conferir e ajustar manualmente os ingredientes de produtos fotografados em farmácias por coletores de campo, lidos via OCR. Como o OCR pode falhar (especialmente em rótulos cilíndricos), a tarefa exige análise visual cuidadosa do rótulo e ajustes em ordem, nomenclatura e composição da lista de ingredientes.

**Perfil:** exige formação na área (química, farmácia, engenharia química, biomedicina, idealmente com experiência em cosméticos). O profissional precisa ter senso crítico para validar ingredientes.

**Organização:** por data de coleta (a partir de 06/04/2026). Cada worker recebe uma faixa de datas exclusiva.

### 8.2. Passo 1 — Acessar a lista de produtos

- Ir para **"Sugestões de usuário"** no Hub
- Filtrar marcas: manuais, sugeridas, todas
- Filtrar pela faixa de datas atribuída (a partir de 06/04)

> *[ESPAÇO PARA SCREENSHOT 1.1: aba "Sugestões de usuário" com filtros aplicados]*

### 8.3. Passo 2 — Selecionar e abrir o produto

- Abrir o produto a ser analisado
- Verificar no **dashboard de resumo** as informações iniciais
- Conferir nas **"Submissões"** se o mesmo produto foi fotografado mais de uma vez — se sim, escolher a foto de melhor qualidade para trabalhar

> *[ESPAÇO PARA SCREENSHOT 2.1: dashboard de resumo do produto]*

> *[ESPAÇO PARA SCREENSHOT 2.2: aba "Submissões" com múltiplas fotos do mesmo produto]*

### 8.4. Passo 3 — Análise da Composição (ingredientes)

Ir para a aba **"Composição"** e:

**a)** Identificar ingredientes "pouco confiáveis" — o sistema marca aqueles com confiabilidade abaixo de 95%.

**b)** Abrir a foto do rótulo clicando na imagem.

**c)** Para cada ingrediente pouco confiável:

- Comparar com o rótulo
- Se estiver **correto** → manter (não há opção de "marcar como confiável", apenas seguir adiante)
- Se estiver **errado** → excluir o ingrediente. O sistema sugere novos ingredientes do padrão INCI para adicionar

**d)** Verificar a ordem dos ingredientes:

- A ordem deve corresponder exatamente ao rótulo
- O ajuste atual é feito com setinhas (para cima/baixo) — para ingredientes muito fora de posição, o processo é lento

**e)** Em caso de dilema (imagem ilegível, dúvida não resolvível): enviar para revisão via "Criar e resolver no Hub" — o fluxo exato ainda será definido pela equipe BeClean.

> *[ESPAÇO PARA SCREENSHOT 3.1: aba "Composição" com ingredientes marcados como pouco confiáveis]*

> *[ESPAÇO PARA SCREENSHOT 3.2: foto do rótulo ampliada]*

> *[ESPAÇO PARA SCREENSHOT 3.3: ação de excluir e adicionar ingrediente]*

> *[ESPAÇO PARA SCREENSHOT 3.4: ajuste de ordem com as setinhas]*

### 8.5. Passo 4 — Salvar a curadoria

- Clicar em **"Salvar Curadoria"** para não perder o trabalho intermediário
- Quando tudo estiver correto, clicar em **"Criar e Resolver no Hub"** para finalizar

> *[ESPAÇO PARA SCREENSHOT 4.1: botão "Salvar Curadoria"]*

> *[ESPAÇO PARA SCREENSHOT 4.2: confirmação de "Criar e Resolver no Hub"]*

### 8.6. Passo 5 — Normalização

Próximo passo após a composição:

- Conferir se a **marca** está correta
- Conferir **categoria** e **subcategoria** (usando o mesmo quadro da Tarefa 1)
- Conferir a **nomenclatura do produto** comparando com a embalagem — corrigir erros ortográficos, capitalização, troca de letras
- O EAN **não precisa ser validado** nesta tarefa (já está no manual)
- Alterar diretamente no Hub quando necessário

> *[ESPAÇO PARA SCREENSHOT 5.1: tela de normalização com marca/categoria/subcategoria]*

> *[ESPAÇO PARA SCREENSHOT 5.2: correção de nomenclatura do produto]*

### 8.7. Passo 6 — Encerramento da jornada

- Salvar todos os screenshots na pasta do EAN no Drive (ver "Organização no Google Drive")
- Atualizar a planilha de controle com cada produto conferido
- Anotar na coluna "Observações" qualquer rótulo recorrentemente ilegível, problema do OCR ou padrão suspeito

---

## 9. Pendências do Hub que afetam a execução {#sec-pendencias}

Itens em aberto com a equipe técnica da BeClean que podem impactar o trabalho dos workers e ainda serão resolvidos:

- **Filtro de enriquecimento vs. scraping:** em validação, há produtos enriquecidos por bases externas aparecendo no filtro scraping (equipe BeClean está testando)
- **Zoom na imagem da composição:** não disponível na tela de ingredientes da Coleta de Rua — a ser implementado
- **Criação de motivos de revisão:** opção a ser desabilitada para o perfil worker
- **Fluxo de "Criar e Resolver no Hub":** destino exato a ser definido pela equipe BeClean para casos de dilema
- **Nome do revisor no Hub:** a ser incluído para rastreabilidade (equipe BeClean tratará internamente). Enquanto isso, relatórios podem ser extraídos via banco de dados
- **Ordem de ingredientes via drag-and-drop:** hoje só setinhas — melhoria sugerida
- **Destaque de pouco confiável em amarelo:** sugestão da BASE/labs para diferenciar visualmente de erros graves

---

## 10. Anexos a serem incluídos {#sec-anexos}

Materiais a serem anexados a este documento (ou compartilhados em separado na pasta do worker) antes do início dos trabalhos:

**Já incorporados a este documento (v1.3, a partir do PDF "Processo de Validação de Produtos" fornecido pelo ponto focal operacional da BeClean):**

- ✅ Lista dos 3 sites de conferência de EAN (ver 7.4.d)
- ✅ Prompt de IA para comparação das listas de ingredientes (ver 7.4.f)
- ✅ Regra de aprovação em lote — nota de corte de 50 produtos (ver 7.6)
- ✅ Passo a passo com prints — referência: arquivo PDF na pasta `workers_tasks/`

**Ainda pendentes:**

- **Quadro de categorias e subcategorias** — pendente ponto focal técnico da BeClean
- **Lista de marcas atribuídas** a cada worker — a definir no onboarding
- **Faixas de datas atribuídas** para a Coleta de Rua — a definir no onboarding
- **Template da planilha de controle** (Google Sheets) — a criar e versionar
- **Link de convite do grupo de WhatsApp** — a gerar no início do projeto
- **Detalhamento da Tarefa 2 (Coleta de Rua) pela BeClean** — o PDF atual cobre apenas a Tarefa 1 (Scraping)

---

## 11. Racional das estimativas de tempo {#sec-racional}

> **Nota:** Esta seção é interna do gestor de contratos — não está vinculada na navegação principal do manual. Serve para calibrar metas de produtividade no início do projeto. Os números aqui são **estimativas a priori**; a versão definitiva nasce depois das primeiras duas semanas de execução, quando a coluna "Tempo gasto (min)" da planilha de controle de cada worker passa a alimentar a base real.

### 11.1. Metodologia

A estimativa parte da decomposição de cada tarefa nos passos descritos nas seções 7 (Scraping) e 8 (Coleta de Rua). Para cada passo, atribuí uma faixa `[mínimo, máximo]` em segundos com base em duas referências:

- **Tempo de operação de UI** (clicar, esperar carregamento, ler toast): tipicamente 10–30 s
- **Tempo de leitura/decisão** (comparar nome, validar EAN, interpretar a conclusão da IA, comparar ingrediente com rótulo): tipicamente 15–180 s, dependendo do volume de texto e da carga cognitiva

A soma das faixas por passo dá a estimativa por produto. Variações de cenário (revisão, edição de categoria, rótulo difícil) entram como acréscimos sobre a base.

**Premissas que precisam ser validadas em campo:**

- **Tarefa 1 — mix de outcomes:** 70% aprovados direto, 20% precisam de ajuste de categoria, 10% vão para revisão
- **Tarefa 2 — esforço médio:** ~5 ingredientes pouco confiáveis a corrigir por produto; ordem dos ingredientes parcialmente fora de posição (ajuste com setinhas)
- **Eficiência da jornada:** worker dedica 85% do tempo bruto a tarefa (os 15% restantes cobrem micro-pausas, organização das pastas no Drive, atualização da planilha em lote, leitura de mensagens no grupo de WhatsApp)
- **Curva de aprendizagem:** zerada após onboarding — workers não atingem essa produtividade no primeiro dia
- **Jornada diária produtiva:** 6 horas (sobre 8 horas de janela), considerando intervalos e overhead administrativo

### 11.2. Tarefa 1 — decomposição por etapa

Tempo em segundos, base de um produto **aprovado direto** (sem editar categoria, sem ir para revisão). Etapas referenciam a seção 7.4 do manual.

| Etapa | Mínimo | Máximo |
|---|---:|---:|
| a) Abrir Link da Loja | 10 | 20 |
| b) Comparar nome Hub × site | 15 | 30 |
| c) Conferir imagem (padrão BeClean) | 10 | 20 |
| d) Validar EAN (Cosmos / Pesquisa de produto / GS1) | 30 | 60 |
| e) Conferir categoria/subcategoria | 10 | 30 |
| **f) Avaliação de ingredientes via IA** (3 copy/paste + prompt + leitura da conclusão) | **90** | **180** |
| g) Aprovar produto + aguardar toast | 10 | 20 |
| Screenshots ao longo do caminho | 60 | 120 |
| Linha na planilha de controle | 20 | 40 |
| **Total — produto aprovado direto** | **255 s (~4,2 min)** | **520 s (~8,7 min)** |

**Acréscimos por cenário:**

- **Editar categoria/subcategoria** (passo 7.4.e com correção): +30–60 s
- **Enviar para revisão** (passo 7.5: Observação + Motivo + Confirmar): +50–100 s

O passo (f) — comparação das três listas de ingredientes via IA — é o **gargalo dominante**. Qualquer ganho de produtividade na Tarefa 1 passa por reduzir esse tempo (atalhos de copy, prompt salvo no chat, IA local com latência menor, etc.).

### 11.3. Tarefa 2 — decomposição por etapa

Tempo em segundos, base de um produto **típico** (rótulo razoável, OCR razoável, ~5 ingredientes a corrigir). Etapas referenciam as seções 8.3 a 8.6 do manual.

| Etapa | Mínimo | Máximo |
|---|---:|---:|
| Abrir produto + dashboard + escolher melhor submissão | 30 | 60 |
| Identificar ingredientes <95% de confiança | 15 | 30 |
| Abrir/inspecionar foto do rótulo | 10 | 20 |
| **Corrigir ingredientes pouco confiáveis** (~5 × ~25 s) | **90** | **240** |
| **Ajustar ordem dos ingredientes** (setinhas — pendência conhecida) | **60** | **240** |
| Salvar Curadoria + Criar e Resolver no Hub | 20 | 40 |
| Normalização (marca, categoria, subcategoria, nome) | 60 | 120 |
| Screenshots ao longo do caminho | 60 | 120 |
| Linha na planilha de controle | 20 | 40 |
| **Total — produto típico** | **365 s (~6,1 min)** | **910 s (~15,2 min)** |

**Variações por dificuldade:**

- **Rótulo cilíndrico ou OCR muito ruim:** o tempo de correção de ingredientes pode dobrar — produto difícil chega a 15–20 min
- **Ordem completamente embaralhada:** o ajuste por setinhas é lento; pode somar +2–4 min sozinho
- **Caso de dilema** (rótulo ilegível, dúvida não resolvível): mais +1–2 min para abrir "Criar e Resolver no Hub" como revisão

### 11.4. Throughput por hora

Aplicando as faixas acima sobre uma jornada com **85% de tempo produtivo** (15% para micro-pausas, organização e overhead):

| Cenário | Produtos por hora |
|---|---:|
| **Tarefa 1 — base teórica** (aprovado direto) | 6,9 – 14,1 |
| **Tarefa 1 — efetivo a 85%** (aprovado direto) | 5,9 – 12,0 |
| **Tarefa 1 — mix realista** (70% ok / 20% editar cat / 10% revisão), efetivo | **5,6 – 11,5** |
| **Tarefa 2 — base teórica** (produto típico) | 4,0 – 9,9 |
| **Tarefa 2 — efetivo a 85%** (produto típico) | **3,4 – 8,4** |
| Tarefa 2 — rótulo fácil (OCR limpo) | 4,8 – 5,9 |
| Tarefa 2 — rótulo difícil (OCR ruim, ordem embaralhada) | 2,9 – 4,4 |

**Tarefa 1 com aprovação em lote (seção 7.6):**

Para lotes acima de 50 produtos a regra é amostrar 20% e aprovar o restante em lote. Isso muda o regime de produtividade radicalmente — o gargalo deixa de ser a conferência produto-a-produto e passa a ser o ciclo da amostra.

| Tamanho do lote | Amostra (20%) | Tempo total estimado | Throughput médio |
|---:|---:|---:|---:|
| 50 | 10 | ~72 min | ~41,5 produtos/h |
| 100 | 20 | ~140 min | ~43,0 produtos/h |
| 200 | 40 | ~274 min | ~43,7 produtos/h |

O throughput converge perto de **~43 produtos/h** porque o custo fixo da aprovação em lote (~5 min para selecionar todos, aprovar e aguardar o toast) se dilui em lotes maiores. Isso explica por que a regra de amostragem é tão importante: ela é o que faz a Tarefa 1 escalar.

### 11.5. Estimativa diária

Considerando **6 horas produtivas por dia** (jornada de 8h descontando pausas, deslocamento entre marcas/datas, troca de aba, leitura de mensagens):

| Cenário | Produtos por dia |
|---|---:|
| Tarefa 1 — mix realista, **sem aprovação em lote** (lotes ≤ 50) | **34 – 69** |
| Tarefa 1 — com aprovação em lote (lotes grandes dominam) | ~250 |
| Tarefa 2 — produto típico | **20 – 50** |

> **Nota:** Os números da Tarefa 1 com aprovação em lote dependem **fortemente** do tamanho médio dos lotes recebidos. Se o worker passa o dia em marcas com lotes de 10–40 produtos (abaixo da nota de corte), a produtividade fica na faixa inferior (34–69/dia). Se cai em marcas grandes (lotes 100+), pode chegar a 250+/dia trivialmente. A média real só sai depois de ver a distribuição de tamanhos de lote por marca.

### 11.6. Como recalibrar com dados reais

Depois de duas semanas de execução, a planilha de controle de cada worker terá dados suficientes para substituir as estimativas a priori desta seção. O caminho de calibração:

1. **Extrair a coluna "Tempo gasto (min)"** de todas as planilhas dos workers, segmentando por Tarefa
2. **Calcular percentis** (p25, p50, p75) por tarefa — a média é menos útil aqui porque produtos difíceis criam cauda longa
3. **Cruzar com a coluna "Resultado"** ("Aprovado" vs. "Enviado para revisão") para validar a premissa de mix (70/20/10 da Tarefa 1)
4. **Cruzar com a coluna "Marca / Faixa de datas"** para identificar marcas/faixas que pesam acima da média (sinal de problema estrutural — anotar em "Observações")
5. **Substituir as faixas desta seção** pelos percentis observados, e marcar a versão do documento (v1.6+) com a data da recalibração

A versão **v1.5** assume tudo isso a priori. As próximas versões devem trazer as faixas observadas e, idealmente, gráficos de distribuição por marca/faixa de coleta.
