"""Safe Nancy transport diagnostics: never persist response bodies or secrets."""
import re

from odoo import _
from odoo.exceptions import UserError


MESSAGES = {
    'authentication': 'Nancy AI requiere revisar la credencial de acceso con un administrador.',
    'permission': 'La cuenta no tiene permiso para esta operación de Nancy AI.',
    'unavailable': 'La capacidad configurada de Nancy AI no está disponible para esta cuenta.',
    'quota': 'Nancy AI alcanzó el límite de uso o saldo de la cuenta. Un administrador debe revisar la facturación antes de reintentar.',
    'rate_limit': 'Nancy AI recibió demasiadas solicitudes. Espera antes de volver a intentarlo.',
    'configuration': 'La solicitud de Nancy AI fue rechazada por su configuración. Comunica la referencia al administrador.',
    'service': 'El servicio de Nancy AI no está disponible temporalmente.',
    'timeout': 'Nancy AI no respondió dentro del tiempo previsto. La solicitud puede haberse procesado; revisa antes de reintentar.',
    'connection': 'No se pudo conectar con Nancy AI. Revisa la conexión del servidor.',
    'invalid_response': 'Nancy AI devolvió una respuesta que no se pudo interpretar. La previa anterior se conserva.',
    'incomplete': 'Nancy AI no terminó la respuesta. La propuesta incompleta no sustituye tu previa.',
    'refusal': 'Nancy AI no pudo generar contenido con esta solicitud. Revisa las instrucciones y las fuentes.',
}


class StudioRequestError(UserError):
    def __init__(self, category, phase, status=None, request_id=None):
        category = category if category in MESSAGES else 'invalid_response'
        self.studio_diagnostic = {'category': category, 'phase': phase,
                                  'reference': 'NANCY_' + category.upper()}
        if isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599:
            self.studio_diagnostic['httpStatus'] = status
        if isinstance(request_id, str) and re.fullmatch(r'req_[a-zA-Z0-9_-]{1,128}', request_id):
            self.studio_diagnostic['requestId'] = request_id
        super().__init__('%s %s [%s]' % (_(MESSAGES[category]),
                         _('No se repitió automáticamente; tus borradores siguen intactos.'),
                         self.studio_diagnostic['reference']))


def http_failure(response):
    status = response.status_code
    category = {401: 'authentication', 403: 'permission', 404: 'unavailable',
                429: 'rate_limit'}.get(status, 'service' if status >= 500 else 'configuration')
    # Read only a known code for categorization, never retain the external text.
    if status == 429:
        try:
            data = response.json()
            error = data.get('error') if isinstance(data, dict) else None
            code = error.get('code') if isinstance(error, dict) else None
            if code in ('insufficient_quota', 'credit_balance_exhausted', 'billing_hard_limit_reached', 'usage_limit_reached') or (
                    isinstance(error, dict) and error.get('type') == 'insufficient_quota'):
                category = 'quota'
        except (ValueError, TypeError):
            pass
    return StudioRequestError(category, 'http', status, response.headers.get('x-request-id'))
