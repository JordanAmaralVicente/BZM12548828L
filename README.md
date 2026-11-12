# Preços PS5 & GTA VI

O projeto acompanha o preço do **PS5** (com disco, Digital e Pro), do **GTA VI** (Edição Padrão e Ultimate) e dos **combos PS5 + GTA VI**. Os preços são coletados 2× ao dia e publicados num site com gráficos e um sinal de **COMPRA / NEUTRO / AGUARDE**. Também pode mandar um alerta por e-mail.

| Fonte | Como coleta | Situação |
|---|---|---|
| Kabum | API pública do catálogo | ✅ |
| Amazon | página de busca (Chromium headless) | ✅ |
| Carrefour | página de busca (Chromium headless) | ✅ |
| PlayStation Store | busca (preço digital do GTA VI) | ✅ |
| Mercado Livre | página de busca | ⚠️ pede verificação de conta para robôs |
| Casas Bahia | página de busca | ⚠️ bloqueia robôs (HTTP 403) |

Quando uma loja bloqueia, o crawler registra "bloqueada" e segue com as outras; ele não tenta burlar captcha nem verificação.

## Como funciona

```
crawler/stores.py    coletores de cada loja → anúncios crus {título, preço, link}
crawler/classify.py  decide a qual produto o anúncio pertence (descarta acessórios, usados, importados, Xbox…)
crawler/signals.py   calcula o sinal a partir do histórico do menor preço
crawler/notify.py    alerta por e-mail quando vira COMPRA ou bate novo mínimo
crawler/main.py      orquestra: coleta → data/*.csv → site/data.json → alertas
site/                site estático (Chart.js) publicado no GitHub Pages
data/prices.csv      histórico (menor preço por loja e produto em cada coleta)
data/runs.csv        status de cada loja em cada coleta
```

### Regras do sinal

O sinal usa o menor preço entre todas as lojas em cada coleta:

- **COMPRA**: o menor preço já registrado, ou até 3% acima do mínimo histórico, ou 8%+ abaixo da média de 30 dias.
- **AGUARDE**: 3%+ acima da média de 30 dias, ou preço caindo nos últimos dias, ou Black Friday a menos de 15 dias.
- **NEUTRO**: preço dentro do normal.
- **COLETANDO**: menos de 3 dias de histórico.

Os limites estão no topo de `crawler/signals.py`.

## Colocando no ar (GitHub)

1. Crie um repositório **público** no GitHub. O Pages é grátis para repositórios públicos. Depois envie o projeto:
   ```bash
   git init -b main && git add . && git commit -m "Rastreador de preços"
   git remote add origin https://github.com/SEU_USUARIO/precos-ps5.git
   git push -u origin main
   ```
2. Em **Settings → Pages**, em *Source*, escolha **GitHub Actions**.
3. Em **Settings → Actions → General → Workflow permissions**, marque **Read and write permissions**.
4. Em **Actions → Coleta de preços → Run workflow**, rode a primeira coleta. O site fica em `https://SEU_USUARIO.github.io/precos-ps5/`.

Depois disso a coleta roda sozinha às 09:00 e às 21:00 (horário de Brasília). O GitHub às vezes atrasa execuções agendadas em alguns minutos.

### Alertas por e-mail (Gmail)

O alerta sai de uma conta Gmail e pode ir para ela mesma. Todos os alertas de uma coleta chegam juntos num único e-mail.

1. A conta Gmail que vai enviar precisa ter a **verificação em duas etapas** ativada.
2. Em https://myaccount.google.com/apppasswords, crie uma **senha de app** (o nome pode ser "precos-ps5") e copie os 16 caracteres.
3. No GitHub, em **Settings → Secrets and variables → Actions → New repository secret**, crie:
   - `EMAIL_USER`: o endereço Gmail que envia
   - `EMAIL_APP_PASSWORD`: a senha de app do passo 2 (não é a sua senha normal)
   - `EMAIL_TO`: quem recebe; se ficar vazio, vai para o próprio `EMAIL_USER`

Os endereços ficam como segredos e não aparecem no código, que é público. Sem esses segredos, o crawler só imprime no log os alertas que mandaria.

## Rodando localmente

```bash
pip install -r requirements.txt && python -m playwright install chromium
python -m crawler.main                    # coleta tudo
python -m crawler.main --stores kabum     # só uma loja
python -m crawler.main --build            # só regera o site a partir do CSV
python -m unittest discover -s tests -t . # testes do classificador e do sinal
cd site && python -m http.server 8000     # abre http://localhost:8000
```
