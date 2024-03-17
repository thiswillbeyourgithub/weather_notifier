import requests
import fire

RAIN_THRESHOLD = 1

DAY_PARSER = ["today", "tomorow", "in 2 days"]
TIME_PARSER = ["in the morning", "at noon", "in the evening", "at night"]


def parse_col(col):
    """
    Parse a column like
    ['0.0 mm | 81%', '0.0 mm | 0%', '0.0 mm | 0%', '0.0 mm | 0%']
    and tell which part of the day will be rainy along with confidence
    """
    mm = float(col.split("mm")[0].strip())
    confidence = col.split("|")[1].strip()
    if mm > RAIN_THRESHOLD:
        return {"state": True, "depth": mm, "confidence": confidence}
    else:
        return {"state": False, "depth": mm, "confidence": confidence}


def send_notif(url, title, message):
    "Use ntfy.sh to send a notification on your device"
    requests.post(
        url=url,
        headers={"Title": title},
        data=message.encode("utf-8"),
    )


def main(
    location,
    ntfy_url=None,
    wttr_url="http://wttr.in/",
    timeout=5,
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
    wttr_url: str, default 'http://wttr.in/'
    timeout: int, default 5
        timeout for wttr.in
    """
    # getting data
    url = wttr_url + location + "?T"
    try:
        response = requests.get(
            url,
            timeout=timeout,
        )
    except requests.exceptions.ReadTimeout:
        if ntfy_url:
            send_notif(
                ntfy_url, "Wttr.in timeout", f"Couldn't reach wttr.in after {timeout}s"
            )
        else:
            return "Wttr.in timed out after {timeout}s"

    text = response.text

    # get lines that indicate milimeters of rain
    forecast_lines = []
    lines = text.splitlines()
    for line in lines:
        if line.count(" mm") == 4:
            forecast_lines.append(line)
    assert len(forecast_lines) == 3, f"Found {len(forecast_lines)} lines instead of 3"

    # for each line of a day, get the 4 column indicating the mm for
    # morning, noon, evening, night
    forecast = []
    for line in forecast_lines:
        # example of line:
        # │     ‘ ‘ ‘ ‘   0.0 mm | 81%   │               0.0 mm | 0%    │               0.0 mm | 0%    │               0.0 mm | 0%    │'

        columns = [l.strip() for l in line.split("│") if l.strip()]
        for i, c in enumerate(columns):
            while not c[0].isdigit():
                c = c[1:]
            while c[-1] != "%":
                c = c[:-1]
            columns[i] = c
        # example of columns:
        # ['0.0 mm | 81%', '0.0 mm | 0%', '0.0 mm | 0%', '0.0 mm | 0%']

        forecast.append(columns)

    parsed = [[parse_col(col) for col in cols] for cols in forecast]
    raining = []
    depth = []
    confidence = []
    for day in parsed:
        raining.append([])
        depth.append([])
        confidence.append([])
        for time in day:
            raining[-1].append(time["state"])
            depth[-1].append(time["depth"])
            confidence[-1].append(time["confidence"])

    if all(not any(r) for r in raining):
        if ntfy_url:
            send_notif(ntfy_url, "No rain for the next 2 days", "")
        else:
            return "No rain for the next 2 days"
    else:
        message = ""
        for iday in range(len(raining)):
            if any(raining[iday]):
                newline = f"Raining {DAY_PARSER[iday]} "
                newline += ", ".join(
                    [
                        f"{TIME_PARSER[ir]} ({depth[iday][ir]}mm {confidence[iday][ir]})"
                        for ir, r in enumerate(raining[iday])
                        if r
                    ]
                )
                if "," in newline:
                    newline = newline[::-1].replace(", ", " and ", 1)[::-1]
                message += newline + "\n"
        if ntfy_url:
            send_notif(ntfy_url, "Rain incoming", message.strip())
        else:
            return f"Rain incoming\n{message.strip()}"


if __name__ == "__main__":
    fire.Fire(main)
