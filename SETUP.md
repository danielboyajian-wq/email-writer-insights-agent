# Email Insights Agent — Setup

Two-step prospecting tool: **company website → insights brief → optional email**.

## How it works

1. You paste a company URL
2. Claude (with web_fetch + web_search) reads their site and pulls external signals — news, hires, funding, product launches, hiring patterns, events, strategic moves
3. You see structured insights with "why it matters" tags
4. Pick which insights to anchor on, add a recipient + persona, optionally paste their LinkedIn
5. Get a drafted email in your tone

## 1. Install

```bash
cd "~/Desktop/email insights agent"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Add your API key

```bash
cp .env.example .env
# Paste your Anthropic key
```

Get a key at https://console.anthropic.com → API Keys.

No Tavily / search key needed — Claude handles search natively via the `web_search` server tool.

## 3. Add your tone

Edit `tones/tone.md`. Drop in 10–25 of your real emails. Format is in the file.

The whole tone file gets prompt-cached, so adding more examples doesn't increase cost after the first run.

## 4. Run

```bash
streamlit run app.py
```

Opens at http://localhost:8501.

## Files

```
app.py         # Streamlit UI
insights.py    # Claude + web_search/web_fetch -> structured brief
agent.py       # Email drafting (uses tones/tone.md)
personas.py    # Title -> persona priorities lookup
tones/tone.md  # YOUR tone description + examples
```

## Iterating

- Tone feels off? Add more examples to `tones/tone.md`
- Want different insight buckets? Edit `BUCKETS` in `insights.py`
- Want different persona hints? Edit `PERSONA_HINTS` in `personas.py`
