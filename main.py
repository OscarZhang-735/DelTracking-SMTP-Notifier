import smtplib
from email.mime.text import MIMEText
import json
from email.utils import formataddr
import requests
import datetime
import logging
import os

RUNNING_MODE = "LOCAL"


def exception_reporter(exception):
    exec_sender = Sender()
    msg = f"An error occurred at {datetime.datetime.now()}.\n\nError\n: {exception}"
    exec_sender.send(msg, title="Tracking System Failed")
    logger.error(msg)
    logger.warning("Failure Reported.")
    quit()


class Utils:
    class Files:
        @staticmethod
        def read_json(file_name):
            with open(file_name, "r") as f:
                return json.load(f)

        @staticmethod
        def write_json(file_name, json_data):
            with open(file_name, "w") as f:
                json.dump(json_data, f)
            return True


class Tracker:
    def __init__(self):
        self.data = Utils.Files.read_json("config.json")
        self.tracking_nums = self.data["tracking_nums"]

    def orange_delivery(self):
        base_url = r"http://203.195.161.123:8180/trackList?searchList.waybillnumber="
        results = []
        try:
            for tracking_num in self.tracking_nums:
                url = base_url + str(tracking_num)
                response_data = json.loads(requests.post(url).text)
                logger.info(f"{self.tracking_nums.index(tracking_num) + 1}/{len(self.tracking_nums)}: {response_data}")
                results.append(response_data)
            change = {}
            for new, old in zip(results, self.data["results"]):
                if new["data"][0]["outinfo"] != old["data"][0]["outinfo"]:
                    change[new["data"][0]["showsystemnumber"]] = [old["data"][0]["outinfo"], new["data"][0]["outinfo"],
                                                                  new["data"][0]["outdate"]]
                    logger.info(new["data"][0]["showsystemnumber"] + " Updated.")
            self.data["results"] = results
            Utils.Files.write_json("config.json", self.data)

            return [results, change]
        except Exception as e:
            logger.warning("Failed tracking.")
            exception_reporter(e)


class Sender:
    def __init__(self):
        config_data = Utils.Files.read_json("config.json")
        if RUNNING_MODE == "LOCAL":
            self.sender = config_data["sender"]
            self.password = config_data["passwd"]
            self.receiver = config_data["receiver"]
        elif RUNNING_MODE == "ONLINE":
            self.sender = os.getenv("sender")
            self.password = os.getenv("passwd")
            self.receiver = os.getenv("receiver")

        try:
            self.smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465)
            self.smtp.login(self.sender[1], self.password)
            logger.info("Successfully log in.")
        except Exception as e:
            logger.warning("Failed log in.")
            exception_reporter(e)

    def send(self, message, title="Delivery Tracking Updates"):
        try:
            msg = MIMEText(message, "plain", "utf-8")
            msg['From'] = formataddr((self.sender[0], self.sender[1]))
            msg["Subject"] = title
            msg["To"] = formataddr((self.receiver[0], self.receiver[1]))
            self.smtp.sendmail(self.sender, [self.receiver[1]], msg.as_string())
            logger.info("Successfully sent.")
            self.smtp.close()
            logger.info("SMTP server closed.")
        except Exception as e:
            logger.warning("Failed sent.")
            exception_reporter(e)

    def message_generator(self, data: list):
        msg = "Updated Deliveries:\n\n"
        i = 0
        msg += f"{len(data[1])} of {len(data[0])} deliveries updated.\n\n"
        for num in data[1]:
            i += 1
            msg += f"Package ({i}/{len(data[1])}):\nSystem Number: {num}\nPrevious: {data[1][num][0]}\nNow: {data[1][num][1]} \nLast Update: {data[1][num][2]}\n\n"
        return msg


def run():
    logger.info(f"Delivery Tracking Started")
    t = Tracker()
    data = t.orange_delivery()
    if data[1] == {}:
        logger.info("No Delivery Updates.")
        logger.info(f"Delivery Tracking Ended")
        quit()
    s = Sender()
    s.send(s.message_generator(data))
    logger.info(f"Delivery Tracking Ended")


if __name__ == '__main__':
    logger = logging.getLogger("logger")
    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler("app.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s]: %(message)s"))
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s]: %(message)s"))
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    run()
