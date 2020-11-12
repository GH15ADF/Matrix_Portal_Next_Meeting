"""
Display your next meeting's information on a Matrix Portal
"""

from adafruit_matrixportal.matrixportal import MatrixPortal
from adafruit_matrixportal.network import Network
import board
import json
import time

# Display imports
import adafruit_display_text.label
import terminalio
from adafruit_io.adafruit_io import AdafruitIO_RequestError
import neopixel

# --- Configuration Settings ---
# repoll time in seconds
POLL_SECS = 60

# How many characters in the appointment subject before needing to scroll the text
SUBJECT_SCROLL_LIMIT = 10

# set the scroll text delay. More than 0.4 looks jerkie to me
SCROLL_DELAY = 0.04

# Display debug messages
DEBUG = True
# -------------------------------

# --- Simulation data ---
"""
Use these setting to simulate AIO responses locally debug the display look and feel
"""
USE_SIM_DATA = False
# SIM_DATA_TIME = ">1 day"
# SIM_DATA_TIME = ">1hr <1day"
# SIM_DATA_TIME = "alert"
# SIM_DATA_TIME = "warning"
# SIM_DATA_TIME = "<1hr >warning"
SIM_DATA_TIME = "in progress"
SIM_DATA = '{"start":1604790000, "subject":"simulated test", "responseStatus":"Organizer"}'
# -------------------------------

# setup for Response status

# icon bitmap
# https://icon-library.net/icon/icon-pixels-6.html
# in GIMP export to BMP after chaning Image mode to Indexed and Generate Optimum pallet
# choose advanced options and "16 bits A1 R5 G5 B5"
ResponseStatus = {"None": {"icon": "images/NR.bmp", "color": 0x444444},
                  "Organizer": {"icon": "images/exclaimation3.bmp", "color": 0xFCFC3F},
                  "Tentative": {"icon": "images/question.bmp", "color": 0x273077},
                  "Accepted": {"icon": "images/check.bmp", "color": 0x2f7727},
                  "Declined": {"icon": "images/X.bmp", "color": 0x684b2c},
                  "Not Responded": {"icon": "images/no-resp.bmp", "color": 0x888888},
                  "No meeting": {"icon": "", "color": 0x000000}}

# define color library for time display
time_display_colors = {
    "gt 1day": {"color": 0x154411, "trigger": 86400},
    "gt 1hr":  {"color": 0x33932A, "trigger": 86400},
    "normal":  {"color": 0x3b7a35, "trigger": 3600},  # 60 min
    "warning": {"color": 0xFCFC3F, "trigger": 600},  # 10 min
    "alert":   {"color": 0xCC0000, "trigger": 300},  # 5 min
    "in progress":   {"color": 0x0000FF, "trigger": 0},
    "No meeting":   {"color": 0x035400, "trigger": 0}
}

# --- Display setup ---
matrixportal = MatrixPortal(
    bit_depth=3, status_neopixel=board.NEOPIXEL, debug=DEBUG)


def get_count_down(start: str, resp_status: str) -> tuple(str, int):
    """ Calcuates the count down value and the color. Returns the count down string and the RGB color
        :param int start: unix epoch start time for the appointment
        :param str resp_status: Text to display as the response status
    """
    # handle the no meeting scenario
    if resp_status == "No meeting":
        cd_status = time_display_colors["No meeting"]["color"]
        status_string = "No meetings"
    else:
        # calculate the start_time string to return
        # figure out if the start time is AM or PM
        start_hour = time.localtime(start).tm_hour
        suffix = "p" if int(start_hour / 12) > 0 else "a"

        start_time = "{lhrs:0>2}:{lmin:0>2}{sfx}".format(
            lhrs=start_hour % 12 or 12, lmin=time.localtime(start).tm_min, sfx=suffix)

        # https://stackoverflow.com/questions/14904814/nameerror-global-name-long-is-not-defined
        # get the number of seconds for the countdown
        count_down_val = int(int(start)-time.mktime(time.localtime()))

        # calcuate the count down string
        # https://stackoverflow.com/questions/775049/how-do-i-convert-seconds-to-hours-minutes-and-seconds
        xmins, secs = divmod(count_down_val, 60)
        hrs, mins = divmod(count_down_val/60, 60)
        count_down_str = "{lmin:0>2}:{lsec:0>2}".format(
            lmin=int(mins), lsec=int(secs))

        if (count_down_val <= time_display_colors["in progress"]["trigger"]):
            cd_status = time_display_colors["in progress"]["color"]
            status_string = "In progress"
        elif count_down_val <= time_display_colors["alert"]["trigger"]:
            cd_status = time_display_colors["alert"]["color"]
            status_string = start_time + "  " + count_down_str
        elif (count_down_val <= time_display_colors["warning"]["trigger"]):
            cd_status = time_display_colors["warning"]["color"]
            status_string = start_time + "  " + count_down_str
        elif (count_down_val <= time_display_colors["normal"]["trigger"]):
            cd_status = time_display_colors["normal"]["color"]
            status_string = start_time + "  " + count_down_str
        elif (count_down_val > time_display_colors["normal"]["trigger"] and count_down_val <= time_display_colors["gt 1day"]["trigger"]):
            cd_status = time_display_colors["gt 1hr"]["color"]
            status_string = start_time + "  " + ">1 hr"
        elif (count_down_val > time_display_colors["gt 1day"]["trigger"]):
            cd_status = time_display_colors["gt 1day"]["color"]
            status_string = "> 1 day away"

        if DEBUG:
            print("start: ", int(start))
            print("start formatted:", time.localtime(start))
            print("{lhrs:0>2}:{lmin:0>2}".format(lhrs=time.localtime(
                start).tm_hour, lmin=time.localtime(start).tm_min))
            print("local time:", time.mktime(time.localtime()))
            print("count_down_val:", count_down_val)

    return status_string, cd_status


