import streamlit as st
import pandas as pd
import stripe
import gspread
from google.oauth2.service_account import Credentials
from urllib.parse import urlencode

# --- GOOGLE SHEETS SETUP ---
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
)
client = gspread.authorize(creds)

# Connect to Sheets
events_sheet = client.open("event_data").worksheet("Events")
bookings_sheet = client.open("event_data").worksheet("Bookings")

# --- STRIPE SETUP ---
stripe.api_key = st.secrets["stripe_secret_key"]
base_url = "testapp1-7syhsu6x6hhrivhjekvc9v.streamlit.app"  # Replace with your actual domain if different

# --- LOAD DATA ---
def load_data():
    events_data = events_sheet.get_all_records()
    bookings_data = bookings_sheet.get_all_records()
    return pd.DataFrame(events_data), pd.DataFrame(bookings_data)

events_df, bookings_df = load_data()
st.session_state.events = events_df
st.session_state.bookings = bookings_df

# --- UI SETUP ---
st.set_page_config(page_title="Event Booking App", layout="wide")
st.title("🎟️ Event Booking & Registration")

tab1, tab2, tab3 = st.tabs(["Register a New Event", "Search Events", "View Bookings"])

# --- TAB 1: Register New Event ---
with tab1:
    with st.form("event_form"):
        st.subheader("Register a New Event")
        title = st.text_input("Event Title")
        date = st.date_input("Event Date")
        time = st.time_input("Event Time")
        info = st.text_area("Event Information")
        price = st.number_input("Price (£)", min_value=0.0, step=0.5)
        submitted = st.form_submit_button("Submit Event")

        if submitted:
            new_event = [len(events_df)+1, title, str(date), str(time), info, price]
            events_sheet.append_row(new_event)
            st.success("✅ Event registered successfully!")

# --- TAB 2: Search Events ---
with tab2:
    st.subheader("🔍 Search Events")

    # Debug display
    st.write("Columns:", st.session_state.events.columns.tolist())
    st.write("Preview of events data:")
    st.dataframe(st.session_state.events)

    search_title = st.text_input("Search by Title")
    filtered_events = st.session_state.events

    if "Title" in st.session_state.events.columns:
        if search_title:
            filtered_events = filtered_events[
                filtered_events["Title"].str.contains(search_title, case=False, na=False)
            ]

        if not filtered_events.empty:
            for idx, row in filtered_events.iterrows():
                with st.expander(f"{row['Title']} on {row['Date']} at {row['Time']}"):
                    st.write(f"**Info:** {row['Info']}")
                    st.write(f"**Price:** £{float(row['Price']):.2f}")
                    col1, col2 = st.columns(2)
                    if col1.button("Book Now", key=f"book_{idx}"):
                        row["Price"] = float(row["Price"])
                        st.session_state.booking_event = row.to_dict()
                        st.session_state.show_booking_form = True
                        st.experimental_rerun()
        else:
            st.info("No events matched your search.")
    else:
        st.warning("⚠️ The 'Title' column is missing from the events data.")

    # Booking form
    if st.session_state.get("show_booking_form"):
        st.subheader("Book Your Spot")

        event = st.session_state.booking_event
        name = st.text_input("Your Name")
        email = st.text_input("Your Email")
        dances = st.multiselect("Dance Style", ["Salsa", "Bachata", "Kizomba"])
        submit_booking = st.button("Pay and Book")

        if submit_booking and name and email and dances:
            try:
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=["card"],
                    line_items=[{
                        "price_data": {
                            "currency": "gbp",
                            "product_data": {
                                "name": event["Title"],
                            },
                            "unit_amount": int(event["Price"] * 100),
                        },
                        "quantity": 1,
                    }],
                    mode="payment",
                    success_url=base_url + f"?page=confirm&name={urlencode({'': name})[1:]}&email={urlencode({'': email})[1:]}&dances={urlencode({'': ','.join(dances)})[1:]}&event_id={event['ID']}",
                    cancel_url=base_url,
                )
                st.success("✅ Redirecting to payment...")
                st.markdown(f"[Click here to complete payment]({checkout_session.url})", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Error creating Stripe session: {e}")

# --- TAB 3: View Bookings ---
with tab3:
    st.subheader("📋 All Bookings")
    if not st.session_state.bookings.empty:
        st.dataframe(st.session_state.bookings)
    else:
        st.info("No bookings found yet.")

# --- SUCCESS HANDLER ---
if st.query_params.get("page") == "confirm":
    name = st.query_params.get("name", "")
    email = st.query_params.get("email", "")
    dances = st.query_params.get("dances", "")
    event_id = st.query_params.get("event_id", "")

    if all([name, email, dances, event_id]):
        booking = [name, email, dances, event_id]
        bookings_sheet.append_row(booking)
        st.success("✅ Your booking is confirmed! Thank you.")
        st.experimental_set_query_params()  # Clear URL
