"""Capa de lectura documental: un documento entra, un proveedor (Tesseract local, Azure Document Intelligence, Mistral
Document AI…) lo analiza y devuelve un ResultadoDocumental común; normalizacion.py lo convierte en DocumentoLeido.
El dominio no importa nada de aquí ni sabe qué motor leyó el documento. Carpeta de Oliver."""
