# Streamlit Chatbot Comparison Frontend

This project contains a Streamlit UI that compares responses from two chatbot models side-by-side, inspired by `UI.png`.

## Run locally

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Start the app:

   ```bash
   streamlit run app.py
   ```

## Response modes

- **Mock**: uses built-in deterministic responses for quick UI testing.
- **API-ready**: calls model endpoints if these environment variables are set:
  - `MODEL_A_ENDPOINT`
  - `MODEL_B_ENDPOINT`

If endpoints are not configured or calls fail, the UI falls back to mock responses.
