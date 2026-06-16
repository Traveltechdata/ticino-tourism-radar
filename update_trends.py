#!/usr/bin/env python3
"""
Ticino Tourism Radar — Google Trends Updater
Esegue ogni lunedì alle 07:00 via GitHub Actions.
Aggiorna il nodo marketing_trends in radar_data.json.
"""

import json
import time
import datetime
from pytrends.request import TrendReq

# ── Configurazione keyword e geo
KEYWORDS = ["Tessin", "Lago Maggiore", "Ascona", "Locarno", "Brissago"]
GEO_LIST = ["DE", "CH"]
TIMEFRAME = "now 7-d"

def fetch_trends(keywords, geo):
    """Scarica i trend per una lista di keyword e un geo."""
    pytrends = TrendReq(hl="de-DE", tz=60, timeout=(10, 25))
    pytrends.build_payload(keywords, cat=0, timeframe=TIMEFRAME, geo=geo)
    time.sleep(2)  # evita rate limiting
    df = pytrends.interest_over_time()
    return df

def calcola_crescita(df, keyword):
    """Calcola la variazione % tra prima metà e seconda metà della settimana."""
    if keyword not in df.columns or df.empty:
        return None, "N/D"
    serie = df[keyword].tolist()
    if len(serie) < 4:
        return None, "N/D"
    meta = len(serie) // 2
    media_prima = sum(serie[:meta]) / meta if meta > 0 else 0
    media_seconda = sum(serie[meta:]) / (len(serie) - meta) if (len(serie) - meta) > 0 else 0
    if media_prima == 0:
        return 0, "Stabile"
    delta = ((media_seconda - media_prima) / media_prima) * 100
    if abs(delta) < 5:
        label = "Stabile"
    elif delta > 0:
        label = f"+{round(delta)}%"
    else:
        label = f"{round(delta)}%"
    trend = "up" if delta > 5 else ("down" if delta < -5 else "stable")
    return round(delta), label, trend

# Suggerimenti dipendenti dalla DIREZIONE del trend, non fissi per keyword
def genera_suggerimento(keyword, trend):
    if trend == "up":
        opzioni = {
            "Tessin": "Ricerche in crescita: spingi questa keyword nei titoli di post e newsletter ora",
            "Lago Maggiore": "Onda di interesse alta: pubblica foto del lago al tramonto con questa keyword nel caption",
            "Ascona": "Domanda in salita: controlla disponibilit\u00e0 Booking e valuta un rialzo tariffario",
            "Locarno": "Interesse in aumento: menziona il Film Festival nei post per intercettare l'intent",
            "Brissago": "Trend positivo: lancia una campagna micro-targeting FB/IG verso utenti ZH/DE",
            "Cannobio": "Ricerche in crescita: evidenzia l'accesso transfrontaliero nelle descrizioni Booking"
        }
        return opzioni.get(keyword, "Ricerche in crescita: aumenta la presenza social su questa keyword")
    elif trend == "down":
        opzioni = {
            "Tessin": "Ricerche in calo: la domanda si sposta su termini pi\u00f9 specifici, punta su 'Lago Maggiore' o sulla tua localit\u00e0",
            "Lago Maggiore": "Interesse in flessione: differenzia con esperienze uniche (gastronomia, eventi) invece della sola destinazione",
            "Ascona": "Ricerche in calo: rafforza il brand con contenuti di valore, non sconti che erodono il posizionamento premium",
            "Locarno": "Interesse in flessione: prepara i contenuti per il picco Film Festival, non spingere ora",
            "Brissago": "Ricerche in calo: punta sulla nicchia, evita campagne ampie poco efficienti in questa fase",
            "Cannobio": "Interesse in flessione: concentra il budget sui canali transfrontalieri ad alta conversione"
        }
        return opzioni.get(keyword, "Ricerche in calo: rivedi la strategia, non investire su questa keyword ora")
    else:  # stable
        opzioni = {
            "Tessin": "Domanda stabile: mantieni presenza costante, usa come keyword di base nei contenuti",
            "Lago Maggiore": "Interesse costante: keyword affidabile per contenuti sempreverdi e SEO di base",
            "Ascona": "Brand stabile: ottimo momento per consolidare le recensioni e la reputazione online",
            "Locarno": "Domanda costante: mantieni i contenuti aggiornati in vista dei picchi stagionali",
            "Brissago": "Nicchia stabile: punta sulla qualit\u00e0 e sulla conversione, non sul volume",
            "Cannobio": "Domanda costante: presidia il canale transfrontaliero con descrizioni curate"
        }
        return opzioni.get(keyword, "Domanda stabile: mantieni una presenza costante su questa keyword")

NOTE = {
    "Tessin": "Termine ombrello — cattura tutto il mercato DACH verso il cantone",
    "Lago Maggiore": "Alta intent turistica, pubblico pronto a prenotare",
    "Ascona": "Brand forte, ricercato da pubblico alto-spendente svizzero-tedesco",
    "Locarno": "Picco legato al Film Festival — prenotazioni anticipate",
    "Brissago": "Nicchia premium, bassa competizione, alta conversione",
    "Cannobio": "Mercato transfrontaliero IT/CH, crescita costante"
}

def main():
    print(f"[{datetime.datetime.now()}] Avvio aggiornamento Google Trends...")

    ricerche_top = []
    seen = set()

    for geo in GEO_LIST:
        print(f"  Fetching trends per geo={geo}...")
        try:
            df = fetch_trends(KEYWORDS, geo)
            for kw in KEYWORDS:
                if kw in seen:
                    continue
                result = calcola_crescita(df, kw)
                if result and result[0] is not None:
                    delta_num, label, trend = result
                    ricerche_top.append({
                        "keyword": kw,
                        "crescita": label,
                        "trend": trend,
                        "geo": geo,
                        "note": NOTE.get(kw, ""),
                        "suggerimento_azione": genera_suggerimento(kw, trend)
                    })
                    seen.add(kw)
            time.sleep(3)
        except Exception as e:
            print(f"  Errore geo={geo}: {e}")
            continue

    # Fallback: aggiungi keyword mancanti con dati neutri
    for kw in KEYWORDS:
        if kw not in seen:
            ricerche_top.append({
                "keyword": kw,
                "crescita": "N/D",
                "trend": "stable",
                "geo": "N/D",
                "note": NOTE.get(kw, ""),
                "suggerimento_azione": genera_suggerimento(kw, "stable")
            })

    # Ordina: prima quelli con crescita positiva
    ricerche_top.sort(key=lambda x: (
        0 if x["trend"] == "up" else (1 if x["trend"] == "stable" else 2)
    ))

    # Leggi radar_data.json
    with open("radar_data.json", "r", encoding="utf-8") as f:
        radar = json.load(f)

    # Aggiorna nodo marketing_trends
    oggi = datetime.date.today().isoformat()
    radar["marketing_trends"]["settimana"] = oggi
    radar["marketing_trends"]["ricerche_top"] = ricerche_top

    # Scrivi il file aggiornato
    with open("radar_data.json", "w", encoding="utf-8") as f:
        json.dump(radar, f, ensure_ascii=False, indent=2)

    print(f"  radar_data.json aggiornato con {len(ricerche_top)} keyword")
    print(f"  Trend aggiornati: {[k['keyword'] + ' ' + k['crescita'] for k in ricerche_top]}")
    print(f"[{datetime.datetime.now()}] Completato.")

if __name__ == "__main__":
    main()
