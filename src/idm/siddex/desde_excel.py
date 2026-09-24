"""SiddexDesdeExcel: implementación de SiddexGateway sobre los exports a Excel de las pantallas de Siddex.
Las columnas se localizan por cabecera según siddex/columnas.py (+ alias en datos/siddex/columnas.json); cada fichero
deja un InformeColumnas. Lee articulos, proveedores, fabricantes, pedidos, stock y escandallos. No escribe nada."""

from decimal import Decimal
from pathlib import Path

from idm.dominio.dinero import CERO, a_decimal
from idm.dominio.estados import RelacionPedido
from idm.dominio.modelos import Articulo, Equivalencia, LineaPedido, Pedido, Proveedor
from idm.equivalencias.proveedores import clave_para
from idm.siddex.columnas import FICHEROS, ColumnasFaltantes, InformeColumnas, cargar_alias_extra, leer_tabla
from idm.siddex.lectura import Escandallo, leer_escandallo, normalizar_codigo


class SiddexDesdeExcel:
    def __init__(self, carpeta: Path, estricto: bool = False) -> None:
        """estricto=True: si faltan columnas requeridas lanza ColumnasFaltantes en vez de devolver vacío."""
        self.carpeta = Path(carpeta)
        self.estricto = estricto
        self.alias_extra = cargar_alias_extra(self.carpeta)
        self.informes: dict[str, InformeColumnas] = {}
        self.avisos: list[str] = []
        self._escandallos: dict[str, Escandallo] | None = None
        self._cache_pedidos: tuple[float, dict[str, Pedido]] | None = None

    def _ruta(self, nombre: str) -> Path | None:
        ruta = self.carpeta / FICHEROS[nombre]
        return ruta if ruta.exists() else None

    def _tabla(self, nombre: str) -> list[dict[str, object]]:
        """Filas de un export o [] si no existe. Nunca pierde columnas en silencio: el informe lo dice."""
        ruta = self._ruta(nombre)
        if ruta is None:
            self.avisos.append(f"Falta el export {FICHEROS[nombre]} en {self.carpeta}")
            return []
        try:
            filas, informe = leer_tabla(ruta, nombre, self.alias_extra)
        except ColumnasFaltantes as exc:
            self.informes[nombre] = exc.informe
            self.avisos.append(str(exc))
            if self.estricto:
                raise
            return []
        self.informes[nombre] = informe
        for campo in informe.faltantes_opcionales:
            self.avisos.append(f"{FICHEROS[nombre]}: sin columna '{campo}', se usa el valor por defecto")
        if informe.desconocidas:
            self.avisos.append(f"{FICHEROS[nombre]}: columnas sin uso: {', '.join(informe.desconocidas)}")
        return filas

    def informe_texto(self) -> str:
        partes = [inf.texto() for inf in self.informes.values()]
        if self.avisos:
            partes.append("Avisos:\n  - " + "\n  - ".join(dict.fromkeys(self.avisos)))
        return "\n".join(partes)

    def proveedores(self) -> list[Proveedor]:
        resultado = []
        for f in self._tabla("proveedores"):
            codigo = str(f["codigo"]).strip() if f["codigo"] is not None else None
            nombre = str(f["nombre"] or "").strip()
            resultado.append(
                Proveedor(
                    clave=clave_para(codigo, nombre),
                    codigo_siddex=codigo,
                    nombre=nombre,
                    cif=str(f["cif"]).strip() if f["cif"] else None,
                    email=str(f["email"]).strip() if f["email"] else None,
                )
            )
        return resultado

    def _clave_proveedor(self, valor) -> str | None:
        if valor in (None, ""):
            return None
        return clave_para(str(valor).strip(), "")

    def articulos(self) -> dict[str, Articulo]:
        resultado = {}
        for f in self._tabla("articulos"):
            if f["codigo"] in (None, ""):
                continue
            codigo = normalizar_codigo(str(f["codigo"]))
            resultado[codigo] = Articulo(
                codigo=codigo,
                descripcion=str(f["descripcion"] or "").strip(),
                unidad=str(f["unidad"] or "UD").strip(),
                proveedor_habitual=self._clave_proveedor(f["proveedor"]),
                precio_compra=a_decimal(f["precio"]) if f["precio"] not in (None, "") else None,
                descuento_pct=a_decimal(f["descuento"]) or CERO,
                multiplo_compra=a_decimal(f["multiplo"]) or Decimal("1"),
                tipo=str(f["tipo"]).strip() if f["tipo"] else None,
            )
        return resultado

    def equivalencias(self) -> list[Equivalencia]:
        resultado = []
        for f in self._tabla("fabricantes"):
            if f["codigo"] in (None, "") or f["codigo_proveedor"] in (None, ""):
                continue
            proveedor = self._clave_proveedor(f["proveedor"])
            if proveedor is None:
                continue
            resultado.append(
                Equivalencia(
                    proveedor=proveedor,
                    codigo_proveedor=str(f["codigo_proveedor"]).strip(),
                    codigo_idm=normalizar_codigo(str(f["codigo"])),
                    descripcion_proveedor=str(f["descripcion"] or "").strip(),
                )
            )
        return resultado

    def _pedidos(self) -> dict[str, Pedido]:
        ruta = self._ruta("pedidos")
        marca = ruta.stat().st_mtime if ruta else -1.0
        if self._cache_pedidos is not None and self._cache_pedidos[0] == marca:
            return self._cache_pedidos[1]
        pedidos: dict[str, Pedido] = {}
        for f in self._tabla("pedidos"):
            if f["numero"] in (None, "") or f["codigo"] in (None, ""):
                continue
            numero = str(f["numero"]).strip()
            if numero.endswith(".0"):
                numero = numero[:-2]
            if numero not in pedidos:
                fecha = f["fecha"]
                pedidos[numero] = Pedido(
                    numero=numero,
                    proveedor=self._clave_proveedor(f["proveedor"]) or "",
                    fecha=fecha.date() if hasattr(fecha, "date") else None,
                    numero_siddex=numero,
                    relacion=RelacionPedido.CON_PEDIDO,
                )
            pedidos[numero].lineas.append(
                LineaPedido(
                    codigo_idm=normalizar_codigo(str(f["codigo"])),
                    descripcion=str(f["descripcion"] or "").strip(),
                    cantidad=a_decimal(f["cantidad"]) or CERO,
                    unidad=str(f["unidad"] or "UD").strip(),
                    precio_bruto=a_decimal(f["precio"]) or CERO,
                    descuento_pct=a_decimal(f["descuento"]) or CERO,
                    cantidad_recibida=a_decimal(f["recibida"]) or CERO,
                    codigo_proveedor=str(f["codigo_proveedor"]).strip() if f["codigo_proveedor"] else None,
                )
            )
        self._cache_pedidos = (marca, pedidos)
        return pedidos

    def pedidos_abiertos(self, proveedor: str | None = None) -> list[Pedido]:
        return [
            p
            for p in self._pedidos().values()
            if (proveedor is None or p.proveedor == proveedor) and any(li.pendiente > CERO for li in p.lineas)
        ]

    def pedido(self, numero: str) -> Pedido | None:
        return self._pedidos().get(str(numero).strip())

    def stock(self) -> dict[str, Decimal]:
        return {
            normalizar_codigo(str(f["codigo"])): a_decimal(f["stock"]) or CERO
            for f in self._tabla("stock")
            if f["codigo"] not in (None, "")
        }

    def pendiente_recibir(self) -> dict[str, Decimal]:
        pendiente: dict[str, Decimal] = {}
        for p in self._pedidos().values():
            for li in p.lineas:
                if li.pendiente > CERO:
                    pendiente[li.codigo_idm] = pendiente.get(li.codigo_idm, CERO) + li.pendiente
        return pendiente

    def escandallo(self, codigo_maquina: str) -> Escandallo | None:
        if self._escandallos is None:
            self._escandallos = {}
            for ruta in sorted(self.carpeta.glob("*.xls")):
                try:
                    e = leer_escandallo(ruta)
                except Exception as exc:  # noqa: BLE001 - un .xls raro no debe tumbar el resto, pero se dice
                    self.avisos.append(f"Escandallo {ruta.name}: no se puede leer ({type(exc).__name__}: {exc})")
                    continue
                if e.codigo_maquina:
                    self._escandallos[e.codigo_maquina] = e
                else:
                    self.avisos.append(f"Escandallo {ruta.name}: sin cabecera ' Articulo: <código>' en la columna 1")
        return self._escandallos.get(normalizar_codigo(codigo_maquina))
