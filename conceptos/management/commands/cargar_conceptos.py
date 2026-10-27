from django.core.management.base import BaseCommand

from conceptos.datos import CONCEPTOS
from conceptos.models import Concepto


class Command(BaseCommand):
    help = 'Carga los conceptos y sus prerrequisitos (se puede ejecutar varias veces).'

    def handle(self, *args, **options):
        por_slug = {}

        # Pasada 1: crear o actualizar cada concepto
        for slug, nombre, categoria, definicion, ejemplo, pre in CONCEPTOS:
            obj, _ = Concepto.objects.update_or_create(
                nombre=nombre,
                defaults={'categoria': categoria, 'definicion': definicion},
            )
            por_slug[slug] = obj

        # Pasada 2: conectar los prerrequisitos (ya existen todos)
        lineas = 0
        for slug, nombre, categoria, definicion, ejemplo, pre in CONCEPTOS:
            por_slug[slug].prerrequisitos.set([por_slug[p] for p in pre])
            lineas += len(pre)

        self.stdout.write(self.style.SUCCESS(
            f'{len(CONCEPTOS)} conceptos y {lineas} prerrequisitos cargados.'))
