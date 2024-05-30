from datetime import datetime
from pathlib import Path
import time
import json
import requests
import fire

DAY_PARSER = ["today", "tomorow", "in 2 days"]
TIME_PARSER = ["in the morning", "at noon", "in the evening", "at night"]
LOGDIRPATH = "weather_logging"
logdir = Path(LOGDIRPATH)
logdir.mkdir(exist_ok=True)


def send_notif(url, title, message):
    "Use ntfy.sh to send a notification on your device"
    if not message:
        message = " "
    requests.post(
        url=url,
        headers={"Title": title},
        data=message.encode("utf-8"),
    )


def main(
    location,
    ntfy_url=None,
    rain_threshold_mm=1.0,
    n_days_average_temp=3,
    temp_tolerance=3,
    wttr_url="http://wttr.in/",
    timeout_s=5,
    retry_for_an_hour=True,
):
    """
    Simple script to parse wttr.in to know if it's going to rain.
    Output is either a notification to your phone (via ntfy.sh) or a print.

    Parameters
    ----------
    location: str
        example: NewYorkCity or Paris.75015 etc
    ntfy_url: str, defautl to None
        if None, will simply print the output
    rain_threshold_mm: float, default 1.0
    n_days_average_temp: int, default 3
       number of days over which to average the temperature to warn you
    temp_tolerance: int, default 3
       if the average temperature of today differs by more than
       this number from the nast n_days_average_temp days, warn user

    wttr_url: str, default 'http://wttr.in/'
    timeout_s: int, default 5
        timeout for wttr.in in second
    retry_for_an_hour: bool, default True
        if True, will retry every 5 minutes for 1h
    """
    # getting data
    url = wttr_url + location + "?format=j1"
    if not retry_for_an_hour:
        try:
            response = requests.get(
                url,
                timeout=timeout_s,
            )
        except requests.exceptions.ReadTimeout:
            raise Exception(f"Couldn't reach wttr.in after {timeout_s}s")
        except Exception as err:
            send_notif(
                ntfy_url,
                "Weather notifier - Error",
                f"Error when requestion weather: '{err}'"
            )
    else:
        start_time = time.time() - 1
        trial = 0
        response = None
        err = "No error message yet"
        while time.time() - start_time < 60 * 60:
            trial += 1
            try:
                response = requests.get(
                    url,
                    timeout=timeout_s,
                )
                assert response.status_code == 200, f"Unexpected status code: '{response.status_code}'"
                json.loads(response.text)  # try to load directly, it would be caught
            except Exception:
                time.sleep(60 * 5)  # wait 5 minute
                continue
            break
        if response is None:
            raise Exception(f"Couldn't reach wttr.in after {trial} trials over 1h. Error was: {err}")

    # load the average temperature of the last few days
    past_logs = sorted([p for p in logdir.rglob("*json")], key=lambda p: int(p.stem))
    if past_logs:
        dates = []
        temperatures = []
        for logfile in past_logs:
            with logfile.open("r") as f:
                data = json.load(f)
            date = data["weather"][0]["date"]
            if date in dates:
                temperatures[-1].append(float(data["weather"][0]["avgtempC"]))
            else:
                dates.append(date)
                temperatures.append([float(data["weather"][0]["avgtempC"])])
        assert len(dates) == len(temperatures)
        averages = []
        for date, data in zip(dates, temperatures):
            averages.append(sum(data) / len(data))
        averages = averages[-n_days_average_temp:]
        reference_temp = sum(averages) / len(averages)
    else:
        reference_temp = None

    # load data from the request
    data = json.loads(response.text)

    # save to file
    with (logdir / (str(int(time.time())) + ".json")).open("w") as f:
        json.dump(data, f, indent=4)

    raining = []
    depth = []
    confidence = []
    mintemps = []
    maxtemps = []
    avgtemps = []
    for iday, day in enumerate(data["weather"]):
        raining.append([])
        buffmm = []
        buffconf = []

        mintemps.append(float(day["mintempC"]))
        maxtemps.append(float(day["maxtempC"]))
        avgtemps.append(float(day["avgtempC"]))

        for ih, hour in enumerate(day["hourly"]):
            if ih % 2 == 0:
                buffmm.append(float(hour["precipMM"]))
                buffconf.append(int(hour["chanceofrain"]))
            else:
                buffmm[-1] += float(hour["precipMM"])
                buffconf[-1] += int(hour["chanceofrain"])
                buffconf[-1] /= 2
        assert len(buffmm) == 4 and len(buffconf) == 4

        for br in buffmm:
            if br >= rain_threshold_mm:
                raining[-1].append(True)
            else:
                raining[-1].append(False)
        depth.append(buffmm)
        confidence.append(buffconf)

    message = ""
    for iday in range(len(raining)):
        if any(raining[iday]):
            newline = f"\nRaining {DAY_PARSER[iday]} "
            newline += ", ".join(
                [
                    f"{TIME_PARSER[ir]} ({float(depth[iday][ir]):.1f}mm {int(confidence[iday][ir]):02d}%)"
                    for ir, r in enumerate(raining[iday])
                    if r
                ]
            )
            if "," in newline:
                newline = newline[::-1].replace(", ", " and ", 1)[::-1]
            message += newline + "\n"

        if reference_temp:
            diff = avgtemps[iday] - reference_temp
            if abs(diff) >= temp_tolerance:
                adj = "colder" if diff > 0 else "warmer"
                sign = "+" if diff > 0 else "-"
                newline = f"\nTemp: {DAY_PARSER[iday]} {int(reference_temp)}->{int(avgtemps[iday])}°C : {sign}{int(abs(diff))}°C ({int(mintemps[iday])}°C / {int(maxtemps[iday])}°C)"
                message = message.strip() + "\n" + newline

    # remove extra newlines
    message = "\n".join([li.strip() for li in message.splitlines()])

    message = message.strip() + "\n\nAverage temperature: " + "°C  ".join([str(int(x)) for x in avgtemps]) + "°C"
    message = message.strip() + "\nMin/Max temperature: " + "°C  ".join([str(int(x)) + "/" + str(int(y)) for x, y in zip(mintemps, maxtemps)]) + "°C"

    title = []
    if "raining" in message.lower():
        title += ["rain incoming"]
    if "temp" in message.lower():
        title += [f"delta temperature of last {n_days_average_temp} days"]
    if not title:
        title.append("all good")
    title = "Weather: " + " & ".join(title).title()

    if ntfy_url:
        send_notif(ntfy_url, title, message.strip())
    else:
        return f"{title}\n{message.strip()}"


if __name__ == "__main__":
    kwargs = fire.Fire(lambda **kwargs: kwargs)
    if "help" in kwargs:
        print(help(main))
        raise SystemExit()
    try:
        out = main(**kwargs)
        if out:
            print(out)
    except Exception as err:
        if "ntfy_url" in kwargs:
            send_notif(
                kwargs["ntfy_url"],
                "Weather notifier - Error",
                f"Error when parsing weather: {err}",
            )
        else:
            raise
