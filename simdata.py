from constants import time_display_colors
import time

class sim:

    def __init__(self):
        self.start_times_ctr = 0
        self.start_times = [">1 day", 
                            ">1hr <1day", 
                            "alert", 
                            "warning", 
                            "<1hr >warning",
                            "in progress"]
        self.resp_statuses_ctr = 0
        self.resp_statuses = ["Accepted",
                                "Canceled",
                                "None",
                                "Not Responded",
                                "Organizer",
                                "Tentative"]
        self.subjects_ctr = 0
        self.subjects = ["Short",
                        "     white space                 ",
                        "LONG -- >Lorem ipsum dolor sit amet, consectetur adipiscing elit. ",
                        "specials `!@#$%^&*()_+-=[]\{}|;':\",./<>?"]
        self.SIM_DATA_TIME = "in progress"
        self.appt_data = {"start":time.time(),"subject": "","responseStatus" : ""}

    def print(self):
        print(self.appt_data)

    def get_sim_data(self):
        # get the current time to start
        sim_test_time = time.time()
        self.appt_data["subject"] = self.subjects[self.subjects_ctr % len(self.subjects)]
        self.appt_data["responseStatus"] = self.resp_statuses[self.resp_statuses_ctr % len(self.resp_statuses)]
        self.SIM_DATA_TIME = self.start_times[self.start_times_ctr % len(self.start_times)]
        self.subjects_ctr += 1
        self.start_times_ctr += 1
        self.resp_statuses_ctr += 1

        if self.SIM_DATA_TIME == ">1 day":
            self.appt_data["start"] = sim_test_time + (24 + 1)*60*60

        if self.SIM_DATA_TIME == ">1hr <1day":
            self.appt_data["start"] = sim_test_time + 12*60*60

        if self.SIM_DATA_TIME == "alert":
            self.appt_data["start"] = sim_test_time + \
                time_display_colors["alert"]["trigger"]

        if self.SIM_DATA_TIME == "warning":
            self.appt_data["start"] = sim_test_time + \
                time_display_colors["warning"]["trigger"]

        if self.SIM_DATA_TIME == "<1hr >warning":
            self.appt_data["start"] = sim_test_time + \
                time_display_colors["warning"]["trigger"] + 10*60

        if self.SIM_DATA_TIME == "in progress":
            self.appt_data["start"] = sim_test_time

        return self.appt_data
