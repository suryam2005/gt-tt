import streamlit as st
from datetime import datetime, timedelta
import re
from PyPDF2 import PdfReader
from ics import Calendar, Event
import pytz
from io import BytesIO

st.set_page_config(page_title="GT Class Calendar Generator")
st.title("📅 Georgia Tech ICS Generator")

# --- PDF PARSER ---
def extract_semester_dates_and_holidays(pdf_file):
    reader = PdfReader(pdf_file)
    text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])

    semester = "Unknown"
    if "Spring" in text:
        semester = "Spring"
        fallback_start, fallback_end = datetime(2025, 1, 6), datetime(2025, 5, 1)
        month_pattern = "January|February|March|April|May"
    elif "Summer" in text:
        semester = "Summer"
        fallback_start, fallback_end = datetime(2025, 5, 15), datetime(2025, 8, 10)
        month_pattern = "May|June|July|August"
    elif "Fall" in text:
        semester = "Fall"
        fallback_start, fallback_end = datetime(2025, 8, 20), datetime(2025, 12, 15)
        month_pattern = "August|September|October|November|December"
    else:
        fallback_start, fallback_end = datetime.today(), datetime.today() + timedelta(weeks=16)
        month_pattern = "January|February|March|April|May|June|July|August|September|October|November|December"

    start_match = re.search(r"First day of classes.*?((?:" + month_pattern + ") \d{1,2}, \d{4})", text)
    end_match = re.search(r"End of term.*?((?:" + month_pattern + ") \d{1,2}, \d{4})", text)

    start_date = datetime.strptime(start_match.group(1), "%B %d, %Y") if start_match else fallback_start
    end_date = datetime.strptime(end_match.group(1), "%B %d, %Y") if end_match else fallback_end

    # Improved holiday detection
    holiday_matches = re.findall(r"(?:Holiday|Break|No classes|Campus closed).*?((?:" + month_pattern + ") \d{1,2}, \d{4})", text)
    holidays = {datetime.strptime(date_str, "%B %d, %Y").date() for date_str in holiday_matches}

    return semester, start_date, end_date, holidays

# --- COURSE INPUT FORM ---
def get_course_input():
    with st.form(key="course_form"):
        # Timezone selection
        timezone = st.selectbox("Choose Your Timezone", pytz.all_timezones, index=pytz.all_timezones.index("US/Eastern"))

        # Number of courses
        num_courses = st.number_input("How many courses?", min_value=1, max_value=10, value=1)

        # Custom CSS for prettier days selection
        st.markdown("""
            <style>
            .stMultiSelect label {
                display: block;
                margin-bottom: 6px;
                font-weight: 600;
            }
            .css-1wa3eu0-MultiValue {
                background-color: #e6f0ff !important;
                border-radius: 999px !important;
                padding: 2px 10px;
                margin-right: 4px;
                font-weight: bold;
            }
            </style>
        """, unsafe_allow_html=True)

        course_data = []

        for i in range(num_courses):
            st.subheader(f"📘 Course {i+1}")
            subject = st.text_input(f"Subject {i+1}", key=f"subject_{i}")
            teacher = st.text_input(f"Teacher {i+1}", key=f"teacher_{i}")
            location = st.text_input(f"Location {i+1}", key=f"location_{i}")
            days = st.multiselect(f"Days {i+1}", ["MO", "TU", "WE", "TH", "FR"], key=f"days_{i}")
            start_time = st.time_input(f"Start Time {i+1}", key=f"start_{i}")
            end_time = st.time_input(f"End Time {i+1}", key=f"end_{i}")

            course_data.append({
                'subject': subject,
                'teacher': teacher,
                'location': location,
                'days': days,
                'start_time': start_time,
                'end_time': end_time
            })

        submit = st.form_submit_button("📅 Generate Calendar")
        return submit, timezone, course_data

# --- ICS GENERATOR ---
def generate_ics(start_date, end_date, course_data, timezone_str, holidays):
    cal = Calendar()
    tz = pytz.timezone(timezone_str)

    for course in course_data:
        for day in course['days']:
            weekday_int = ["MO", "TU", "WE", "TH", "FR"].index(day)
            days_ahead = (weekday_int - start_date.weekday() + 7) % 7
            current_date = start_date + timedelta(days=days_ahead)

            while current_date <= end_date:
                if current_date.date() in holidays:
                    current_date += timedelta(days=7)
                    continue

                dtstart = datetime.combine(current_date, course['start_time'])
                dtend = datetime.combine(current_date, course['end_time'])

                if dtend <= dtstart:
                    st.warning(f"⚠️ Skipping {course['subject']} on {current_date.strftime('%A')} because end time is before or equal to start time.")
                    current_date += timedelta(days=7)
                    continue

                event = Event()
                event.name = course['subject']
                event.begin = tz.localize(dtstart)
                event.end = tz.localize(dtend)
                event.location = course['location']
                event.description = f"{course['subject']} - {course['teacher']}"
                cal.events.add(event)

                current_date += timedelta(days=7)

    return cal

# --- MAIN LOGIC ---
pdf_file = st.file_uploader("Upload GT Academic Calendar (PDF)", type="pdf")

if pdf_file:
    semester, start_date, end_date, holidays = extract_semester_dates_and_holidays(pdf_file)
    st.success(f"📅 Detected {semester} semester: {start_date.strftime('%b %d')} to {end_date.strftime('%b %d')}")
    if holidays:
        st.info(f"📌 {len(holidays)} holidays detected: " + ", ".join(sorted(date.strftime("%b %d") for date in holidays)))
else:
    semester = st.selectbox("Select Semester", ["Spring", "Summer", "Fall", "Other"])
    start_date = st.date_input("Semester Start Date")
    end_date = st.date_input("Semester End Date")
    holidays = set()

submit, timezone_str, course_data = get_course_input()
if submit:
    cal = generate_ics(start_date, end_date, course_data, timezone_str, holidays)
    output = BytesIO(str(cal).encode("utf-8"))
    st.download_button("📥 Download ICS File", output, file_name="gt_schedule.ics", mime="text/calendar")
