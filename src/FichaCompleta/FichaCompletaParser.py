import re
from lxml import html
from unidecode import unidecode


class FichaCompletaParser:
    _WORDS_REMOVE = {'Quem Somos', 'Contato', 'Política de Privacidade', 'Ver mais', 'Marcas'}

    def is_captcha(self, content: str) -> bool:
        tree = html.fromstring(content)
        return any('Digite o código:' in t for t in tree.xpath('//text()'))

    # ------------------------------------------------------------------ #
    # Catalog parsers                                                      #
    # ------------------------------------------------------------------ #

    def automakers(self, content: str) -> list[str]:
        tree = html.fromstring(content)
        items = tree.xpath('//span/text()')
        return [
            unidecode(m.lower().strip().replace(' ', '-'))
            for m in items
            if m.strip() and m.strip() not in self._WORDS_REMOVE
        ]

    def models(self, content: str) -> list[str]:
        tree = html.fromstring(content)
        items = tree.xpath('//span/text()')
        return [
            unidecode(m.lower().strip().replace(' ', '-'))
            for m in items
            if m.strip() and m.strip() not in self._WORDS_REMOVE
        ]

    def version_years(self, content: str) -> tuple[dict, list[str]]:
        tree = html.fromstring(content)
        versions: dict[str, str] = {}
        years: list[str] = []

        for element in tree.xpath('//div/a[normalize-space(text())]'):
            text = element.text.strip()
            href = element.get('href', '').strip()
            if not href or any(w in text for w in self._WORDS_REMOVE):
                continue
            versions[text] = href
            m = re.match(r'^\d{4}', text)
            if m and m.group(0) not in ('Carregando', 'Carregando...'):
                years.append(m.group(0))

        return versions, years

    # ------------------------------------------------------------------ #
    # Technical sheet parser                                               #
    # ------------------------------------------------------------------ #

    def technical_sheet(self, content: str) -> dict:
        tree = html.fromstring(content)
        keys = tree.xpath('//div[1]/b/text()')
        values = [v.strip() for v in tree.xpath('//div[2]/text()') if v.strip()]
        specs = dict(zip(keys, values))
        equipments = [e.strip() for e in tree.xpath('//li/span/text()') if e.strip()]
        specs['equipamentos'] = equipments or ['Equipment not listed for this model']
        return specs
