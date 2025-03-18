import csv

primera_columna = set()
segunda_columna = set()


ruta_archivo = '/home/oleon/Descargas/Hoja de cálculo sin título - Hoja 1.csv'

with open(ruta_archivo, 'r') as archivo:
    lector = csv.reader(archivo)
    for fila in lector:

        if len(fila) > 0 and fila[0].strip():
            primera_columna.add(fila[0].strip())

        if len(fila) > 1 and fila[1].strip():
            segunda_columna.add(fila[1].strip())


valores_faltantes = primera_columna - segunda_columna

print("Valores en la primera columna que no están en la segunda:")
for valor in sorted(valores_faltantes):
    print(valor)