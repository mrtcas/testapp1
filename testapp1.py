import streamlit as st
import pandas as pd
import gspread
import stripe
from oauth2client.service_account import ServiceAccountCredentials
from urllib.parse import urlencode

# Stripe setup
stripe.api_key = st.secrets["stripe"]["secret_key"]
STRIPE_PUBLISHABLE_KEY = st.secrets["stripe"]["publishable_key"]

# Set page
st.set_page_config(page_title="Event Booking App", layout="centered")

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
client = gspread.authorize(credentials)

# Load sheets
def get_sheet(name):
    return client.open(name).sheet1

event_sheet = get_sheet("testapp1_events")
booking_sheet = get_sheet("testapp1_bookings")

# Load events into session
def load_events():
    try:
        events = event_sheet.get_all_records()
        return pd.DataFrame(events)
    except:
        return pd.DataFrame()

if "events_df" not in st.session_state:
    st.session_state.events_df = load_events()

# Tabs
tab1, tab2, tab3 = st.tabs(["Register Event", "Search Events", "View Bookings"])

# --- TAB 1: Register Event ---
with tab1:
    st.subheader("Register a New Event")
    with st.form("event_form"):
        title = st.text_input("Event Title")
        date = st.date_input("Date")
        location = st.text_input("Location")
        info = st.text_area("Additional Information")
        price = st.number_input("Price (£)", min_value=1.0, format="%.2f")
        submitted = st.form_submit_button("Register Event")
        if submitted:
            event_sheet.append_row([str(date), title, location, info, float(price)])
            st.success("Event registered.")
            st.session_state.events_df = load_events()
            st.experimental_rerun()

# --- TAB 2: Search & Book ---
with tab2:
    st.subheader("Search for Events")
    events = st.session_state.events_df
    if events.empty:
        st.info("No events found.")
    else:
        search = st.text_input("Search by Title or Location")
        filtered = events[
            events["Title"].str.contains(search, case=False, na=False) |
            events["Location"].str.contains(search, case=False, na=False)
        ] if search else events

        for idx, row in filtered.iterrows():
            try:
                price = float(row.get("Price", 0))
            except (ValueError, TypeError):
                price = 0.0
            with st.expander(f"{row['Title']} on {row['Date']} at {row['Location']}"):
                st.write(f"**Info:** {row['Info']}")
                st.write(f"**Price:** £{price:.2f}")
                if st.button("Book Now", key=f"book_{idx}"):
                    row["Price"] = price
                    st.session_state.booking_event = row.to_dict()
                    st.session_state.show_booking_form = True #set the session state
                    st.rerun()

# --- TAB 3: View Bookings ---
with tab3:
    st.subheader("All Bookings")
    try:
        bookings = booking_sheet.get_all_records()
        if bookings:
            st.dataframe(pd.DataFrame(bookings))
        else:
            st.info("No bookings yet.")
    except Exception as e:
        st.error(f"Error loading bookings: {e}")

# --- BOOKING PAGE (via query param) ---
if st.session_state.get("show_booking_form"): #check the session state
    st.subheader("Book This Event")
    event = st.session_state.get("booking_event")
    if not event:
        st.warning("No event selected.")
        st.stop()

    with st.form("booking_form"):
        name = st.text_input("Your Name")
        email = st.text_input("Your Email")
        dances = st.multiselect("Select Dances", ["Heavy Jig", "Light Jig", "Reel", "Championship"])
        book = st.form_submit_button("Proceed to Payment")

        if book and name and email and dances:
            try:
                price = float(event["Price"])
            except (ValueError, TypeError):
                price = 0.0

            # Create Stripe Checkout Session
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "gbp",
                        "product_data": {"name": f"{event['Title']} - {event['Date']}"},
                        "unit_amount": int(price * 100),
                    },
                    "quantity": 1,
                }],
                mode="payment",
		base_url = "https://testapp1.streamlit.app"  # Or your actual deployed URL
		success_url = base_url + "/?page=confirm" + \
              		f"&name={urlencode({'': name})[1:]}" + \
              		f"&email={urlencode({'': email})[1:]}" + \
              		f"&dances={urlencode({'': ','.join(dances)})[1:]}",
                cancel_url=st.experimental_get_url(),
            )

            st.success("Redirecting to Stripe Checkout...")
            st.markdown(f"""
                <meta http-equiv="refresh" content="0; URL={session.url}" />
            """, unsafe_allow_html=True)
            st.stop()

# --- PAYMENT CONFIRMATION PAGE ---
if st.query_params.get("page") == "confirm":
    st.success("Payment Successful! Booking confirmed.")
    name = st.query_params.get("name", "")
    email = st.query_params.get("email", "")
    dances = st.query_params.get("dances", "")
    event = st.session_state.get("booking_event")

    if not event:
        st.error("Missing event context.")
        st.stop()

    # Log booking
    booking_sheet.append_row([
        event["Title"], event["Date"], event["Location"],
        name, email, dances
    ])

    st.write(f"**Name:** {name}")
    st.write(f"**Event:** {event['Title']} on {event['Date']} at {event['Location']}")
    st.write(f"**Dances:** {dances}")
    st.write("You will receive a confirmation email shortly.")
