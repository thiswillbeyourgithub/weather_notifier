# Weather Notifier
Cron friendly python script to query [wttr.in](https://github.com/chubin/wttr.in) for rain then send a notification on your phone using [ntfy.sh](https://ntfy.sh/). Also tells you if the temperature of each of the next 3 days will be different than the average over the previous X days.

## Usage
* `python -m pip install -r requirements.txt`
* `python wttr_notifier.py --location London --ntfy_url https://ntfy.sh/[YOURTOKEN]`

## Cron line
`0 8 * * * cd /YOUR/PATH/wttr_notifier/ && python wttr_notifier.py --location "London" --ntfy_url https://ntfy.sh/[YOURTOKEN]`
`0 18 * * * cd /YOUR/PATH/wttr_notifier/ && python wttr_notifier.py --location "London" --ntfy_url https://ntfy.sh/[YOURTOKEN]`
