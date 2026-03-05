import streamlit as st
from openai import OpenAI

st.title("🏡 AI Listing Assistant")

api_key = st.secrets["OPENAI_API_KEY"]
client = OpenAI(api_key=api_key)

st.write("Enter property details")

address = st.text_input("Address")
beds = st.number_input("Bedrooms", value=3)
baths = st.number_input("Bathrooms", value=2)
sqft = st.number_input("Square Feet", value=1800)
price = st.text_input("Price")
features = st.text_area("Features")

if st.button("Generate Listing"):

    prompt = f"""
    Create:

    1. MLS Listing description
    2. Social media post
    3. Email to buyers

    Property:
    Address: {address}
    Beds: {beds}
    Baths: {baths}
    Sqft: {sqft}
    Price: {price}
    Features: {features}
    """

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role":"user","content":prompt}]
    )

    st.write(response.choices[0].message.content)
