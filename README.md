# Rank Clip Studio

Editor web em português para criar vídeos com a imagem base aprovada. Arranca com **`python main.py`** em **`0.0.0.0:80`** (não 8080).

## Hospedagem Python

1. Instalar dependências: `pip install -r requirements.txt`.
2. Definir o inicializador como `main.py`.
3. Definir a porta como `80` e iniciar com `python main.py`.
4. Abrir o endereço HTTPS fornecido pela hospedagem.

Não é necessário Node, base de dados ou chave de API. O navegador faz a composição; o servidor converte a gravação em MP4 H.264/AAC. A dependência `imageio-ffmpeg` fornece um executável FFmpeg quando o sistema não o tem. Se o servidor não tiver FFmpeg, a interface informa e oferece o formato nativo do navegador. As conversões são temporárias e os ficheiros são apagados no fim da resposta.

Alternativa Docker: `docker build -t rank-video .` e `docker run --rm -p 80:80 rank-video`.

## Utilização

- Configurar as cinco cenas iniciais; adicionar, duplicar ou remover cenas (1–12).
- Os pontos finais, ganhos, limites e duração são independentes por cena.
- Carregar PNGs transparentes dos ícones reais dos ranks e escolher os ícones de cada cena. Não estão incluídos ícones oficiais nem são descarregados automaticamente.
- Ajustar as posições no painel de coordenadas se usares outro template.
- Escolher formato vertical (720×1280 / 1080×1920) ou original (1080×720 / 1620×1080). O modo vertical conserva a imagem completa, com fundo preto (como no exemplo) ou desfocado.
- Carregar música opcional e, para um final idêntico ao jogo, uma gravação própria da subida a Mestres/Pro (usam-se no máximo 15 segundos). As celebrações incorporadas são recriações, não animações oficiais.
- Pré-visualizar, exportar uma imagem PNG ou gerar o vídeo. Manter o separador visível durante a gravação; mudar de separador cancela-a para evitar vídeos incompletos.
- Guardar o projeto em JSON: inclui cenas, posições, ícones, template personalizado e fonte personalizada. Música e vídeo final devem ser selecionados novamente quando abres o projeto.

Os Brawlers continuam os do template, conforme combinado. A troca de Brawlers/skins fica para a próxima etapa. A fidelidade depende da imagem, dos ícones e da fonte carregados; não há garantia de identidade pixel a pixel com o jogo.

## Ficheiros

- `main.py`: servidor HTTP e conversão MP4.
- `static/index.html`, `style.css`, `app.js`: editor e gravação Canvas/MediaRecorder.
- `static/template.png`: imagem base aprovada.
- `static/game.ttf`: Lilita One, distribuída sob SIL Open Font License (`static/FONT-LICENSE.txt`); podes carregar outra fonte.
- `requirements.txt`: FFmpeg portátil para exportar MP4.
- `Dockerfile`: arranque em Python com porta 80.

O site não inclui login. Não há API de Brawl Stars, autenticação GitHub ou tokens guardados na aplicação. Usa os ficheiros de imagem, áudio e vídeo que tenhas autorização para usar.

## Estado desta versão

Versão inicial pronta para instalar. Verificações feitas: sintaxe Python/JavaScript, navegador Chromium em desktop e telemóvel, sequência de cinco cenas, exportação MP4 H.264, alterações de formato, cancelamento e gravação/reabertura do projeto. O teste de áudio e gravação final é incluído em `tests/browser.cjs`.

Para repetir os testes de navegador, instala Playwright no ambiente de desenvolvimento e executa `TEST_PORT=18080 node tests/browser.cjs` com FFmpeg/ffprobe disponíveis. Podes indicar `CHROME_PATH` para um navegador local. Esta porta é apenas do teste; a aplicação continua a usar 80 por defeito. A hospedagem tem de permitir bind na porta 80.

Não foi feita publicação na hospedagem. Não foram fornecidos ícones oficiais nem uma gravação própria da subida de rank; estes podem ser carregados no editor.
