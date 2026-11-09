class ExternalAPIError(Exception):
    """Falló una consulta a un servicio externo (red, respuesta inválida, etc.).

    El resto del proyecto solo necesita atrapar esta excepción para mostrar un
    mensaje al usuario, sin conocer los detalles de la librería `requests`.
    """
