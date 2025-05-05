import streamlit as st
import pandas as pd
import uuid
import stripe
from urllib.parse import urlencode
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURATION ---
st.set_page_config(page_title="Event Manager", layout="wide")
st.title("🎉 Event Booking Web App")

# Stripe API Key
stripe.api_key = st.secrets["stripe"]["secret_key"]

# Google Sheets Setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
client = gspread.authorize(creds)

# Connect to Sheets
events_sheet = client.open("event_data").worksheet("Events")
bookings_sheet = client.open("event_data").worksheet("Bookings")

# Base URL for Stripe redirect
base_url = "https://testapp1.streamlit.app"

# --- SESSION STATE ---
if "show_booking_form" not in st.session_state:
    st.session_state.show_booking_form = False
if "booking_event" not in st.session_state:
    st.session_state.booking_event = {}

# --- LOAD DATA FROM SHEETS ---
@st.cache_data(ttl=300)
def load_events():
    records = events_sheet.get_all_records()
    return pd.DataFrame(records)

@st.cache_data(ttl=300)
def load_bookings():
    records = bookings_sheet.get_all_records()
    return pd.DataFrame(records)

st.session_state.events = load_events()
st.session_state.bookings = load_bookings()

# --- UI TABS ---
tab1, tab2, tab3 = st.tabs(["Register a New Event", "Search Events", "View Bookings"])

# --- TAB 1: Register Event ---
with tab1:
    st.subheader("Register a New Event")

    with st.form("event_form"):
        title = st.text_input("Event Title")
        date = st.date_input("Date of Event")
        location = st.text_input("Location")
        info = st.text_area("Additional Information")
        price = st.number_input("Price (£)", min_value=0.0, format="%.2f")
        submitted = st.form_submit_button("Submit")

    if submitted:
        event_id = str(uuid.uuid4())
        new_event = [event_id, title, str(date), location, info, float(price)]
        events_sheet.append_row(new_event)
        st.success("Event registered successfully!")
        st.rerun()

# --- TAB 2: Search Events ---
with tab2:
    st.subheader("Search Events")

    search_title = st.text_input("Search by Title")
    filtered_events = st.session_state.events

    if search_title:
        filtered_events = filtered_events[filtered_events["Title"].str.contains(search_title, case=False, na=False)]

    if not filtered_events.empty:
        for idx, row in filtered_events.iterrows():
            with st.expander(f"{row['Title']} on {row['Date']} at {row['Location']}"):
                st.write(f"**Info:** {row['Info']}")
                st.write(f"**Price:** £{row['Price']:.2f}")
                col1, col2 = st.columns(2)
                if col1.button("Book Now", key=f"book_{idx}"):
                    row["Price"] = float(row["Price"])
                    st.session_state.booking_event = row.to_dict()
                    st.session_state.show_booking_form = True
                    st.rerun()
    else:
        st.info("No events found.")

# --- TAB 3: View Bookings ---
with tab3:
    st.subheader("All Bookings")
    if not st.session_state.bookings.empty:
        st.dataframe(st.session_state.bookings)
    else:
        st.info("No bookings yet.")

# --- SHOW BOOKING FORM ---
if st.session_state.show_booking_form:
    event = st.session_state.booking_event
    st.sidebar.header("Complete Booking for:")
    st.sidebar.markdown(f"**{event['Title']}** on **{event['Date']}**")
    st.sidebar.markdown(f"**Location:** {event['Location']}")
    st.sidebar.markdown(f"**Price:** £{float(event['Price']):.2f}")

    with st.sidebar.form("booking_form"):
        name = st.text_input("Your Name")
        email = st.text_input("Your Email")
        dances = st.multiselect("Select Dances", ["Heavy Jig", "Light Jig", "Reel", "Championship"])
        confirm = st.form_submit_button("Proceed to Payment")

    if confirm:
        if not name or not email or not dances:
            st.sidebar.warning("Please complete all fields.")
        else:
            # Build success URL
            success_url = base_url + "/?page=confirm" + \
                f"&name={urlencode({'': name})[1:]}" + \
                f"&email={urlencode({'': email})[1:]}" + \
                f"&dances={urlencode({'': ','.join(dances)})[1:]}" + \
                f"&event_id={event['ID']}"

            # Create Stripe checkout session
            try:
                session = stripe.checkout.Session.create(
                    payment_method_types=["card"],
                    line_items=[{
                        "price_data": {
                            "currency": "gbp",
                            "product_data": {
                                "name": f"{event['Title']} - {event['Date']}"
                            },
                            "unit_amount": int(float(event['Price']) * 100),
                        },
                        "quantity": 1,
                    }],
                    mode="payment",
                    success_url=success_url,
                    cancel_url=base_url
                )
                st.sidebar.markdown(f"[Click to Pay via Stripe]({session.url})", unsafe_allow_html=True)
            except Exception as e:
                st.sidebar.error(f"Stripe error: {e}")

# --- HANDLE PAYMENT CONFIRMATION ---
query_params = st.query_params
if query_params.get("page") == "confirm":
    st.success("✅ Payment Confirmed!")

    name = query_params.get("name", "")
    email = query_params.get("email", "")
    dances = query_params.get("dances", "")
    event_id = query_params.get("event_id", "")

    booking_id = str(uuid.uuid4())
    booking_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    booking_data = [booking_id, event_id, name, email, dances, booking_date]
    bookings_sheet.append_row(booking_data)

    st.write("Thank you for your booking!")
    st.write(f"**Name:** {name}")
    st.write(f"**Email:** {email}")
    st.write(f"**Dances:** {dances}")
    st.write(f"**Booking ID:** {booking_id}")
