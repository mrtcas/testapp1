import streamlit as st
import pandas as pd
from datetime import datetime
import smtplib
from email.message import EmailMessage

# Page config
st.set_page_config(page_title="Event Manager - testapp1", page_icon="📅")
st.title("📅 Event Registration, Booking and Search - testapp1")

# Email credentials from secrets
EMAIL_ADDRESS = st.secrets["email"]["address"]
EMAIL_PASSWORD = st.secrets["email"]["password"]

# Function to send confirmation email
def send_booking_email(to_email, name, event, dances):
    msg = EmailMessage()
    msg["Subject"] = f"Your Booking for {event['Title']}"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email

    dance_list = ", ".join(dances)
    body = f"""
Hi {name},

This is to confirm your booking for the event:

Event: {event['Title']}
Date: {event['Date']}
Location: {event['Location']}
Dances: {dance_list}

Thank you for registering!
"""
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Failed to send confirmation email: {e}")
        return False

# Session state initialization
if 'events' not in st.session_state:
    st.session_state.events = pd.DataFrame(columns=["Date", "Title", "Location", "Info"])
if 'edit_index' not in st.session_state:
    st.session_state.edit_index = None
if 'bookings' not in st.session_state:
    st.session_state.bookings = []
if 'show_booking_form' not in st.session_state:
    st.session_state.show_booking_form = False
if 'booking_event' not in st.session_state:
    st.session_state.booking_event = None
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "edit"

# Tabs
tab1, tab2, tab3 = st.tabs(["Register/Edit Event", "Search Events", "View Bookings"])

# --- Register/Edit Tab ---
if st.session_state.active_tab == "edit":
    with tab1:
        st.header("Register a New Event")

        with st.form("event_form", clear_on_submit=True):
            if st.session_state.edit_index is None:
                event_date = st.date_input("Date of Event", value=datetime.now())
                event_title = st.text_input("Event Title")
                event_location = st.text_input("Location")
                event_info = st.text_area("Additional Information")
            else:
                event = st.session_state.events.iloc[st.session_state.edit_index]
                event_date = st.date_input("Date of Event", value=pd.to_datetime(event['Date']))
                event_title = st.text_input("Event Title", value=event['Title'])
                event_location = st.text_input("Location", value=event['Location'])
                event_info = st.text_area("Additional Information", value=event['Info'])

            submitted = st.form_submit_button("Save Event")

            if submitted:
                new_event = {
                    "Date": event_date,
                    "Title": event_title,
                    "Location": event_location,
                    "Info": event_info
                }
                if st.session_state.edit_index is None:
                    st.session_state.events = pd.concat(
                        [st.session_state.events, pd.DataFrame([new_event])],
                        ignore_index=True
                    )
                    st.success("Event registered successfully!")
                else:
                    st.session_state.events.iloc[st.session_state.edit_index] = new_event
                    st.success("Event updated successfully!")
                    st.session_state.edit_index = None

        st.subheader("Existing Events")

        if not st.session_state.events.empty:
            for idx, row in st.session_state.events.iterrows():
                with st.expander(f"{row['Title']} on {row['Date']} at {row['Location']}"):
                    st.write(f"**Info:** {row['Info']}")
                    col1, col2, col3 = st.columns(3)
                    if col1.button("Edit", key=f"edit_{idx}"):
                        st.session_state.edit_index = idx
                        st.session_state.active_tab = "edit"
                    if col2.button("Delete", key=f"delete_{idx}"):
                        st.session_state.events.drop(idx, inplace=True)
                        st.session_state.events.reset_index(drop=True, inplace=True)
                        st.success("Event deleted successfully!")
                        st.session_state.active_tab = "edit"
                    if col3.button("Book Now", key=f"book_{idx}"):
                        st.session_state.booking_event = idx
                        st.session_state.show_booking_form = True
                        st.session_state.active_tab = "edit"

            if st.session_state.show_booking_form:
                idx = st.session_state.booking_event
                if idx is not None and idx < len(st.session_state.events):
                    event = st.session_state.events.iloc[idx]
                    st.subheader(f"Booking for: {event['Title']} on {event['Date']}")
                    with st.form("booking_form"):
                        name = st.text_input("Your Name")
                        email = st.text_input("Your Email Address")
                        dances = st.multiselect("Dance Selections", ["Heavy Jig", "Light Jig", "Reel", "Championship"])
                        submit_booking = st.form_submit_button("Submit Booking")
                        if submit_booking:
                            booking = {
                                "Event": event['Title'],
                                "Date": event['Date'],
                                "Location": event['Location'],
                                "Name": name,
                                "Email": email,
                                "Dances": dances
                            }
                            st.session_state.bookings.append(booking)
                            email_sent = send_booking_email(email, name, event, dances)
                            if email_sent:
                                st.success("Booking submitted and confirmation email sent!")
                            else:
                                st.warning("Booking submitted, but email failed.")
                            st.session_state.show_booking_form = False
                            st.session_state.booking_event = None

        else:
            st.info("No events registered yet.")

# --- Search Events Tab ---
if st.session_state.active_tab == "search":
    with tab2:
        st.header("Search Events")

        search_query = st.text_input("Search by Title or Location", key="search_text")
        search_date = st.date_input("Or search by Date", value=None, key="search_date")

        filtered_events = st.session_state.events.copy()

        if search_query:
            filtered_events = filtered_events[
                filtered_events["Title"].str.contains(search_query, case=False, na=False) |
                filtered_events["Location"].str.contains(search_query, case=False, na=False)
            ]

        if search_date and search_date != datetime.now().date():
            filtered_events = filtered_events[filtered_events["Date"] == pd.to_datetime(search_date)]

        st.subheader(f"Found {len(filtered_events)} event(s):")
        st.dataframe(filtered_events)

# --- View Bookings Tab ---
if st.session_state.active_tab == "bookings":
    with tab3:
        st.header("View Bookings")

        if st.session_state.bookings:
            booking_df = pd.DataFrame(st.session_state.bookings)
            st.dataframe(booking_df)
        else:
            st.info("No bookings yet.")
