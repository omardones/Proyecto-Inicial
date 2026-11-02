from django.db import models

# Create your models here.
class Fuente(models.Model):
    nombre = models.CharField(max_length=200) # Ej: Superintendencia de Pensiones
    emisor = models.CharField(max_length=200)
    descripcion = models.TextField()
    enlace = models.URLField()

    def __str__(self):
        return self.nombre

class Concepto(models.Model):
    titulo = models.CharField(max_length=200) # Ej: AFP, APV, Sueldo Bruto
    categoria = models.CharField(max_length=100) # Ej: Básico, Avanzado
    definicion = models.TextField()
    ejemplo = models.TextField()
    prerequisitos = models.ManyToManyField('self', blank=True, symmetrical=False, related_name='conceptos_posteriores')
    fuentes = models.ManyToManyField(Fuente, blank=True)

    def __str__(self):
        return self.titulo