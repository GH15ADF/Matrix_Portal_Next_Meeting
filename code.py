"""
Display your next meeting's information on a Matrix Portal
"""
# local imports
import simdata
from constants import time_display_colors

# libraries
from adafruit_matrixportal.matrixportal import MatrixPortal
from adafruit_matrixportal.network import Network
import board
import json
import time
import gc

# Display imports
import adafruit_display_text.label
import terminalio
from adafruit_io.adafruit_io import AdafruitIO_RequestError
import neopixel

# Some critical but private settings are in the secrets.py file
try:
    from secrets import secrets
except ImportError:
    print('WiFi secrets are kept in secrets.py, please add them there!')
    raise

# --- Configuration Settings ---
# repoll time in seconds
POLL_SECS = 60
# time resync every hour to limit clock drift
TIME_RESYNC = 60 

# How many characters in the appointment subject before needing to scroll the text
SUBJECT_SCROLL_LIMIT = 10

# set the scroll text delay. More than 0.4 looks jerkie to me
SCROLL_DELAY = 0.04

# Display debug messages --------
DEBUG = True
MATRIX_DEBUG = True
# -------------------------------

# fetch info --------------------
_HEADER = {'X-AIO-Key': secrets['aio_key']}
_PATH = ['value']
_RECENT_DATA_URL = 'https://io.adafruit.com/api/v2/' + \
    secrets['aio_username'] + '/feeds/appts/data/last'
# --------------------------------

# --- Simulation data ---
"""
Use these setting to simulate AIO responses locally debug the display look and feel
"""
sim = simdata.sim()
USE_SIM_DATA = False
# -------------------------------


def my_local_time(pad=0) -> str:
    """Returns the local time as a string formatted HH:MM:SS
    :param int pad: the number of spaced characters to prepend to the string to position on the RGB LED display. Default is 0 
    """
    # now that we connected to the network to get the time,
    # we can display the local time
    curr_time_struct = time.localtime()
    curr_time_str = '{sp}{lhrs:0>2}:{lmin:0>2}:{lsec:0>2}'.format(
                sp=' '  * pad,
                lhrs=curr_time_struct.tm_hour,
                lmin=curr_time_struct.tm_min,
                lsec=curr_time_struct.tm_sec)
    return curr_time_str


def compute_status(resp_status: str, meeting_status: str) -> str:
    """Compute the status row values for icon and message.
    :param str resp_status: the reponse status value for the appointment
    :param str meeting_status: the meeting status for the meeting
    Returns the status line icon, text and text color as a dict
    """
    # if the meeting status is canceled, ignore the response status
    if meeting_status.lower().find('canceled') > -1:
        return('Canceled')
    else:
        return(resp_status)


def get_count_down(start: str, resp_status: str) -> tuple(str, int):
    """ Calcuates the count down value and the color. Returns the count down string and the RGB color
        :param int start: unix epoch start time for the appointment
        :param str resp_status: Text to display as the response status
    """
    # handle the no meeting scenario
    if resp_status == 'No meeting':
        cd_status = time_display_colors['No meeting']['color']
        status_string = 'No meetings'
    else:
        # calculate the start_time string to return
        # figure out if the start time is AM or PM
        start_hour = time.localtime(start).tm_hour
        suffix = 'p' if int(start_hour / 12) > 0 else 'a'

        start_time = '{lhrs:0>2}:{lmin:0>2}{sfx}'.format(
            lhrs=start_hour % 12 or 12, lmin=time.localtime(start).tm_min, sfx=suffix)

        # https://stackoverflow.com/questions/14904814/nameerror-global-name-long-is-not-defined
        # get the number of seconds for the countdown
        count_down_val = int(int(start)-time.mktime(time.localtime()))

        # calcuate the count down string
        # https://stackoverflow.com/questions/775049/how-do-i-convert-seconds-to-hours-minutes-and-seconds
        xmins, secs = divmod(count_down_val, 60)
        hrs, mins = divmod(count_down_val/60, 60)
        count_down_str = '{lmin:0>2}:{lsec:0>2}'.format(
            lmin=int(mins), lsec=int(secs))

        # set the status_string to the majority default
        status_string = '{st}  {cd}'.format(st=start_time, cd=count_down_str)

        if (count_down_val <= time_display_colors['in progress']['trigger']):
            cd_status = time_display_colors['in progress']['color']
            status_string = 'In progress'
        elif count_down_val <= time_display_colors['alert']['trigger']:
            cd_status = time_display_colors['alert']['color']
        elif (count_down_val <= time_display_colors['warning']['trigger']):
            cd_status = time_display_colors['warning']['color']
        elif (count_down_val <= time_display_colors['normal']['trigger']):
            cd_status = time_display_colors['normal']['color']
        elif (count_down_val > time_display_colors['normal']['trigger'] and count_down_val <= time_display_colors['gt 1day']['trigger']):
            cd_status = time_display_colors['gt 1hr']['color']
            status_string = '{st}  >1 hr'.format(st=start_time)
        elif (count_down_val > time_display_colors['gt 1day']['trigger']):
            cd_status = time_display_colors['gt 1day']['color']
            status_string = '> 1 day away'

        if DEBUG:
            print(f'{my_local_time()} start: {int(start)} local time: {time.mktime(time.localtime())} count_down_val: {count_down_val}')

    return status_string, cd_status


