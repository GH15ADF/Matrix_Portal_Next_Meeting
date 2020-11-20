""" Poll the local Outlook client and send the most recent appointment to an AIO feed.

Mostly based on https://pythoninoffice.com/get-outlook-calendar-meeting-data-using-python/

Outlook AppointmentItem object COM reference:
    https://docs.microsoft.com/en-us/office/vba/api/outlook.appointmentitem
"""
from json.decoder import JSONDecodeError
from typing import Tuple
from Adafruit_IO import Client, RequestError
import time
import json
import logging
import win32com.client
import win32com
from datetime import datetime
import datetime as dt

MINUTES_BACK = 5
DAYS_AHEAD = 2
POLL_SECS = 60

UPLOAD = True  # prevent AIO posts during debugging
MULTIPLE_APPTS_STR = "*** Multiple ***"

# import Adafruit IO key and feed name
try:
    from secrets import secrets
except ImportError:
    print('AIO secrets are kept in secrets.py, please add them there!')
    raise

# --- Some helpful Outlook constants ---

# https://docs.microsoft.com/en-us/office/vba/api/outlook.olresponsestatus
ResponseStatus = ["None", "Organizer", "Tentative",
                  "Accepted", "Declined", "Not Responded"]

# https://docs.microsoft.com/en-us/office/vba/api/outlook.olimportance
Importance = ["Low", "Normal", "High"]

# https://docs.microsoft.com/en-us/office/vba/api/outlook.olmeetingstatus
MeetingStatus = ["None", "Meeting", "", "Received", "", "Canceled", "", "Received/Canceled"]

# --- Logging if you want ---
logging.basicConfig(
    format='%(asctime)s %(funcName)s - %(message)s', level=logging.INFO)

# Connect to the AIO Feed
aio = Client(secrets["aio_username"], secrets["aio_key"])


def get_outlook_appts(begin: datetime, end: datetime) -> Tuple[str, int, str]:
    """
    Retrieve the next Outlook appointment details

    Return the next Outlook appointment subject, start time, and response status. The start time is
    Unix Epoch local time to help calculations. If there are more than one appointments scheduled at the start time,
    the subject is set to MULTIPLE_APPTS_STR

    :param datetime begin: the filter for appointments with start times after this time
    :param datetime end: the filter appointments with start times no later than this time
    :return: tuple of subject, start time, response status, meeting status
    """
    logging.debug("begin: %s end: %s", begin, end)

    outlook = win32com.client.Dispatch(
        'Outlook.Application').GetNamespace('MAPI')
    calendar = outlook.getDefaultFolder(9).Items
    calendar.IncludeRecurrences = True
    calendar.Sort('[Start]')

    # https://docs.microsoft.com/en-us/office/vba/api/outlook.items.restrict
    # important to add the AM/PM format code %p otherwise the API seems to not handle the time right
    # https://strftime.org/
    restriction = "[Start] >= '" + begin.strftime('%m/%d/%Y %I:%M %p') + "' AND [END] <= '" + end.strftime(
        '%m/%d/%Y %I:%M %p') + "'"
    logging.debug("Initial restriction: %s", restriction)
    calendar = calendar.Restrict(restriction)

    # for debugging
    for item in calendar:
        logging.debug("Appt--> %s|%s|%s|%s|%s", item.start, item.subject,
                      ResponseStatus[item.responseStatus], Importance[item.Importance], MeetingStatus[item.MeetingStatus])

    # to detect multiple appointements at the same time, filter again
    # assume calendar[0] has the earliest start time to filter on
    restriction = "[Start] = '" + \
        calendar[0].start.strftime('%m/%d/%Y %I:%M %p') + "'"
    logging.debug("Multiple appts restriction: %s", restriction)
    calendar = calendar.Restrict(restriction)

    # It appears that you need to load calendar appointments COM Object into a list since the 
    # calendar object does not seem to behave like a real list
    # load what's left into a list
    cal_items = []
    for item in calendar:
        cal_items.append({
            "start":item.start, 
            "subject": item.subject, 
            "resp_stat":ResponseStatus[item.responseStatus],
            "importance":Importance[item.Importance],
            "meeting_status":MeetingStatus[item.MeetingStatus]})
    appt_count = len(cal_items)
    logging.debug("Appts list size %d", appt_count)

    if appt_count > 1:
        subject = MULTIPLE_APPTS_STR
        start = int(cal_items[0]["start"].timestamp())
        response_status = "None"
        meeting_status = "None"
    elif appt_count == 1:
        subject = cal_items[0]["subject"]
        start = int(cal_items[0]["start"].timestamp())
        response_status = cal_items[0]["resp_stat"]
        meeting_status = cal_items[0]["meeting_status"]
    else:  # handle nothing in Outlook to return at this point
        subject = "None"
        start = ""
        response_status = ""
        meeting_status = ""

    return subject, start, response_status, meeting_status


