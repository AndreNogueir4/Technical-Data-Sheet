import re
from lxml import html


class CarrosWebParser:
    def __init__(self):
        self._words_remove = {
            'página principal', 'comparativo', 'avaliação', 'notícias',
            'opinião do dono', 'concessionárias', 'ranking',
            'carros mais vendidos', 'todos', 'hatchback', 'sedã', 'perua',
            'minivan', 'cupê', 'conversível', 'suv', 'picape', 'van',
            'furgão', 'jipe', 'chassi-cabine', 'mapa do site', 'sobre o site',
            'privacidade', 'termos de uso', 'mobile', 'fale conosco',
            'comunicar erro', 'próximos lançamentos', 'comparativos', 'versão clássica',
        }
        self._section_headers = {
            'MOTOR', 'TRANSMISSÃO', 'TRANSMISSAO', 'SUSPENSÃO', 'SUSPENSAO',
            'FREIOS', 'DIREÇÃO', 'DIRECAO', 'PNEUS', 'DIMENSÕES', 'DIMENSOES',
            'DESEMPENHO', 'CONSUMO', 'AUTONOMIA',
        }

    # ------------------------------------------------------------------ #
    # Catalog parsers                                                       #
    # ------------------------------------------------------------------ #

    def is_error_page(self, content: str) -> bool:
        tree = html.fromstring(content)
        return any('Ocorreu um erro.' in text for text in tree.xpath('//text()'))

    def automakers(self, content: str) -> list[str]:
        tree = html.fromstring(content)
        automakers = tree.xpath('//a/font/text()')
        return [m.strip().lower() for m in automakers if m.strip() and m.strip().lower() not in self._words_remove]

    def models(self, content: str) -> list[str]:
        tree = html.fromstring(content)
        models = tree.xpath('//a/font/text()')
        return [m.strip().lower() for m in models if m.strip() and m.strip().lower() not in self._words_remove]

    def years(self, content: str) -> list[str]:
        tree = html.fromstring(content)
        years = tree.xpath('//a/font/text()')
        return [y.strip().lower() for y in years if y.strip() and y.strip().lower() not in self._words_remove]

    def versions_code(self, content: str) -> dict:
        tree = html.fromstring(content)
        links = tree.xpath('//font/a')
        versions = {}
        for link in links:
            href = link.get('href', '')
            text = link.text_content().strip()
            text = re.sub(r'\s+', ' ', text).strip()
            if href and text and href.startswith('fichadetalhe.asp?codigo'):
                versions[text] = href
        return versions

    # ------------------------------------------------------------------ #
    # Technical sheet parser                                               #
    # ------------------------------------------------------------------ #

    def technical_sheet(self, content: str) -> dict:
        tree = html.fromstring(content)
        result = {
            'nome': self._extract_name(tree),
            **self._extract_specs(tree),
            'equipamentos': self._extract_equipment(tree),
            'fotos': self._extract_photos(tree),
        }
        return result

    def _clean_text(self, text: str) -> str:
        return re.sub(r'[\xa0\s]+', ' ', text).strip()

    def _extract_name(self, tree) -> str:
        fonts = tree.xpath('//font[@color="darkred" and @size="4"]')
        for font in fonts:
            text = self._clean_text(font.text_content())
            if text and text.upper() not in self._section_headers and \
                    text not in ('Ficha Técnica', 'Equipamentos', 'Fotos'):
                return text
        return ''

    def _extract_specs(self, tree) -> dict:
        # Collect (section, label, value, row_context) 4-tuples in document order.
        # row_context = first pair's label when a row contains two pairs — used to
        # disambiguate labels that repeat within the same section (e.g. "Elemento
        # elástico" appears twice in SUSPENSÃO, once for dianteiro and once for traseiro).
        Quad = tuple  # (section: str, label: str, value, context: str | None)
        quads: list[Quad] = []
        current_section = 'Geral'

        specs_table = tree.xpath(
            '//table[@border="0" and @cellspacing="1" and @cellpadding="3" and @width="100%"]'
        )
        if not specs_table:
            return {}

        for row in specs_table[0].xpath('.//tr'):
            cells = list(row.xpath('./td'))
            if not cells:
                continue

            # Section header: centred td with a darkred size-4 font
            header_fonts = row.xpath(
                './/td[@align="center"]//font[@color="darkred" and @size="4"]'
            )
            if header_fonts:
                section_text = self._clean_text(header_fonts[0].text_content())
                if section_text and section_text.upper() in self._section_headers:
                    current_section = section_text.upper()
                continue

            # Collect valid label-value pairs from this row (preserving left→right order)
            row_pairs: list[tuple[str, object]] = []
            i = 0
            while i < len(cells):
                label_td = cells[i]
                if label_td.get('align') != 'right' or label_td.get('bgcolor') != '#ffffff':
                    i += 1
                    continue
                label_fonts = label_td.xpath('.//font[@color="darkred" and @size="3"]')
                if not label_fonts:
                    i += 1
                    continue
                label = self._clean_text(label_fonts[0].text_content())
                if not label or i + 1 >= len(cells):
                    i += 1
                    continue
                value_td = cells[i + 1]
                if value_td.get('bgcolor') != '#efefef':
                    i += 1
                    continue
                value = self._parse_cell_value(value_td)
                if value is not None:
                    row_pairs.append((label, value))
                i += 2

            # When a row has two pairs, the second pair uses the first pair's
            # label as row_context to resolve within-section duplicates.
            for idx, (label, value) in enumerate(row_pairs):
                context = row_pairs[0][0] if idx == 1 and len(row_pairs) == 2 else None
                quads.append((current_section, label, value, context))

        # ---- Duplicate resolution ----
        from collections import Counter
        label_counts = Counter(label for _, label, _, _ in quads)
        section_label_counts = Counter((s, label) for s, label, _, _ in quads)

        specs: dict = {}
        counter: Counter = Counter()
        for section, label, value, context in quads:
            if label_counts[label] == 1:
                # Unique across entire page
                key = label
            elif section_label_counts[(section, label)] == 1:
                # Unique within section, but duplicated across sections → prefix section
                key = f'{section} - {label}'
            else:
                # Duplicated within the same section → use row_context when available
                if context:
                    key = f'{label} ({context})'
                else:
                    counter[(section, label)] += 1
                    n = counter[(section, label)]
                    key = f'{section} - {label}' if n == 1 else f'{section} - {label} ({n})'
            specs[key] = value

        # "Nota do leitor" value is not in a standard #efefef cell
        nota = self._extract_reader_rating(tree)
        if nota:
            specs['Nota do leitor'] = nota

        return specs

    def _parse_cell_value(self, td) -> str | dict | None:
        # Values rendered as images to prevent scraping (e.g. deslocamento, peso, comprimento)
        ocr_imgs = td.xpath('.//img[contains(@src, "campoImagem") or contains(@src, "imgValor")]')
        if ocr_imgs:
            raw_src = ocr_imgs[0].get('src', '')
            # Normalise: '..\campoImagem\imgValor1.asp' → 'campoImagem/imgValor1.asp'
            img_path = raw_src.replace('\\', '/').lstrip('./').lstrip('.')
            img_path = re.sub(r'^/+', '', img_path)
            # The text after the img element is the unit (e.g. "cm³", "kg", "mm")
            tail = self._clean_text(ocr_imgs[0].tail or '')
            return {'__ocr__': img_path, '__unit__': tail}

        text = self._clean_text(td.text_content())
        return text if text else None

    def _extract_reader_rating(self, tree) -> str | None:
        # The rating is an <img src="*estrelas*"> followed by tail text like "\xa08,5"
        imgs = tree.xpath('//img[contains(@src, "estrelas")]')
        if not imgs:
            return None
        tail = re.sub(r'[\xa0\s]+', '', imgs[0].tail or '').strip()
        return tail or None

    # ------------------------------------------------------------------ #
    # Equipment section                                                    #
    # ------------------------------------------------------------------ #

    def _extract_equipment(self, tree) -> dict:
        equipment: dict[str, list] = {}
        current_category = 'Geral'

        # The equipment list is rendered inside a nested <table width="92%">
        equip_tables = tree.xpath('//table[@width="92%"]')
        if not equip_tables:
            return equipment

        equip_table = equip_tables[0]

        def process_cells(cells: list) -> None:
            nonlocal current_category
            if not cells:
                return
            first = cells[0]
            # Category header: single cell with colspan=4 containing a darkred font
            if first.get('colspan') in ('4', '3') and first.xpath('.//font[@color="darkred"]'):
                cat_text = self._clean_text(first.text_content())
                if cat_text:
                    current_category = cat_text
                    equipment.setdefault(current_category, [])
                return
            # Equipment item pairs: (img_cell, name_cell)
            equipment.setdefault(current_category, [])
            i = 0
            while i + 1 < len(cells):
                img_cell, name_cell = cells[i], cells[i + 1]
                imgs = img_cell.xpath('.//img')
                if imgs:
                    img_src = (imgs[0].get('src') or '').lower()
                    name = self._clean_text(name_cell.text_content())
                    if name and ('verde.gif' in img_src or 'amar.gif' in img_src):
                        equip_type = 'serie' if 'verde.gif' in img_src else 'opcional'
                        equipment[current_category].append({'nome': name, 'tipo': equip_type})
                i += 2

        # Malformed HTML causes some <td> elements to be direct children of the <table>
        # rather than inside a <tr>. We iterate all children and batch orphaned <td>s.
        orphaned: list = []
        for child in equip_table:
            if child.tag == 'tr':
                if orphaned:
                    process_cells(orphaned)
                    orphaned = []
                process_cells(list(child.xpath('./td')))
            elif child.tag == 'td':
                orphaned.append(child)

        if orphaned:
            process_cells(orphaned)

        return {k: v for k, v in equipment.items() if v}

    # ------------------------------------------------------------------ #
    # Photos                                                               #
    # ------------------------------------------------------------------ #

    def _extract_photos(self, tree) -> list[str]:
        hrefs = tree.xpath('//a[@rel="example_group"]/@href')
        seen: set[str] = set()
        result: list[str] = []
        for href in hrefs:
            normalized = href.replace('\\', '/')
            if normalized not in seen:
                seen.add(normalized)
                result.append(normalized)
        return result