# icon bitmap
# https://icon-library.net/icon/icon-pixels-6.html
# in GIMP export to BMP after chaning Image mode to Indexed and Generate Optimum pallet
# choose advanced options and "16 bits R5 G5 B5"
'''
Response Status	    Description
-----------------------------------------------------------------
Accepted	        Sombody elses meeting you have accepted
Canceled            Sombody elses meeting but is now canceled
None        	    Your meeting but no attendees
Not Responded	    Sombody elses meeting and you have not responded
Organizer   	    Your meeting with attendees
Tentative    	    Sombody elses meeting you  accepted as tentative
'''
status_msg = {
                    'Accepted': {'icon': 'images/check.bmp',         'color': 0x2f7727, 'text': 'Accepted'},
                    'Canceled': {'icon': 'images/X.bmp',             'color': 0xFF4b2c, 'text': 'Canceled'},
                    'None': {'icon': 'images/NR.bmp',            'color': 0x444444, 'text': ''},
                    'Not Responded': {'icon': 'images/no-resp.bmp',       'color': 0x888888, 'text': 'Not Resp'},
                    'Organizer': {'icon': 'images/exclaimation.bmp',  'color': 0xFCFC3F, 'text': 'Organizer'},
                    'Tentative': {'icon': 'images/question_mark.bmp',      'color': 0x273077, 'text': 'Tentative'},
                    'No meeting': {'icon': '',                         'color': 0x000000, 'text': ''}
                }

# --- Display setup ---
matrixportal = MatrixPortal(
    bit_depth=5, status_neopixel=board.NEOPIXEL, debug=MATRIX_DEBUG)

# --- Set up the text areas ---
# Create a new textbox 0 for scrolling the Subject
matrixportal.add_text(
    text_font=terminalio.FONT,
    text_color=0x9b67fc,
    text_position=(0, 3),
    scrolling=True,
)

# Create a new textbox 1 time
matrixportal.add_text(
    text_font='fonts/Minecraftia-Regular-8.bdf',
    text_color=0x262022,
    text_position=(0, 21)
)

# Create a new textbox 2 response status
matrixportal.add_text(
    text_font='fonts/Minecraftia-Regular-8.bdf',
    # text_font=terminalio.FONT,
    text_position=(12, 31)
)

# Create a new textbox 3 for non-scrolling Subject
matrixportal.add_text(
    text_font=terminalio.FONT,
    text_color=0x9b67fc,
    text_position=(0, 3)
)
matrixportal.set_text('Setting time...', 1)

# try doing an AIO call before getting time and avoid bug
# https://github.com/adafruit/Adafruit_CircuitPython_MatrixPortal/issues/51
before_time = time.monotonic()
matrixportal.get_io_feed(secrets['aio_feed'])
if DEBUG:
    print(f'AIO get_io_feed response time: {time.monotonic() - before_time}')

# Need to set the clock to local time
before_time = time.monotonic()
matrixportal.get_local_time(location=secrets['timezone'])
# set variable to manage time resync period
last_time_sync = time.monotonic()

# now that we connected to the network to get the time,
# we can display the local time
curr_time = my_local_time(6)
matrixportal.set_text_color(0x6666FF, 1)

matrixportal.set_text(curr_time, 1)

if DEBUG:
    print(f'AIO get_local_time response time: {time.monotonic() - before_time}')
    print(f'time.localtime: {curr_time}')