def main():

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
        # text_font="fonts/6x10.bdf",
        # text_font="fonts/Dogica_Pixel-8-8.bdf",
        text_font="fonts/Minecraftia-Regular-8.bdf",
        # text_color=0xEF7F31,
        text_color=0x262022,
        text_position=(0, (matrixportal.graphics.display.height // 2 + 4)),
    )

    # Create a new textbox 2 response status
    matrixportal.add_text(
        text_font=terminalio.FONT,
        text_position=(
            12, (2 * matrixportal.graphics.display.height // 3) + 3),
    )

    # Create a new textbox 3 for non-scrolling Subject
    matrixportal.add_text(
        text_font=terminalio.FONT,
        text_color=0x9b67fc,
        text_position=(0, 3)
    )

    # Some critical but private settings are in the secrets.py file
    try:
        from secrets import secrets
    except ImportError:
        print('WiFi secrets are kept in secrets.py, please add them there!')
        raise

    matrixportal.set_text("Setting time...", 1)

    # Need to set the clock to local time
    matrixportal.get_local_time(location=secrets['timezone'])

    # now that we connected to the network to get the time,
    # we can display the local time
    curr_time_struct = time.localtime()
    curr_time = "      {lhrs:0>2}:{lmin:0>2}:{lsec:0>2}".format(
                lhrs=curr_time_struct.tm_hour,
                lmin=curr_time_struct.tm_min,
                lsec=curr_time_struct.tm_sec)
    matrixportal.set_text_color(0x6666FF, 1)
    matrixportal.set_text(curr_time, 1)

    # main look that runs forever
    while True:
        # for testing
        if USE_SIM_DATA:
            print("Simulating data")
            appt_data = json.loads(SIM_DATA)
            sim_test_time = time.time()

            if SIM_DATA_TIME == ">1 day":
                sim_start_time = sim_test_time + (24 + 1)*60*60

            if SIM_DATA_TIME == ">1hr <1day":
                sim_start_time = sim_test_time + 12*60*60

            if SIM_DATA_TIME == "alert":
                sim_start_time = sim_test_time + \
                    time_display_colors["alert"]["trigger"]

            if SIM_DATA_TIME == "warning":
                sim_start_time = sim_test_time + \
                    time_display_colors["warning"]["trigger"]

            if SIM_DATA_TIME == "<1hr >warning":
                sim_start_time = sim_test_time + \
                    time_display_colors["warning"]["trigger"] + 10*60

            if SIM_DATA_TIME == "in progress":
                sim_start_time = sim_test_time

            appt_data["start"] = sim_start_time

        # Typical path to get the latet appointment from AIO
        else:
            # check to see if the feed exists
            try:
                ol_event_feed = matrixportal.get_io_data(secrets['aio_feed'])
            except AdafruitIO_RequestError:
                matrixportal.set_text_color(0xFF0000, 1)
                matrixportal.set_text('Feed error', 1)
                time.sleep(30)
                continue

            # handle no data on AIO
            if len(ol_event_feed) == 0:
                # set all appt_data fields for nothing to display
                print("No meetings to display")
                appt_data = {}
                appt_data["subject"] = ""
                appt_data["responseStatus"] = "No meeting"
                # make up a start time
                appt_data["start"] = time.mktime(time.localtime())

            else:
                first_item = ol_event_feed[0]
                print(first_item["value"])

                first_value = first_item["value"]
                # appt_data = json.loads(first_value.replace("'", '"'))
                appt_data = json.loads(first_value)
                print("appt_data: ", appt_data)

                print("appt_data[\"subject\"]:", appt_data["subject"])
                print("appt_data[\"start\"]", int(appt_data["start"]))

        if len(appt_data["subject"]) > SUBJECT_SCROLL_LIMIT:
            matrixportal.set_text(appt_data["subject"], 0)
            matrixportal.set_text("", 3)
        else:
            matrixportal.set_text(appt_data["subject"], 3)
            matrixportal.set_text(" ", 0)

        # Set Response status text and icon
        matrixportal.set_text(appt_data["responseStatus"], 2)
        matrixportal.set_text_color(
            ResponseStatus[appt_data["responseStatus"]]["color"], 2)
        matrixportal.set_background(
            ResponseStatus[appt_data["responseStatus"]]["icon"], [0, 21])

        # to set up for the re-poll time, get the last update time
        last = time.time()
        # Need to loop to allow the scrolling text to be continuously displayed
        # Loop until the re-poll time is over
        while time.time() - last < POLL_SECS:
            # calculate the time row contents
            count_down_str, count_down_stat_color = get_count_down(
                appt_data["start"], appt_data["responseStatus"])
            matrixportal.set_text_color(count_down_stat_color, 1)
            matrixportal.set_text(count_down_str, 1)
            # scroll the text
            matrixportal.scroll_text(SCROLL_DELAY)
            # do a little pause before repeating the scroll
            time.sleep(1)


if __name__ == "__main__":
    while True:
        main()
        time.sleep(POLL_SECS)
