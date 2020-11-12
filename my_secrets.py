# IMPORTANT!!! Rename this file to secrets.py

""" Excert from:
 https://learn.adafruit.com/electronic-history-of-the-day-with-pyportal/code-walkthrough-secrets-py

Once you have logged into your account, there are two pieces of information you'll need to place
in your secrets.py file: Adafruit IO username, and Adafruit IO key. Head to io.adafruit.com and 
simply click the View AIO Key link on the left hand side of the Adafruit IO page to get this information.
"""

secrets = {
    'ssid'      : 'wifi wssid',
    'password'  : 'wifi password',
    'latitude'  : 40.0000,
    'longitude' : -74.0000,
    'timezone'  : 'America/New_York',
    'aio_key' : "your AIO key",
    'aio_username' : "your AIO username",
    'aio_feed' : 'appts'
}