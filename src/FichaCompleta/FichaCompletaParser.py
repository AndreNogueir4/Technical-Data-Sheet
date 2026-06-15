from lxml import html
from unidecode import unidecode


class FichaCompletaParser:
    _WORDS_REMOVE = {'Quem Somos', 'Contato', 'Política de Privacidade', 'Ver mais', 'Marcas'}

    def is_captcha(self, content: str) -> bool:
        tree = html.fromstring(content)
        return any('Digite o código:' in t for t in tree.xpath('//text()'))

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

        for card in tree.xpath("//div[@class='ver-card']"):
            hrefs = card.xpath(".//a[@class='ver-card__link']/@href")
            year_texts = card.xpath(".//span[@class='ver-card__year']/text()")
            name_texts = card.xpath(".//span[@class='ver-card__name']/text()")
            fuel_texts = card.xpath(".//span[@class='ver-card__fuel']/text()")

            if not hrefs or not year_texts:
                continue

            href = hrefs[0].strip()
            year = year_texts[0].strip()
            name = name_texts[0].strip() if name_texts else ''
            fuel = fuel_texts[0].strip() if fuel_texts else ''

            version = ' '.join(filter(None, [name, fuel]))
            text = f"{year} {version}".strip()

            if any(w in text for w in self._WORDS_REMOVE):
                continue

            versions[text] = href
            years.append(year)

        return versions, years

    def technical_sheet(self, content: str) -> dict:
        tree = html.fromstring(content)
        specs = {}

        for item in tree.xpath("//div[contains(@class, 'ent-spec-item')]"):
            label = item.xpath(".//span[@class='ent-spec-label']/text()")
            value_parts = item.xpath(".//span[@class='ent-spec-value']//text()")
            if not label or not value_parts:
                continue
            key = label[0].strip()
            val = ' '.join(v.strip() for v in value_parts if v.strip())
            if key and val:
                specs[key] = val

        equipments = [e.strip() for e in tree.xpath('//li/span/text()') if e.strip()]
        specs['equipamentos'] = equipments or ['Equipment not listed for this model']
        return specs
