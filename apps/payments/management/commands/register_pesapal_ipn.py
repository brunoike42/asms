"""
Usage:
    python manage.py register_pesapal_ipn --domain https://yourdomain.com

Registers your IPN URL with PesaPal and prints the ipn_id to add to settings.py.
Only needs to be run once per deployment (sandbox and live separately).
"""
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = 'Register the ASMS IPN URL with PesaPal and output the ipn_id for settings.py'

    def add_arguments(self, parser):
        parser.add_argument(
            '--domain',
            type=str,
            required=True,
            help='Your public domain, e.g. https://stamarys.asms.app',
        )
        parser.add_argument(
            '--list',
            action='store_true',
            default=False,
            help='List already registered IPN URLs instead of registering a new one',
        )

    def handle(self, *args, **options):
        from apps.payments.pesapal import PesaPalClient, PesaPalError

        client  = PesaPalClient()
        sandbox = getattr(settings, 'PESAPAL_SANDBOX', True)
        env     = 'SANDBOX' if sandbox else 'LIVE'

        self.stdout.write(f'\nPesaPal IPN Registration — {env} environment')
        self.stdout.write(f'Consumer Key: {settings.PESAPAL_CONSUMER_KEY[:8]}...')
        self.stdout.write('-' * 50)

        if options['list']:
            try:
                ipns = client.get_registered_ipns()
                self.stdout.write(f'\nRegistered IPN URLs ({len(ipns)}):')
                for ipn in ipns:
                    self.stdout.write(
                        f"  ipn_id: {ipn.get('ipn_id')}\n"
                        f"  url:    {ipn.get('url')}\n"
                        f"  type:   {ipn.get('ipn_notification_type')}\n"
                    )
            except PesaPalError as e:
                raise CommandError(f'Failed to list IPNs: {e}')
            return

        domain  = options['domain'].rstrip('/')
        ipn_url = f'{domain}/payments/ipn/'

        self.stdout.write(f'\nRegistering IPN URL: {ipn_url}')

        try:
            result = client.register_ipn(ipn_url, notification_type='GET')
        except PesaPalError as e:
            raise CommandError(f'PesaPal IPN registration failed: {e}')

        ipn_id = result.get('ipn_id', '')

        self.stdout.write(self.style.SUCCESS(f'\n✓ IPN registered successfully!\n'))
        self.stdout.write(f'  IPN ID:  {ipn_id}')
        self.stdout.write(f'  URL:     {result.get("url")}')
        self.stdout.write(f'  Status:  {result.get("status")}')

        self.stdout.write(self.style.WARNING(
            f'\n▶ Add this to your settings.py / .env:\n'
            f'  PESAPAL_IPN_ID = "{ipn_id}"\n'
        ))
        self.stdout.write(
            f'  (Use a separate IPN ID for sandbox and live — register both.)\n'
        )
