"""
PesaPal API v3 Client for ASMS.

Endpoints used:
  POST /api/Auth/RequestToken         — get bearer token
  POST /api/URLSetup/RegisterIPN      — register IPN callback URL
  POST /api/Transactions/SubmitOrderRequest — create payment order
  GET  /api/Transactions/GetTransactionStatus?orderTrackingId=... — verify payment

Sandbox:  https://cybqa.pesapal.com/pesapalv3
Live:     https://pay.pesapal.com/v3

Docs: https://developer.pesapal.com/how-to-integrate/e-commerce/api-30-json
"""
import logging
import requests
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

SANDBOX_BASE = 'https://cybqa.pesapal.com/pesapalv3/api'
LIVE_BASE    = 'https://pay.pesapal.com/v3/api'

# PesaPal payment status codes
STATUS_INVALID   = 0
STATUS_COMPLETED = 1
STATUS_FAILED    = 2
STATUS_REVERSED  = 3

STATUS_LABELS = {
    STATUS_INVALID:   'Invalid',
    STATUS_COMPLETED: 'Completed',
    STATUS_FAILED:    'Failed',
    STATUS_REVERSED:  'Reversed',
}


class PesaPalError(Exception):
    """Raised when PesaPal returns an error response."""
    pass


class PesaPalClient:
    """
    Thin wrapper around the PesaPal v3 REST API.
    Instantiate once per request or reuse across a request cycle.
    Token is cached in Django's cache backend (Redis recommended).
    """

    TOKEN_CACHE_KEY = 'pesapal_auth_token'
    TOKEN_CACHE_BUFFER_SECS = 60  # Refresh token 60 s before it actually expires

    def __init__(self):
        self.consumer_key    = getattr(settings, 'PESAPAL_CONSUMER_KEY', '')
        self.consumer_secret = getattr(settings, 'PESAPAL_CONSUMER_SECRET', '')
        self.sandbox         = getattr(settings, 'PESAPAL_SANDBOX', True)
        self.ipn_id          = getattr(settings, 'PESAPAL_IPN_ID', '')
        self.base_url        = SANDBOX_BASE if self.sandbox else LIVE_BASE
        self._token          = None

    # ─────────────────────────────────────────────
    #  Authentication
    # ─────────────────────────────────────────────

    def get_token(self) -> str:
        """Return a valid bearer token, using the cache to avoid repeated auth calls."""
        cached = cache.get(self.TOKEN_CACHE_KEY)
        if cached:
            return cached

        url = f'{self.base_url}/Auth/RequestToken'
        payload = {
            'consumer_key':    self.consumer_key,
            'consumer_secret': self.consumer_secret,
        }
        try:
            resp = requests.post(url, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error(f'PesaPal auth failed: {e}')
            raise PesaPalError(f'Authentication failed: {e}')

        if data.get('status') != '200' or not data.get('token'):
            raise PesaPalError(f'Auth error: {data.get("error", data)}')

        token = data['token']

        # Calculate TTL from expiryDate returned by PesaPal
        try:
            expiry = datetime.fromisoformat(data['expiryDate'].replace('Z', '+00:00'))
            from django.utils import timezone as tz
            now = tz.now()
            ttl = int((expiry - now).total_seconds()) - self.TOKEN_CACHE_BUFFER_SECS
            ttl = max(ttl, 30)  # at least 30 seconds
        except Exception:
            ttl = 270  # fallback: 4.5 minutes

        cache.set(self.TOKEN_CACHE_KEY, token, timeout=ttl)
        logger.debug(f'PesaPal token refreshed, valid for {ttl}s')
        return token

    def _headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self.get_token()}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    # ─────────────────────────────────────────────
    #  IPN Registration
    # ─────────────────────────────────────────────

    def register_ipn(self, ipn_url: str, notification_type: str = 'GET') -> dict:
        """
        Register your IPN callback URL with PesaPal.
        Returns the ipn_id you must store in settings.PESAPAL_IPN_ID.
        Only needs to be done once per deployment.
        """
        url = f'{self.base_url}/URLSetup/RegisterIPN'
        payload = {
            'url': ipn_url,
            'ipn_notification_type': notification_type,
        }
        try:
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise PesaPalError(f'IPN registration failed: {e}')

        if data.get('status') != '200':
            raise PesaPalError(f'IPN registration error: {data}')

        logger.info(f'PesaPal IPN registered: {data}')
        return data

    def get_registered_ipns(self) -> list:
        """List all registered IPN URLs for this account."""
        url = f'{self.base_url}/URLSetup/GetIpnList'
        try:
            resp = requests.get(url, headers=self._headers(), timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            raise PesaPalError(f'Failed to list IPNs: {e}')

    # ─────────────────────────────────────────────
    #  Order Submission (STK Push / Redirect)
    # ─────────────────────────────────────────────

    def submit_order(
        self,
        merchant_reference: str,
        amount: float,
        currency: str,
        description: str,
        callback_url: str,
        billing_first_name: str,
        billing_last_name: str,
        billing_email: str = '',
        billing_phone: str = '',
        billing_country: str = 'UG',
        branch: str = '',
    ) -> dict:
        """
        Submit a payment order to PesaPal.

        Returns dict with:
          - order_tracking_id  (PesaPal's reference — store this)
          - redirect_url       (send the parent to this URL)
          - merchant_reference (echoed back)

        The parent visits redirect_url, chooses MTN/Airtel/Card,
        and for mobile money receives a USSD STK push on their phone.
        """
        if not self.ipn_id:
            raise PesaPalError(
                'PESAPAL_IPN_ID is not configured in settings. '
                'Run: python manage.py register_pesapal_ipn'
            )

        url = f'{self.base_url}/Transactions/SubmitOrderRequest'
        payload = {
            'id':               merchant_reference,
            'currency':         currency,
            'amount':           float(amount),
            'description':      description[:100],  # PesaPal max 100 chars
            'callback_url':     callback_url,
            'redirect_mode':    '',  # empty = default redirect
            'notification_id':  self.ipn_id,
            'branch':           branch[:50] if branch else '',
            'billing_address':  {
                'email_address': billing_email or '',
                'phone_number':  billing_phone or '',
                'country_code':  billing_country,
                'first_name':    billing_first_name,
                'middle_name':   '',
                'last_name':     billing_last_name,
                'line_1':        '',
                'line_2':        '',
                'city':          '',
                'state':         '',
                'postal_code':   '',
                'zip_code':      '',
            },
        }

        logger.info(f'Submitting PesaPal order: ref={merchant_reference} amount={amount} {currency}')
        try:
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error(f'PesaPal order submission failed: {e}')
            raise PesaPalError(f'Order submission failed: {e}')

        if data.get('error') or data.get('status') not in ('200', 200):
            logger.error(f'PesaPal order error: {data}')
            raise PesaPalError(f'Order error: {data.get("error", data)}')

        logger.info(
            f'PesaPal order created: tracking_id={data.get("order_tracking_id")} '
            f'redirect={data.get("redirect_url", "")[:60]}'
        )
        return data

    # ─────────────────────────────────────────────
    #  Transaction Status
    # ─────────────────────────────────────────────

    def get_transaction_status(self, order_tracking_id: str) -> dict:
        """
        Query the status of a payment by PesaPal order tracking ID.

        status_code values:
          0 = INVALID   1 = COMPLETED   2 = FAILED   3 = REVERSED
        """
        url = f'{self.base_url}/Transactions/GetTransactionStatus'
        params = {'orderTrackingId': order_tracking_id}
        try:
            resp = requests.get(url, params=params, headers=self._headers(), timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error(f'PesaPal status check failed for {order_tracking_id}: {e}')
            raise PesaPalError(f'Status check failed: {e}')

        logger.info(
            f'PesaPal status for {order_tracking_id}: '
            f'{data.get("payment_status_description")} '
            f'(code {data.get("status_code")})'
        )
        return data

    def is_payment_complete(self, order_tracking_id: str) -> bool:
        """Convenience helper — returns True only if payment_status_code == 1 (COMPLETED)."""
        try:
            status = self.get_transaction_status(order_tracking_id)
            return int(status.get('status_code', 0)) == STATUS_COMPLETED
        except PesaPalError:
            return False
