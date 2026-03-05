import json
import streamlit as st
from openai import OpenAI
from openai import RateLimitError, APIError

st.set_page_config(page_title="AI Listing Assistant v2.0", page_icon="🏡", layout="centered")

# -----------------------
# Auth (simple password gate)
# -----------------------
def require_password() -> bool:
    expected = st.secrets.get("APP_PASSWORD", "")
    if not expected:
        # If no password set, don't gate
        return True

    if "authed" not in st.session_state:
        st.session_state.authed = False

    if st.session_state.authed:
        return True

    st.title("🏡 AI Listing Assistant")
    st.caption("Enter the demo password to continue.")

    pwd = st.text_input("Password", type="password")
    if st.button("Unlock"):
        if pwd == expected:
            st.session_state.authed = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()


require_password()

# -----------------------
# Client setup
# -----------------------
api_key = st.secrets.get("OPENAI_API_KEY", "")
if not api_key:
    st.error("Missing OPENAI_API_KEY in Streamlit Secrets.")
    st.stop()

client = OpenAI(api_key=api_key)

# -----------------------
# Session state
# -----------------------
if "history" not in st.session_state:
    st.session_state.history = []  # list of dicts {meta, outputs}
if "brand_voice" not in st.session_state:
    st.session_state.brand_voice = "Friendly, clear, professional. Avoid hype. Focus on benefits and key features."
if "busy" not in st.session_state:
    st.session_state.busy = False

# -----------------------
# UI
# -----------------------
st.title("🏡 AI Listing Assistant v2.0")
st.caption("Generate MLS copy + social pack + buyer email. Includes saved history and a brokerage voice profile.")

with st.expander("🏢 Brokerage Voice / Style Profile (saved)"):
    st.session_state.brand_voice = st.text_area(
        "Describe your brokerage voice (tone, length, do/don'ts).",
        value=st.session_state.brand_voice,
        height=120,
        placeholder="Example: Warm, confident, not salesy. Avoid ALL CAPS. Keep MLS factual..."
    )

colA, colB = st.columns(2)
with colA:
    tone = st.selectbox(
        "Tone preset",
        ["Professional MLS", "Warm + inviting", "Modern + punchy", "Luxury", "Investor-focused"],
        index=0
    )
with colB:
    include_cta = st.checkbox("Include a clear CTA", value=True)

with st.form("listing_form"):
    address = st.text_input("Address", placeholder="123 Maple St, Toledo, OH")
    price = st.text_input("Price", placeholder="$325,000")
    c1, c2, c3 = st.columns(3)
    with c1:
        beds = st.number_input("Bedrooms", min_value=0, max_value=20, value=3)
    with c2:
        baths = st.number_input("Bathrooms", min_value=0.0, max_value=20.0, value=2.0, step=0.5)
    with c3:
        sqft = st.number_input("Square feet", min_value=0, max_value=20000, value=1850, step=50)

    highlights = st.text_area(
        "Highlights / Features",
        placeholder="Renovated kitchen, fenced yard, finished basement, new HVAC, hardwood floors...",
        height=110
    )
    neighborhood = st.text_area(
        "Neighborhood / Location Notes",
        placeholder="Walkable to parks, close to downtown, top-rated schools, near highways...",
        height=90
    )

    submitted = st.form_submit_button("Generate Marketing Copy", disabled=st.session_state.busy)

# -----------------------
# Generation
# -----------------------
def build_prompt() -> str:
    cta = "Include a clear call-to-action (schedule a showing, message for details)." if include_cta else "No call-to-action."
    return f"""
You are a real estate marketing expert and MLS-compliant copywriter.

Follow this brokerage voice profile:
{st.session_state.brand_voice}

Rules:
- Avoid discriminatory language or references to protected classes.
- Keep MLS description factual, not exaggerated.
- Do not mention demographics.
- Do not invent details not provided.

Task:
Generate marketing copy for the property below.

Property details:
Address: {address}
Price: {price}
Beds: {beds}
Baths: {baths}
Square Feet: {sqft}
Highlights: {highlights}
Neighborhood notes: {neighborhood}

Tone preset: {tone}
CTA rule: {cta}

Return STRICT JSON with this schema:
{{
  "mls": {{
    "headline": "string (max 12 words)",
    "description": "string (120-180 words)"
  }},
  "social": {{
    "instagram": "string",
    "facebook": "string",
    "hashtags": ["string", "string", "string", "string", "string"]
  }},
  "email": {{
    "subject": "string",
    "body": "string (5-8 sentences)"
  }}
}}
"""

