import argparse

def parse_args():
    parser = argparse.ArgumentParser(
        description='CLI para rodar scrapers de veículos'
    )

    subparsers = parser.add_subparsers(
        dest='command', required=True, help='Escolha o comando para executar'
    )

    site_parser = subparsers.add_parser(
        'site', help='Rodar scraper de um site específico'
    )
    site_parser.add_argument(
        'site',
        choices=['carronaweb', 'fichacompleta'],
        help='Nome do site para rodar'
    )
    site_parser.add_argument(
        '--phase',
        type=int,
        choices=[1, 2, 3],
        default=3,
        help='Fase do processo: 1 = dados iniciais, 2= ficha técnica, 3 = tudo (default)'
    )


    full_parser = subparsers.add_parser(
        'full', help='Rodar todos os scrapers'
    )
    full_parser.add_argument(
        '--phase',
        type=int,
        choices=[1, 2, 3],
        default=3,
        help='Fase do processo: 1 = dados iniciais, 2 = ficha técnica, 3 = tudo (default)'
    )

    """Subcomando para usar no futuro para limpar registros antigos"""
    maintenance_parser = subparsers.add_parser(
        'maintenance', help='Comandos de manutenção (DB, cache, etc.)'
    )
    maintenance_parser.add_argument(
        '--clean-db',
        action='store_true',
        help='Limpar registros antigos do banco de dados'
    )
    maintenance_parser.add_argument(
        '--show-stats',
        action='store_true',
        help='Mostrar estatísticas do scraping'
    )

    return parser.parse_args()