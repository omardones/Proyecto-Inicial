from django.db import models


class Concepto(models.Model):
    CATEGORIAS = [
        ('fundamentos', 'Fundamentos'),
        ('ahorro', 'Ahorro e inversión'),
        ('deuda', 'Deudas y créditos'),
        ('macro', 'Macroeconomía'),
    ]

    nombre = models.CharField(max_length=100)
    categoria = models.CharField(max_length=20, choices=CATEGORIAS, default='fundamentos')
    definicion = models.TextField()
    prerrequisitos = models.ManyToManyField(
        'self', symmetrical=False, blank=True, related_name='desbloquea'
    )

    def __str__(self):
        return self.nombre