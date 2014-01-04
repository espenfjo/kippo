# TODO copyrights

import smtplib
from email.mime.text import MIMEText

from time import localtime, strftime
from kippo.core.config import config

    #def __init__(self):
    
#@staticmethod
def attempt_success(src, user, time, execcmd):
    # send mail
    formatted_time = strftime("%a, %d %b %Y %H:%M:%S", localtime())
    body = "Successful attempt from %s on %s (user %s)\n" % (src, formatted_time, user)

    if execcmd != None:
        body = body + 'Non-interactive command(s) run: "%s"' % execcmd

    msg = MIMEText(body)
    msg['From'] = "%s <%s>" % (config().get('mailer', 'from'), config().get('mailer', 'envelope_from'))
    msg['Subject'] = "[Kippo] Successful login attempt by %s" % (src)

    smtp = smtplib.SMTP(config().get('mailer', 'smtp_server'))
    smtp.sendmail(config().get('mailer', 'envelope_from'), config().get('mailer', 'envelope_to'), msg.as_string())

