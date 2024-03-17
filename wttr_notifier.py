import json
import requests
import fire

DAY_PARSER = ["today", "tomorow", "in 2 days"]
TIME_PARSER = ["in the morning", "at noon", "in the evening", "at night"]


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
    rain_threshold_mm=1.0,
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
    rain_threshold_mm: float, default 1.0

    wttr_url: str, default 'http://wttr.in/'
    timeout: int, default 5
        timeout for wttr.in
    """
    # getting data
    url = wttr_url + location + "?format=j1"
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

    data = json.loads(response.text)

    raining = []
    depth = []
    confidence = []
    for iday, day in enumerate(data["weather"]):
        raining.append([])
        buffmm = []
        buffconf = []
        for ih, hour in enumerate(day["hourly"]):
            if ih % 2 == 0:
                buffmm.append(float(hour["precipMM"]))
                buffconf.append(int(hour["chanceofrain"]))
            else:
                buffmm[-1] += float(hour["precipMM"])
                buffconf[-1] += int(hour["chanceofrain"])
        assert len(buffmm) == 4 and len(buffconf) == 4

        for br in buffmm:
            if br >= rain_threshold_mm:
                raining[-1].append(True)
            else:
                raining[-1].append(False)
        depth.append(buffmm)
        confidence.append(buffconf)

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
                        f"{TIME_PARSER[ir]} ({depth[iday][ir]}mm {confidence[iday][ir]:02d}%)"
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
