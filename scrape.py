# tribe-events-calendar-month__events

import time
import undetected_chromedriver as uc
from bs4 import BeautifulSoup

# Set up undetected Chrome
options = uc.ChromeOptions()
options.headless = True  # Set to False if you want to watch the browser
driver = uc.Chrome(options=options)

# Load the events page
url = "https://oahubusinessconnector.org/events/"
driver.get(url)

# Wait for page to load fully — increase time if needed
time.sleep(5)

# Get the full rendered page HTML
html = driver.page_source
soup = BeautifulSoup(html, 'html.parser')

# Find all <td> elements with class that includes 'tribe-events-calendar-month__events'
event_cells = soup.find_all('td')
matching_cells = []

for cell in event_cells:
    if cell.has_attr('class') and any('tribe-events-calendar-month__events' in cls for cls in cell['class']):
        matching_cells.append(cell)

# Print stripped text content
for event in matching_cells:
    print(event.text.strip())

driver.quit()
