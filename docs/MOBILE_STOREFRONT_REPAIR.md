# Reparación responsive del website Bader

Operación de configuración, no una migración ni un hook de instalación.
`scripts/repair_mobile_storefront.py` transforma texto SCSS de forma pura y
conserva cada byte del contenido anterior. La versión instalada del addon no
cambia por aplicar una personalización del editor nativo del website.

## Problemas reproducidos

En 360 px, el scroll real de Odoo (`#wrapwrap`) alcanzaba 582 px en Inicio:
títulos guardados con tamaños fijos dentro de elementos `span/font/strong`.
Contacto y Be-Learning también desbordaban. La barra nativa de catálogo tenía
`flex-nowrap`, obligando al botón de filtros a salir de pantalla.

## Corrección limitada

- El marcador de búsqueda BPI delimita el website autorizado.
- Títulos H1 de páginas de contenido no comercial: tamaño fluido hasta 767.98 px,
  con herencia en los elementos de formato y ajuste de palabras largas.
- Barra nativa del catálogo: controles reorganizados hasta 575.98 px; búsqueda,
  tarifas y filtros permanecen disponibles.
- No recortar ni ocultar el overflow del documento o de `#wrapwrap`.
- No modificar HTML guardado, fuentes oficiales, nombres de producto, imágenes,
  precios, formularios, enlaces, SEO, carrusel o reglas de variantes.
- Desktop y website sin marcador BPI conservan sus estilos anteriores.

El helper exige una configuración tipográfica previamente revisada y rechaza
marcadores duplicados o modificados. Repetir la misma operación no añade reglas.

## Validación y aplicación

```sh
python3 -m unittest discover -s scripts -p 'test_repair_mobile_storefront.py' -v
```

Primero probar el CSS congelado en navegador, incluyendo scroll de `#wrapwrap`,
menú cerrado/abierto, búsqueda, filtros, títulos y footer en 320/360/390/414 px,
los límites 575/576/767/768 y desktop. Un `scrollWidth` correcto en `html` no
es suficiente para certificar Odoo. Probar páginas públicas existentes; no
enviar formularios, modificar carrito ni ejecutar IA en una prueba de lectura.

Antes de escribir: confirmar entorno, empresa/website, flags, propiedad de la
personalización, usuario administrador y hash anterior bajo bloqueo de fila.
Crear backup externo verificable del banco y todos sus archivos referenciados,
filestore base/delta, medios privados, addon/config afectados y SCSS exacto.
Guardar únicamente el dato binario del attachment SCSS del website, invalidar
assets con los mecanismos nativos y verificar nuevamente la entrega real.
No copiar esta herramienta como código runtime ni ejecutar `-u all`.

Rollback: restaurar solamente el SCSS anterior si su hash actual coincide con
el resultado aplicado. Rechazar ediciones concurrentes. Nunca restaurar el banco
completo de una tienda activa por una corrección CSS. Los certificados de runtime
y las rutas de backup pertenecen al registro privado de cada operación; este
documento no certifica que QAS o PROD haya recibido la personalización.