def main():
    # because this get changed for simulated data, declare it as global
    global POLL_SECS

    # for testing
    if USE_SIM_DATA:
        if DEBUG:
            before_mem = gc.mem_free()
            gc.collect()
            print(
                f'Simulating data, Available Heap before: {before_mem} after: {gc.mem_free()}')
        POLL_SECS = 5  # shorten the poll time to make the test go quicker
        # appt_data = sim.get_sim_data(meet_stat='None', subject='Me too!!!', resp_stat='Not Responded', ttime=None)
        appt_data = sim.get_sim_data()

    # Typical path to get the latet appointment from AIO
    else:
        # check to see if the feed exists
        try:
            before_time = time.monotonic()
            if DEBUG:
                print(f'{my_local_time()} right before get_io_data()')
            ol_event_feed = matrixportal.get_io_data(secrets['aio_feed'])
            # ol_event_feed = matrixportal.network.fetch_data(
                # _RECENT_DATA_URL, headers=_HEADER, json_path=(_PATH,))
            if DEBUG:
                print(f'{my_local_time()} Available Heap: {gc.mem_free()}')
                print(
                    f'{my_local_time()} AIO get_io_data response time: {time.monotonic() - before_time}')
        except AdafruitIO_RequestError:
            matrixportal.set_text_color(0xFF0000, 1)
            matrixportal.set_text('Feed error', 1)
            time.sleep(30)
            # continue
        except ValueError as e:
            if DEBUG:
                print(f'{my_local_time()} ValueError: {e}')
            # continue
        except RuntimeError as e:
            if DEBUG:
                print(f'{my_local_time()} RuntimeError: {e}')
            # continue				
        # handle no data on AIO
        if len(ol_event_feed) == 0:
            # set all appt_data fields for nothing to display
            if DEBUG:
                print(f'{my_local_time()} No meetings to display')
            appt_data = {}
            appt_data['subject'] = ''
            appt_data['responseStatus'] = 'No meeting'
            appt_data['meeting_status'] = ''
            # make up a start time
            appt_data['start'] = time.mktime(time.localtime())

        else:
            # use this with get_io_data()
            appt_data = json.loads(ol_event_feed[0]['value'])
            # use this with network.fetch_data()
            # appt_data = json.loads(ol_event_feed[0])

            if DEBUG:
                print(f'appt_data: {appt_data}')
                print(f'appt_data["subject"]: {appt_data["subject"]}')
                print(f'appt_data["start"]: {appt_data["start"]}')

    # if DEBUG:
    #     before_mem = gc.mem_free()
    #     gc.collect()
    #     print(f'{my_local_time()} Available Heap before: {before_mem} after: {gc.mem_free()}')
    if len(appt_data['subject']) > SUBJECT_SCROLL_LIMIT:
        matrixportal.set_text(appt_data['subject'].strip(), 0)
        matrixportal.set_text('', 3)
    else:
        matrixportal.set_text(appt_data['subject'].strip(), 3)
        matrixportal.set_text(' ', 0)

    # Set Response status text and icon
    status_display = compute_status(appt_data['responseStatus'],appt_data['meeting_status'])
    print(f'{my_local_time()} status_display: {status_display}')
    matrixportal.set_text(status_msg[status_display]['text'], 2)
    matrixportal.set_text_color(
        status_msg[status_display]['color'], 2)
    matrixportal.set_background(
        status_msg[status_display]['icon'], [0, 21])

    # to set up for the re-poll time, get the last update time
    last = time.time()
    # Need to loop to allow the scrolling text to be continuously displayed
    # Loop until the re-poll time is over
    while time.time() - last < POLL_SECS:
        # calculate the time row contents
        count_down_str, count_down_stat_color = get_count_down(
            appt_data['start'], appt_data['responseStatus'])
        matrixportal.set_text_color(count_down_stat_color, 1)
        matrixportal.set_text(count_down_str, 1)
        # scroll the text
        matrixportal.scroll_text(SCROLL_DELAY)
    
    gc.collect()
    if DEBUG:
        print(f'{my_local_time()} Available Heap: {gc.mem_free()}')


if __name__ == '__main__':
    while True:
        # check for time resync. The MatrixPortal clock seems to drift enough over long 
        # periods that the meeting count down display is misleading
        if (time.monotonic() - last_time_sync > TIME_RESYNC):
            last_time_sync = time.monotonic()
            matrixportal.get_local_time(location=secrets['timezone'])
            if DEBUG:
                print(f'Time resync: {my_local_time()}')
        main()
