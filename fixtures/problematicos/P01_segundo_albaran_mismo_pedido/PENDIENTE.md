# P01 · Segundo albarán del mismo pedido antes de que Siddex refleje el primero

**Situación.** Pedido de 5 rodamientos. Llega un albarán con 2 (entrega parcial, aprobado). Al día siguiente llega otro
con 3. El export de pedidos de Siddex sigue diciendo `recibida = 0` porque Fernando aún no ha metido la primera entrada
(o el export no se ha vuelto a sacar). Hoy el programa coteja el segundo albarán contra 5 pendientes → PARCIAL con 2
pendientes, cuando en realidad el pedido queda COMPLETO.

**Qué necesitamos de IDM.** Decidir cuál es la fuente de "cantidad recibida":
1. Siddex (export refrescado antes de cada pasada): lo más fiel, pero depende de que Fernando haya grabado la entrada.
2. Nuestra base de datos (albaranes aprobados del mismo pedido): inmediato, pero puede descontar dos veces cuando Siddex
   se ponga al día.
3. Las dos: descontar lo aprobado en nuestra base de datos solo si es posterior al export de Siddex.

**Esperado provisional (`esperado.json`).** Opción 3: entrega COMPLETA y VERDE. El test está `xfail` hasta decidirlo.
