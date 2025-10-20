import os, asyncio, datetime, requests
from dotenv import load_dotenv
from playwright.async_api import async_playwright

CALENDLY_URL = "https://calendly.com/d/cpg8-rvf-4hq/jsm-virtual-lease-signing?month=2025-"
CUTOFF = datetime.date(2025, 12, 3)                     # earliest you’ll accept
DAYS_TO_SCAN = 21 

load_dotenv()
NTFY_TOPIC = os.getenv("NTFY_TOPIC")

def notify(msg: str, title="Calendly Slot"):
    """Send a notification to your ntfy topic."""
    url = f"https://ntfy.sh/{NTFY_TOPIC}"
    try:
        resp = requests.post(
            url,
            data=msg.encode("utf-8"),
            headers={
                "Title": title,
                "Priority": "high",
            },
            timeout=5,
        )
        if resp.status_code == 200:
            print(f"[notify] sent to ntfy topic '{NTFY_TOPIC}'")
        else:
            print(f"[notify:error] {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"[notify:error] {e}")


async def my_slots(start_date: datetime.date, cutoff_date: datetime.date, page):
    counter = start_date.month
    page_to_check = CALENDLY_URL + str(counter)
    page.goto(page_to_check)
    html_content = await page.content()
    print("times in" in html_content)


async def has_slots_on(page, date: datetime.date) -> bool:

    # check for the string "no times in"
    # if no string, move to the next month if the month is still within the range

    # if no times in is present on the page, then there are available slots
    # if there is a slot earlier than a certain date, then send the noti

    # Calendly dates usually have aria-labels like: "Choose Tuesday, December 2, 2025"
    label = date.strftime("Choose %A, %B %-d, %Y") if os.name != "nt" else date.strftime("Choose %A, %B %#d, %Y")
    # Click the date; if it exists, the times list will render; otherwise it won’t
    try:
        await page.get_by_role("button", name=label).click(timeout=1500)
    except:
        return False
    # If times appear, Calendly renders time-slot buttons; look for any button in the times panel
    try:
        await page.wait_for_selector("div[data-component*='time'] button, button:has-text('AM'), button:has-text('PM')", timeout=1500)
        return True
    except:
        return False

async def main():

    output_string = "Found earlier dates:\n"

    months = {
        1: "January",
        2: "February",
        3: "March",
        4: "April",
        5: "May",
        6: "June",
        7: "July",
        8: "August",
        9: "September",
        10: "October",
        11: "November",
        12: "December",
    }

    counter = datetime.date.today().month
    cutoff_date = datetime.date(2025, 12, 9)

    earlier_found = False

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"),
            locale="en-US",
            timezone_id="America/Chicago",
            service_workers="block",   # avoid SW holding connections open
        )
        page = await context.new_page()

        while counter <= cutoff_date.month:
            print("Checking month:", months[counter])
            page_to_check = CALENDLY_URL + str(counter)
            await page.goto(page_to_check, wait_until="domcontentloaded", timeout=60000)
            print("Done loading page.")

            try:
                await page.wait_for_selector("text=No times in", timeout=20000)
            except:
                pass

            html_content = await page.content()
            if "No times in" in html_content:
                print("No available times in", months[counter])
            else:
                # get all the button elements with the aria-label
                btns = page.locator('button[aria-label$="Times available"]')
                count = await btns.count()
                for i in range(count):
                    # filter out the date
                    btn_string = await btns.nth(i).get_attribute("aria-label")
                    date_string = ""
                    for i in btn_string:
                        if i in "0124356789":
                            date_string += i
                    date_string = int(date_string)

                    if counter < cutoff_date.month:
                        earlier_found = True
                        print(f"EARLIER MONTH: {months[counter]} {date_string}")
                        output_string += f"EARLIER MONTH: {months[counter]} {date_string}\n"
                    else:
                        if date_string < cutoff_date.day:
                            earlier_found = True
                            print(f"same month, earlier day: {months[counter]} {date_string}")
                            output_string += f"EARLIER MONTH: {months[counter]} {date_string}\n"

            counter += 1
        
        if not earlier_found:
            print("No earlier dates found.")
        else:
            notify(output_string)
        

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())