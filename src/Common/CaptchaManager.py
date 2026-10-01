"""Tudo que neste projeto se lê de uma imagem — a peça didática dele.

São dois usos do mesmo OCR, e o carrosnaweb serve os dois:

- a verificação humana, uma imagem de quatro caracteres com um formulário do
  lado, que interrompe a navegação;
- os valores da ficha (deslocamento, potência, peso, comprimento) que o site
  desenha em vez de escrever, justamente para não serem copiados.

As duas imagens são o caso mais simples que existe: traço escuro sobre fundo
claro, fonte única, sem ruído, sem distorção e sem sobreposição. É exatamente o
material que um OCR de prateleira lê, e é por isso que servem de exemplo de como
um scraper enxerga esse tipo de defesa.

O que segura coleta automática de verdade está no resto do projeto — ritmo de
requisição, sessão, referer coerente, proxy — não num desenho de quatro letras.
"""
import io
import string
import asyncio
import logging
from collections import Counter
from typing import Awaitable, Callable, Iterator

import pytesseract
from PIL import Image, ImageOps


class CaptchaManager:
    """Lê com Tesseract o que o site entrega como imagem: o captcha e os valores.

    Uma passada só de OCR erra com facilidade: o limiar que separa traço de fundo
    muda com a imagem, e o modo de segmentação do Tesseract muda o que ele entende
    por "linha de texto". Por isso a leitura aqui é sempre a mesma receita —
    preparar a imagem em várias versões, ler cada uma em vários modos, e ficar com
    o que se sustenta. O que muda entre os dois usos é quando parar: o captcha
    aparece uma vez por sessão e paga a votação inteira; o valor aparece várias
    vezes por ficha e para na primeira leitura que serve.
    """

    # Os valores da ficha são número, vírgula e ponto. Nada mais entra: sem a
    # whitelist o Tesseract responde com o acento e a pontuação que ele imagina.
    NUMBER_CHARSET = '0123456789.,'

    def __init__(self, length: int = 4,
                 charset: str = string.ascii_lowercase + string.digits,
                 attempts: int = 3, scale: int = 4, border: int = 3,
                 thresholds: tuple[int, ...] = (110, 140, 170),
                 page_modes: tuple[int, ...] = (8, 13, 7)):
        self.length = length
        self.charset = charset
        self.attempts = max(1, attempts)
        self.logger = logging.getLogger(type(self).__module__)
        self._scale = scale
        self._border = border
        self._thresholds = thresholds
        self._page_modes = page_modes
        # A sessão HTTP é uma só: uma verificação aceita vale para todos os workers.
        # O lock evita que os 30 batam no mesmo muro ao mesmo tempo, cada um gerando
        # um desafio novo para o site.
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ #
    # OCR                                                                  #
    # ------------------------------------------------------------------ #

    def solve(self, image_bytes: bytes) -> str | None:
        """Devolve a leitura mais provável da imagem, ou None quando nenhuma serve."""
        readings = self.readings(image_bytes)
        if not readings:
            self.logger.warning('solve - no plausible reading for the image')
            return None

        answer, votes = readings[0]
        total = sum(count for _, count in readings)
        self.logger.info(f'solve - read {answer!r} ({votes}/{total} votes)')
        return answer

    def readings(self, image_bytes: bytes) -> list[tuple[str, int]]:
        """Toda leitura plausível do captcha com seus votos, da mais votada à menos.

        É por onde se enxerga o OCR trabalhando: quando o primeiro palpite é
        recusado pelo site, a lista mostra o que mais o Tesseract considerou e o
        quanto as variantes concordaram entre si.
        """
        # O tamanho é o filtro que mais paga: quando o OCR parte um traço em dois,
        # sobra um caractere a mais e a leitura cai fora sozinha.
        votes = Counter(text for text in self._reads(image_bytes, self.charset, self._border)
                        if len(text) == self.length)
        return votes.most_common()

    def read_number(self, image_bytes: bytes) -> str | None:
        """Lê um valor que a ficha entrega desenhado em vez de escrito.

        Aqui não há votação: cada leitura é um processo do Tesseract, e a ficha traz
        um punhado desses valores — pagar nove leituras por campo travaria o laço do
        crawler, que é o mesmo para todos os workers. Então as variantes são um
        plano B, não um coro: a primeira que devolver algum dígito encerra a
        conta, e as outras só entram quando a imagem resiste.
        """
        for text in self._reads(image_bytes, self.NUMBER_CHARSET, border=0):
            if any(char.isdigit() for char in text):
                return text

        self.logger.warning('read_number - no digits found in the image')
        return None

    def _reads(self, image_bytes: bytes, charset: str, border: int) -> Iterator[str]:
        """Lê a imagem em toda combinação de variante e modo, sob demanda.

        Preguiçoso de propósito: quem quer votar consome tudo, quem quer só uma
        resposta para na primeira que serve e não paga pelo resto.
        """
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert('L')
        except Exception as error:
            self.logger.warning(f'_reads - image could not be opened: {error!r}')
            return

        for variant in self._variants(image, border):
            for page_mode in self._page_modes:
                yield self._clean(self._read(variant, page_mode, charset), charset)

    def _variants(self, image: Image.Image, border: int):
        """A imagem como veio e depois em preto e branco, em vários limiares.

        Antes do limiar: `border` pixels saem fora (a moldura do captcha vira um
        retângulo que o Tesseract tenta ler; a imagem de valor não tem moldura e
        entra com 0), o contraste é esticado e a imagem é ampliada — o Tesseract foi
        treinado em texto impresso, e 38px de altura é menos do que ele espera.

        A imagem crua vem primeiro porque preparar também custa: ampliar cria
        sombra na borda do traço, e o limiar pode promover essa sombra a um
        caractere que não existe. Quando ela já é legível, é ela que vale.
        """
        yield image

        width, height = image.size
        border = border if min(width, height) > 2 * border else 0
        image = image.crop((border, border, width - border, height - border))
        image = ImageOps.autocontrast(image)
        image = image.resize((image.width * self._scale, image.height * self._scale),
                             Image.LANCZOS)

        for threshold in self._thresholds:
            yield image.point(lambda pixel: 0 if pixel < threshold else 255, '1')

    def _read(self, image: Image.Image, page_mode: int, charset: str) -> str:
        """Uma passada do Tesseract, presa ao alfabeto esperado.

        A whitelist é o que impede o OCR de responder com pontuação e acento que o
        formulário nunca aceitaria; `--psm` diz a ele que a imagem é uma palavra
        solta (8), uma linha crua (13) ou uma linha de texto (7), e não uma página.
        """
        config = f'--oem 3 --psm {page_mode} -c tessedit_char_whitelist={charset}'
        try:
            return pytesseract.image_to_string(image, config=config)
        except Exception as error:
            self.logger.warning(f'_read - tesseract failed (psm {page_mode}): {error!r}')
            return ''

    def _clean(self, text: str, charset: str) -> str:
        """Tira do texto do OCR tudo que não pode estar na resposta."""
        # Só normaliza a caixa quando o alfabeto é de uma caixa só — senão seria o
        # próprio limpador jogando fora a distinção que o captcha pede.
        if not any(char.isupper() for char in charset):
            text = text.lower()
        elif not any(char.islower() for char in charset):
            text = text.upper()
        return ''.join(char for char in text if char in charset)

    # ------------------------------------------------------------------ #
    # Desafio                                                              #
    # ------------------------------------------------------------------ #

    async def solve_challenge(self, fetch_image: Callable[[], Awaitable[bytes | None]],
                              submit: Callable[[str], Awaitable[bool]]) -> bool:
        """Lê o captcha e manda a resposta, até `attempts` vezes. Diz se passou.

        As duas pontas do site entram por quem chama: `fetch_image` baixa a imagem
        da vez e `submit` envia a resposta e responde se ela foi aceita. Assim o
        manager não sabe nada de URL, cabeçalho ou campo de formulário — o que muda
        de site para site fica no `RequestFactory`, e isto aqui continua servindo
        para qualquer um deles.

        Cada tentativa baixa uma imagem nova: a resposta errada queima o desafio e o
        site gera outro, então repetir a leitura da imagem antiga não levaria a nada.
        """
        async with self._lock:
            for attempt in range(1, self.attempts + 1):
                image = await fetch_image()
                answer = self.solve(image) if image else None

                if not answer:
                    self.logger.warning(
                        f'solve_challenge - nothing readable ({attempt}/{self.attempts})')
                    continue

                if await submit(answer):
                    self.logger.info(
                        f'solve_challenge - {answer!r} accepted ({attempt}/{self.attempts})')
                    return True

                self.logger.warning(
                    f'solve_challenge - {answer!r} refused ({attempt}/{self.attempts})')

            return False
