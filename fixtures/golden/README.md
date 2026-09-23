# fixtures/golden

Golden dataset: cada carpeta es un caso con documentos **ficticios** y el resultado esperado.
`tests/golden/test_golden.py` los ejecuta todos y falla si algo que funcionaba deja de funcionar.
Carpeta compartida: se añade o cambia un caso solo de acuerdo entre Pedro y Oliver.

Estructura de un caso:

```
fixtures/golden/<nn>_<nombre>/
  albaran.json      albarán ya interpretado (modelo Albaran) — o —
  documento.pdf     documento a leer (entonces esperado.json lleva "lectura")
  pedido.json       pedido de Siddex (modelo Pedido); ausente = albarán sin pedido
  reglas.json       (opcional) ReglasCotejo
  esperado.json     { "lectura": {...campos...}, "cotejo": {...campos...} }
```

En `esperado.json` solo se ponen los campos que se quieren fijar; el resto no se compara.
Para el cotejo se comparan: `semaforo`, `relacion`, `entrega`, `precio`, `total_albaran`,
`lineas[].semaforo`, `lineas[].entrega`, y `avisos` como lista de tipos por línea.