def safe_parse_json(text: str) -> dict:
    # Try direct JSON parse
    try:
        return json.loads(text)
    except Exception:
        # Try to extract JSON block if model included extra text
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end+1])
            except Exception:
                pass
        return {}

def generate_outputs() -> dict:
    prompt = build_prompt()
    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "You write compliant real estate marketing copy and return valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=800,
    )
    text = resp.choices[0].message.content
    data = safe_parse_json(text)
    if not data:
        # Fallback: show raw text in a minimal wrapper
        data = {
            "mls": {"headline": "Generated Listing", "description": text},
            "social": {"instagram": "", "facebook": "", "hashtags": []},
            "email": {"subject": "", "body": ""},
            "_raw": text,
        }
    return data

if submitted:
    if not address or not highlights:
        st.error("Please provide at least an address and some highlights/features.")
    else:
        st.session_state.busy = True
        try:
            with st.spinner("Generating..."):
                outputs = generate_outputs()

            # Save to history
            st.session_state.history.insert(0, {
                "meta": {
                    "address": address,
                    "price": price,
                    "beds": beds,
                    "baths": baths,
                    "sqft": sqft,
                    "tone": tone
                },
                "outputs": outputs
            })

            st.success("Generated and saved to history.")
        except RateLimitError:
            st.error("OpenAI rate limit / quota hit. Try again in a moment or check your API billing/limits.")
        except APIError as e:
            st.error(f"OpenAI API error: {e}")
        except Exception as e:
            st.error(f"Unexpected error: {e}")
        finally:
            st.session_state.busy = False

# -----------------------
# History + Results
# -----------------------
st.divider()

left, right = st.columns([0.9, 1.1])

with left:
    st.subheader("🕘 History")
    if not st.session_state.history:
        st.caption("No generations yet. Create one above.")
    else:
        options = []
        for i, item in enumerate(st.session_state.history):
            m = item["meta"]
            label = f'{m.get("address","(no address)")} — {m.get("price","")} ({m.get("tone","")})'
            options.append((label, i))

        selected_label = st.selectbox(
            "Select a previous result",
            options=[o[0] for o in options],
            index=0
        )
        selected_idx = next(i for (lbl, i) in options if lbl == selected_label)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Delete selected"):
                st.session_state.history.pop(selected_idx)
                st.rerun()
        with col2:
            if st.button("Clear all history"):
                st.session_state.history = []
                st.rerun()

with right:
    st.subheader("📄 Output")
    if not st.session_state.history:
        st.caption("Generate copy to see results here.")
    else:
        item = st.session_state.history[0]  # show most recent by default
        # If user selected a different item, use that
        if "selected_idx" in locals():
            item = st.session_state.history[selected_idx]

        outputs = item["outputs"]
        mls = outputs.get("mls", {})
        social = outputs.get("social", {})
        email = outputs.get("email", {})

        tab_mls, tab_social, tab_email = st.tabs(["MLS", "Social", "Email"])

        with tab_mls:
            st.markdown("**Headline**")
            st.code(mls.get("headline", ""), language="text")
            st.markdown("**Description**")
            st.code(mls.get("description", ""), language="text")

        with tab_social:
            st.markdown("**Instagram**")
            st.code(social.get("instagram", ""), language="text")
            st.markdown("**Facebook**")
            st.code(social.get("facebook", ""), language="text")
            tags = social.get("hashtags", [])
            if tags:
                st.markdown("**Hashtags**")
                st.code(" ".join([t if t.startswith("#") else f"#{t.replace(' ','')}" for t in tags]), language="text")

        with tab_email:
            st.markdown("**Subject**")
            st.code(email.get("subject", ""), language="text")
            st.markdown("**Body**")
            st.code(email.get("body", ""), language="text")

        # Export
        export_payload = {
            "meta": item["meta"],
            "outputs": outputs
        }
        st.download_button(
            "Download JSON",
            data=json.dumps(export_payload, indent=2).encode("utf-8"),
            file_name="listing_output.json",
            mime="application/json"
        )