def send_to_aio(key: str, data: str) -> None:
    """Send data to AIO. Will not send anything if UPLOAD is not True
    :param str key: the feed name
    :param str data: the data to send
    """
    if UPLOAD:
        # need to send as JSON
        aio.send_data(key, data)

        data = aio.receive(key)
        logging.debug("Latest value from OL_Event: %s", data.value)
        logging.debug(
            "Recieved value from OL_Event feed has the following metadata: %s", data)
    else:
        logging.debug("*** DEBUG MODE: AIO send SKIPPED ***")


def main():
    # get the Outlook calendar entries from now back 30 minutes and one day ahead
    now = dt.datetime.now()

    logging.debug("formatted from: %s", datetime.strftime(
        now - dt.timedelta(minutes=MINUTES_BACK), "%Y-%m-%d %I:%M %p"))

    logging.debug("formatted to: %s", datetime.strftime(
        now + dt.timedelta(days=DAYS_AHEAD), "%Y-%m-%d %I:%M %p"))

    # get the next appointment
    subject, start_time, resp_stat, meeting_status = get_outlook_appts(\
        dt.datetime.now() - dt.timedelta(minutes=MINUTES_BACK), \
        dt.datetime.now() + dt.timedelta(days=DAYS_AHEAD))

    # strip the subject in case a subject has trailing spaces
    curr_latest = {"start": start_time,
                   "subject": subject.strip(), 
                   "responseStatus": resp_stat,
                   "meeting_status" : meeting_status}
    upload = json.dumps(curr_latest)
    logging.debug("JSON to AIO: %s", upload)

    logging.debug("Sending to AIO")
    # Create an instance of the REST client

    # Set up the AIO feed
    try:
        aio_appt_feed = aio.feeds(secrets["feed_name"])
    except RequestError as re:  # Doesn't exist, print error message
        logging.error(re)
        exit()

    # get the latest value
    try:
        aio_latest = aio.receive(secrets["feed_name"])
        logging.debug(
            "Recieved value from OL_Event feed has the following metadata: %s", aio_latest)
        # Tip: to replace double quotes as single to load as a JSON into a dict
        # value_dict = json.loads(latest.value.replace("'", '"'))

        aio_latest_dict = json.loads(aio_latest.value)
        logging.debug("The value parameter as a dict: is %s", aio_latest_dict)
        logging.debug("display start is %s", curr_latest["start"])
        logging.debug("returned start is %s", aio_latest_dict["start"])
        logging.debug("display subject is %s", curr_latest["subject"])
        logging.debug("returned subject is %s", aio_latest_dict["subject"])
        logging.debug("id for AIO item is %s", aio_latest.id)

        if aio_latest_dict["start"] == curr_latest["start"] \
            and aio_latest_dict["subject"] == curr_latest["subject"] \
            and aio_latest_dict["responseStatus"] == curr_latest["responseStatus"]:
            logging.debug("SKIPPING SEND: latest and current are the same")
        else:
            logging.debug("different appointment processing")

            resp = aio.delete(aio_appt_feed.key, aio_latest.id)
            logging.debug("delete response %s", resp)

            # need to send as JSON
            logging.info("sent %s", curr_latest["subject"])
            send_to_aio(aio_appt_feed.key, upload)

    except RequestError:
        logging.warning("No entries in AdafruitIO")
        # this happens when it is a new feed or you delete all the entries
        send_to_aio(aio_appt_feed.key, upload)
    except JSONDecodeError as e:
        logging.warning("JSON error from AdafruitIO")
        logging.error("Exception: %s", e)
    except Exception as e:
        logging.error("Exception: %s", e)
        exit()


if __name__ == "__main__":
    logging.info("starting up...")
    while True:
        main()
        time.sleep(POLL_SECS)
