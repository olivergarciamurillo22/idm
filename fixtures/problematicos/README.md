# fixtures/problematicos

Casos que representan una situación real que **todavía no sabemos resolver** porque falta una regla de IDM.
Cada caso tiene la misma estructura que un golden (`documento.*` o `albaran.json`, `pedido.json`, `esperado.json`)
más un `PENDIENTE.md` que dice exactamente qué decisión falta y de quién. Los tests están marcados `xfail` y pasan a
`fixtures/golden/` cuando IDM decide. La lista completa está en `docs/PENDIENTE-IDM.md`.
