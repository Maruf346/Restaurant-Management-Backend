"""
apps/users/email.py
────────────────────
Email helpers for user management workflows.

send_restaurant_admin_invite — sends a branded HTML invitation email to a
newly created Restaurant Admin, including their temporary password and the
list of restaurants they've been assigned to.
"""

import logging
import os
from email.mime.image import MIMEImage

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

# Absolute path to the logo used in the email header (embedded as CID)
_LOGO_PATH = os.path.join(settings.BASE_DIR, 'core', 'logo.png')


def send_restaurant_admin_invite(user, password: str, restaurant_names: list[str]) -> bool:
    """
    Send a branded HTML invitation email to a newly created Restaurant Admin.

    Args:
        user:              The newly created User instance.
        password:          The plain-text temporary password (only available at creation time).
        restaurant_names:  List of restaurant name strings the user has been assigned to.

    Returns:
        True if the email was sent successfully, False otherwise.
    """
    subject = "You've been invited to ProfitPlate"
    from_email = settings.DEFAULT_FROM_EMAIL
    to_email = [user.email]

    context = {
        'full_name': user.full_name or user.email,
        'email': user.email,
        'password': password,
        'restaurant_names': restaurant_names,
    }

    html_body = render_to_string('users/invite_restaurant_admin.html', context)
    text_body = strip_tags(html_body)

    msg = EmailMultiAlternatives(subject, text_body, from_email, to_email)
    msg.attach_alternative(html_body, 'text/html')

    # Embed the logo as an inline CID attachment (works in all major email clients)
    try:
        with open(_LOGO_PATH, 'rb') as logo_file:
            logo_data = logo_file.read()
        logo_mime = MIMEImage(logo_data)
        logo_mime.add_header('Content-ID', '<logo>')
        logo_mime.add_header('Content-Disposition', 'inline', filename='logo.png')
        msg.attach(logo_mime)
    except FileNotFoundError:
        logger.warning('ProfitPlate logo not found at %s — email will be sent without logo.', _LOGO_PATH)

    try:
        msg.send()
        logger.info('Invitation email sent to %s', user.email)
        return True
    except Exception as exc:
        logger.error('Failed to send invitation email to %s: %s', user.email, exc)
        return False
